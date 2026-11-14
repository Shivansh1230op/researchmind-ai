"""Tests for the ChatMemoryService.

Tests cover:
- Adding user and assistant messages
- Retrieving conversation history
- History chronological ordering
- Clearing chat history
- Session isolation (different sessions don't share history)
- History length limiting
- Formatting history for LLM prompts
- Session listing and existence checks
"""

import pytest
from datetime import datetime

from app.services.chat_memory import ChatMemoryService


class TestChatMemoryService:
    """Tests for the ChatMemoryService class."""

    @pytest.fixture
    def memory_service(self):
        return ChatMemoryService()

    @pytest.fixture
    def session_id(self):
        """Generate a unique session ID for each test."""
        import uuid
        return f"test-session-{uuid.uuid4().hex[:8]}"

    def test_add_user_message(self, memory_service, session_id):
        """Test adding a user message to history."""
        memory_service.add_message(session_id, "user", "What is machine learning?")

        history = memory_service.get_history(session_id)
        assert len(history) == 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "What is machine learning?"

    def test_add_assistant_message_with_sources(self, memory_service, session_id):
        """Test adding an assistant message with source citations."""
        sources = [
            {"document_name": "doc.pdf", "page_number": 1, "content": "excerpt"}
        ]
        memory_service.add_message(
            session_id, "assistant", "ML is a subset of AI.", sources=sources
        )

        history = memory_service.get_history(session_id)
        assert len(history) == 1
        assert history[0]["role"] == "assistant"
        assert len(history[0]["sources"]) == 1

    def test_history_chronological_order(self, memory_service, session_id):
        """Test that history is returned in chronological order."""
        memory_service.add_message(session_id, "user", "First question")
        memory_service.add_message(session_id, "assistant", "First answer")
        memory_service.add_message(session_id, "user", "Second question")
        memory_service.add_message(session_id, "assistant", "Second answer")

        history = memory_service.get_history(session_id)
        assert len(history) == 4
        assert history[0]["content"] == "First question"
        assert history[1]["content"] == "First answer"
        assert history[2]["content"] == "Second question"
        assert history[3]["content"] == "Second answer"

    def test_clear_history(self, memory_service, session_id):
        """Test that clearing history removes all messages."""
        memory_service.add_message(session_id, "user", "Test question")
        memory_service.add_message(session_id, "assistant", "Test answer")

        deleted = memory_service.clear_history(session_id)
        assert deleted == 2

        history = memory_service.get_history(session_id)
        assert len(history) == 0

    def test_session_isolation(self, memory_service):
        """Test that different sessions have isolated histories."""
        session1 = "session-isolation-1"
        session2 = "session-isolation-2"

        memory_service.add_message(session1, "user", "Question for session 1")
        memory_service.add_message(session2, "user", "Question for session 2")

        history1 = memory_service.get_history(session1)
        history2 = memory_service.get_history(session2)

        assert len(history1) == 1
        assert len(history2) == 1
        assert history1[0]["content"] == "Question for session 1"
        assert history2[0]["content"] == "Question for session 2"

    def test_history_limit(self, memory_service, session_id):
        """Test that history is limited to the specified count."""
        # Add more messages than the limit
        for i in range(15):
            memory_service.add_message(session_id, "user", f"Question {i}")
            memory_service.add_message(session_id, "assistant", f"Answer {i}")

        # Retrieve with limit=5
        history = memory_service.get_history(session_id, limit=5)
        assert len(history) == 5
        # Should be the most recent 5 messages
        assert history[-1]["content"] == "Answer 14"

    def test_get_history_for_prompt(self, memory_service, session_id):
        """Test that history is formatted correctly for the LLM prompt."""
        memory_service.add_message(session_id, "user", "What is AI?")
        memory_service.add_message(session_id, "assistant", "AI is artificial intelligence.")

        formatted = memory_service.get_history_for_prompt(session_id)
        assert "User: What is AI?" in formatted
        assert "Assistant: AI is artificial intelligence." in formatted

    def test_get_history_for_prompt_empty(self, memory_service, session_id):
        """Test that empty history returns an empty string."""
        formatted = memory_service.get_history_for_prompt(session_id)
        assert formatted == ""

    def test_get_history_messages_format(self, memory_service, session_id):
        """Test that get_history_messages returns the right dict format."""
        memory_service.add_message(session_id, "user", "Test question")
        memory_service.add_message(session_id, "assistant", "Test answer")

        messages = memory_service.get_history_messages(session_id)
        assert len(messages) == 2
        assert messages[0] == {"role": "user", "content": "Test question"}
        assert messages[1] == {"role": "assistant", "content": "Test answer"}

    def test_delete_session(self, memory_service, session_id):
        """Test that deleting a session removes all its data."""
        memory_service.add_message(session_id, "user", "Question")
        memory_service.add_message(session_id, "assistant", "Answer")

        deleted = memory_service.delete_session(session_id)
        assert deleted == 2

        history = memory_service.get_history(session_id)
        assert len(history) == 0

    def test_session_exists(self, memory_service):
        """Test checking if a session exists."""
        session_id = "existence-test-session"
        assert not memory_service.session_exists(session_id)

        memory_service.add_message(session_id, "user", "Hello")
        assert memory_service.session_exists(session_id)

    def test_get_all_sessions(self, memory_service):
        """Test listing all sessions."""
        session1 = "list-test-1"
        session2 = "list-test-2"

        memory_service.add_message(session1, "user", "Q1")
        memory_service.add_message(session2, "user", "Q2")

        sessions = memory_service.get_all_sessions()
        session_ids = [s["session_id"] for s in sessions]
        assert session1 in session_ids
        assert session2 in session_ids

    def test_message_count_in_sessions(self, memory_service):
        """Test that session list includes message counts."""
        session_id = "count-test-session"
        memory_service.add_message(session_id, "user", "Q1")
        memory_service.add_message(session_id, "assistant", "A1")
        memory_service.add_message(session_id, "user", "Q2")
        memory_service.add_message(session_id, "assistant", "A2")

        sessions = memory_service.get_all_sessions()
        target = next(s for s in sessions if s["session_id"] == session_id)
        assert target["message_count"] == 4
