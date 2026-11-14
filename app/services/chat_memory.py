"""Conversation memory service for managing chat history.

Maintains conversation history per session, with support for:
- Follow-up questions (the LLM can see previous Q&A)
- Document context preservation across questions
- Session isolation (each session has its own history)
- Configurable history length (older messages are dropped)

History is stored both in SQLite (for persistence) and in memory
(for fast access during a conversation).
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.database.database import get_db_context
from app.database.models import ConversationSession, ChatMessage

logger = get_logger(__name__)


class ChatMemoryService:
    """Manages conversation history per session.

    Each session is identified by a unique session_id provided by the
    frontend.  Messages are stored in the database and can be retrieved
    for building context-aware prompts.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.max_history = settings.max_conversation_history

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: Optional[List[Dict]] = None,
        document_id: Optional[str] = None,
    ) -> None:
        """Add a message to the conversation history.

        Args:
            session_id: Unique session identifier.
            role: "user" or "assistant".
            content: Message text.
            sources: List of source citation dicts (for assistant messages).
            document_id: Optional document reference.
        """
        with get_db_context() as db:
            # Ensure the session exists
            session = db.query(ConversationSession).filter_by(session_id=session_id).first()
            if session is None:
                session = ConversationSession(session_id=session_id)
                db.add(session)
                db.flush()

            message = ChatMessage(
                session_id=session_id,
                role=role,
                content=content,
                sources_json=sources or [],
                document_id=document_id,
            )
            db.add(message)
            from datetime import datetime, timezone
            session.updated_at = datetime.now(timezone.utc)
            db.commit()

        logger.info(
            f"Added {role} message to session {session_id} "
            f"(content length: {len(content)})"
        )

    def get_history(
        self,
        session_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve conversation history for a session.

        Args:
            session_id: Session to retrieve history for.
            limit: Maximum number of messages to return (most recent).
                   Defaults to max_conversation_history setting.

        Returns:
            List of message dicts with 'role', 'content', 'sources', 'timestamp'.
        """
        limit = limit or self.max_history

        with get_db_context() as db:
            messages = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
                .all()
            )

            # Reverse to get chronological order
            messages.reverse()

            history = [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "sources": msg.sources_json or [],
                    "timestamp": msg.created_at.isoformat() if msg.created_at else None,
                }
                for msg in messages
            ]

        logger.info(f"Retrieved {len(history)} messages for session {session_id}")
        return history

    def get_history_for_prompt(
        self,
        session_id: str,
        limit: Optional[int] = None,
    ) -> str:
        """Format conversation history as a string for the LLM prompt.

        Args:
            session_id: Session to retrieve history for.
            limit: Number of recent messages to include.

        Returns:
            Formatted conversation history string, or empty string if
            no history exists.
        """
        history = self.get_history(session_id, limit)

        if not history:
            return ""

        formatted = []
        for msg in history:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            formatted.append(f"{role_label}: {msg['content']}")

        return "\n\n".join(formatted)

    def get_history_messages(
        self,
        session_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """Get history as a list of {role, content} dicts for LangChain.

        Args:
            session_id: Session to retrieve history for.
            limit: Number of recent messages.

        Returns:
            List of {"role": "user"/"assistant", "content": str} dicts.
        """
        history = self.get_history(session_id, limit)
        return [{"role": m["role"], "content": m["content"]} for m in history]

    def clear_history(self, session_id: str) -> int:
        """Delete all messages for a session.

        Args:
            session_id: Session to clear.

        Returns:
            Number of messages deleted.
        """
        with get_db_context() as db:
            deleted = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id)
                .delete(synchronize_session=False)
            )
            # Also update session timestamp
            session = db.query(ConversationSession).filter_by(session_id=session_id).first()
            if session:
                session.updated_at = datetime.now(timezone.utc)

            db.commit()

        logger.info(f"Cleared {deleted} messages for session {session_id}")
        return deleted

    def delete_session(self, session_id: str) -> int:
        """Delete an entire session and all its messages.

        Args:
            session_id: Session to delete.

        Returns:
            Number of messages deleted.
        """
        with get_db_context() as db:
            messages_count = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id)
                .count()
            )

            db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).delete(synchronize_session=False)

            db.query(ConversationSession).filter(
                ConversationSession.session_id == session_id
            ).delete(synchronize_session=False)

            db.commit()

        logger.info(f"Deleted session {session_id} with {messages_count} messages")
        return messages_count

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """List all conversation sessions.

        Returns:
            List of session dicts with id, session_id, created_at, message_count.
        """
        with get_db_context() as db:
            sessions = db.query(ConversationSession).all()
            result = []

            for session in sessions:
                msg_count = (
                    db.query(ChatMessage)
                    .filter(ChatMessage.session_id == session.session_id)
                    .count()
                )
                result.append({
                    "session_id": session.session_id,
                    "title": session.title,
                    "created_at": session.created_at.isoformat() if session.created_at else None,
                    "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                    "message_count": msg_count,
                })

        return result

    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists in the database."""
        with get_db_context() as db:
            return (
                db.query(ConversationSession)
                .filter_by(session_id=session_id)
                .first()
                is not None
            )
