"""SQLAlchemy ORM models for DocuMind AI.

Two tables:
- ``documents``: metadata about each uploaded file (name, path, size, etc.)
- ``conversations`` / ``messages``: chat history per session

These models store *metadata* only — the actual text content and vectors
live in the ChromaDB vector store.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Index
from sqlalchemy.dialects.sqlite import JSON  # works on PostgreSQL too
from sqlalchemy.orm import relationship

from app.database.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(320), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    password_hash = Column(Text, nullable=False)


class SignupChallenge(Base):
    __tablename__ = "signup_challenges"
    id = Column(String(64), primary_key=True)
    email = Column(String(320), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False)
    password_hash = Column(Text, nullable=False)
    code_hash = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    sent_at = Column(DateTime, nullable=False)
    window_started_at = Column(DateTime, nullable=False)
    send_count = Column(Integer, nullable=False, default=1)
    attempts = Column(Integer, nullable=False, default=0)
    consumed = Column(Integer, nullable=False, default=0)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)


class Workspace(Base):
    __tablename__ = "workspaces"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DocumentAccess(Base):
    __tablename__ = "document_access"
    document_id = Column(String, ForeignKey("documents.id"), primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False, index=True)


class DocumentProcessingJob(Base):
    __tablename__ = "document_processing_jobs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default="queued", index=True)
    stage = Column(String(30), nullable=False, default="queued")
    attempts = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ConversationPreferences(Base):
    __tablename__ = "conversation_preferences"
    session_id = Column(String(100), ForeignKey("conversation_sessions.session_id"), primary_key=True)
    display_title = Column(String(120), nullable=False)


class ResearchReport(Base):
    __tablename__ = "research_reports"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    workspace_id = Column(String, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    sources_json = Column(JSON, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def _utcnow() -> datetime:
    """Return current UTC datetime — used as default for timestamp columns."""
    return datetime.now(timezone.utc)


def _generate_uuid() -> str:
    """Generate a UUID4 string for primary keys."""
    return str(uuid.uuid4())


class Document(Base):
    """ORM model for an uploaded document.

    Attributes:
        id: UUID primary key.
        filename: Original file name as uploaded.
        file_path: Where the file is stored on disk.
        file_type: Extension without dot (e.g. "pdf", "docx").
        file_size: Size in bytes.
        total_pages: Number of pages (for PDFs) or None.
        total_chunks: Number of text chunks created from this document.
        metadata_json: Additional flexible metadata (author, title, etc.).
        status: "processing", "ready", or "error".
        error_message: If status is "error", describes what went wrong.
        created_at / updated_at: Timestamps.
    """

    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=_generate_uuid)
    filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_type = Column(String(20), nullable=False)
    file_size = Column(Integer, nullable=False)
    total_pages = Column(Integer, nullable=True)
    total_chunks = Column(Integer, default=0, nullable=False)
    metadata_json = Column(JSON, nullable=True, default=dict)
    status = Column(String(20), default="processing", nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    # Relationship: one document → many chat messages that reference it
    messages = relationship("ChatMessage", back_populates="document")

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.filename}, status={self.status})>"


class ConversationSession(Base):
    """ORM model for a conversation session.

    Each session groups a series of Q&A exchanges.  The session_id is
    sent by the frontend so conversations stay isolated between users.
    """

    __tablename__ = "conversation_sessions"

    id = Column(String, primary_key=True, default=_generate_uuid)
    session_id = Column(String(100), nullable=False, unique=True, index=True)
    title = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    messages = relationship("ChatMessage", back_populates="session",
                            order_by="ChatMessage.created_at", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ConversationSession(session_id={self.session_id}, messages={len(self.messages)})>"


class ChatMessage(Base):
    """ORM model for a single chat message (user question or AI answer).

    Attributes:
        role: "user" or "assistant".
        content: The message text.
        sources_json: For assistant messages, the cited sources as JSON.
        document_id: If the question referenced a specific document.
    """

    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=_generate_uuid)
    session_id = Column(String(100), ForeignKey("conversation_sessions.session_id"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    sources_json = Column(JSON, nullable=True, default=list)
    document_id = Column(String, ForeignKey("documents.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    session = relationship("ConversationSession", back_populates="messages")
    document = relationship("Document", back_populates="messages")

    # Index for fast session-based retrieval
    __table_args__ = (
        Index("ix_chat_messages_session_created", "session_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ChatMessage(role={self.role}, session={self.session_id})>"
