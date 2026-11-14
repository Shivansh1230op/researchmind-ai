"""Tests for the RAGPipeline.

Tests cover:
- Answer generation with mocked LLM
- Source citation assembly
- Confidence score calculation
- No-answer detection
- Conversation memory integration
- Error handling when LLM fails
- Context building
- Prompt construction

The LLM service is mocked so tests don't require an API key.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.services.rag_pipeline import RAGPipeline
from app.services.retrieval_service import RetrievalResult


class TestRAGPipeline:
    """Tests for the RAGPipeline class."""

    @pytest.fixture
    def mock_pipeline(self):
        """Create a RAGPipeline with all services mocked."""
        pipeline = RAGPipeline.__new__(RAGPipeline)
        pipeline.retrieval_service = MagicMock()
        pipeline.memory_service = MagicMock()
        pipeline.llm_service = MagicMock()
        pipeline.default_top_k = 5

        # Memory service returns empty history by default
        pipeline.memory_service.get_history_messages.return_value = []
        pipeline.memory_service.max_history = 10

        return pipeline

    def _make_mock_results(self, count=3):
        """Create mock retrieval results."""
        results = []
        for i in range(count):
            r = RetrievalResult(
                content=f"Content from chunk {i} about machine learning.",
                metadata={
                    "document_id": "doc1",
                    "document_name": "textbook.pdf",
                    "page_number": i + 1,
                    "chunk_index": i,
                },
                similarity_score=0.9 - i * 0.1,
                final_score=0.9 - i * 0.1,
            )
            results.append(r)
        return results

    def test_answer_generation_success(self, mock_pipeline):
        """Test that the pipeline generates an answer when retrieval succeeds."""
        # Mock retrieval to return results
        mock_results = self._make_mock_results(3)
        mock_pipeline.retrieval_service.retrieve.return_value = mock_results

        # Mock LLM to return a coherent answer
        mock_pipeline.llm_service.generate_response.return_value = (
            "Machine learning is a subset of AI [textbook.pdf, page 1]. "
            "It enables systems to learn from data [textbook.pdf, page 2]."
        )

        result = mock_pipeline.answer_question(
            question="What is machine learning?",
            session_id="test_session",
        )

        assert result["no_answer_found"] is False
        assert "machine learning" in result["answer"].lower()
        assert len(result["sources"]) == 3
        assert result["confidence"] > 0
        assert result["session_id"] == "test_session"

    def test_no_results_returns_no_answer(self, mock_pipeline):
        """Test that no retrieval results returns a no-answer response."""
        mock_pipeline.retrieval_service.retrieve.return_value = []

        result = mock_pipeline.answer_question(
            question="What is quantum physics?",
            session_id="test_session",
        )

        assert result["no_answer_found"] is True
        assert "couldn't find" in result["answer"].lower()
        assert len(result["sources"]) == 0
        assert result["confidence"] == 0.0

    def test_no_answer_detection(self, mock_pipeline):
        """Test that 'I couldn't find' responses are detected."""
        mock_results = self._make_mock_results(2)
        mock_pipeline.retrieval_service.retrieve.return_value = mock_results
        mock_pipeline.llm_service.generate_response.return_value = (
            "I couldn't find this information in the uploaded documents."
        )

        result = mock_pipeline.answer_question(
            question="What is quantum computing?",
            session_id="test_session",
        )

        assert result["no_answer_found"] is True

    def test_source_citations_built(self, mock_pipeline):
        """Test that source citations are correctly assembled from retrieval results."""
        mock_results = self._make_mock_results(2)
        mock_pipeline.retrieval_service.retrieve.return_value = mock_results
        mock_pipeline.llm_service.generate_response.return_value = (
            "Here is the answer [textbook.pdf, page 1]."
        )

        result = mock_pipeline.answer_question(
            question="What is ML?",
            session_id="test_session",
        )

        sources = result["sources"]
        assert len(sources) == 2
        assert sources[0]["document_name"] == "textbook.pdf"
        assert sources[0]["page_number"] == 1
        assert sources[0]["chunk_index"] == 0
        assert "content" in sources[0]
        assert "similarity_score" in sources[0]

    def test_confidence_calculation(self, mock_pipeline):
        """Test that confidence is the average of top retrieval scores."""
        mock_results = self._make_mock_results(3)
        # Scores: 0.9, 0.8, 0.7 → avg of top 3 = 0.8
        mock_pipeline.retrieval_service.retrieve.return_value = mock_results
        mock_pipeline.llm_service.generate_response.return_value = "Answer here."

        result = mock_pipeline.answer_question(
            question="test question",
            session_id="session1",
        )

        expected_confidence = round((0.9 + 0.8 + 0.7) / 3, 4)
        assert result["confidence"] == expected_confidence

    def test_llm_failure_handled_gracefully(self, mock_pipeline):
        """Test that LLM failures are handled without crashing."""
        mock_results = self._make_mock_results(2)
        mock_pipeline.retrieval_service.retrieve.return_value = mock_results
        mock_pipeline.llm_service.generate_response.side_effect = Exception("API error")

        result = mock_pipeline.answer_question(
            question="test question",
            session_id="session1",
        )

        assert result["no_answer_found"] is True
        assert "error" in result["answer"].lower()
        assert result["confidence"] == 0.0

    def test_memory_stored_after_answer(self, mock_pipeline):
        """Test that both user and assistant messages are stored in memory."""
        mock_results = self._make_mock_results(1)
        mock_pipeline.retrieval_service.retrieve.return_value = mock_results
        mock_pipeline.llm_service.generate_response.return_value = "Answer."

        mock_pipeline.answer_question(
            question="What is AI?",
            session_id="session123",
        )

        # Should have called add_message twice (user + assistant)
        assert mock_pipeline.memory_service.add_message.call_count == 2

        # First call: user message
        first_call = mock_pipeline.memory_service.add_message.call_args_list[0]
        assert first_call[0][1] == "user"

        # Second call: assistant message
        second_call = mock_pipeline.memory_service.add_message.call_args_list[1]
        assert second_call[0][1] == "assistant"

    def test_conversation_history_passed_to_llm(self, mock_pipeline):
        """Test that conversation history is passed to the LLM."""
        mock_results = self._make_mock_results(1)
        mock_pipeline.retrieval_service.retrieve.return_value = mock_results
        mock_pipeline.memory_service.get_history_messages.return_value = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]
        mock_pipeline.llm_service.generate_response.return_value = "Answer."

        mock_pipeline.answer_question(
            question="Follow up question",
            session_id="session1",
        )

        # Verify the LLM was called with conversation_history
        call_kwargs = mock_pipeline.llm_service.generate_response.call_args[1]
        assert "conversation_history" in call_kwargs
        assert len(call_kwargs["conversation_history"]) == 2

    def test_context_building(self, mock_pipeline):
        """Test that context is built from retrieved chunks with source labels."""
        mock_results = self._make_mock_results(2)
        context = mock_pipeline._build_context(mock_results)

        assert "[Source 1:" in context
        assert "[Source 2:" in context
        assert "textbook.pdf" in context

    def test_user_prompt_contains_question(self, mock_pipeline):
        """Test that the user prompt includes the question and context."""
        context = "Some document context here."
        question = "What is the main finding?"
        prompt = mock_pipeline._build_user_prompt(question, context)

        assert question in prompt
        assert context in prompt
        assert "QUESTION:" in prompt

    def test_top_k_override(self, mock_pipeline):
        """Test that top_k can be overridden per request."""
        mock_results = self._make_mock_results(1)
        mock_pipeline.retrieval_service.retrieve.return_value = mock_results
        mock_pipeline.llm_service.generate_response.return_value = "Answer."

        mock_pipeline.answer_question(
            question="test",
            session_id="s1",
            top_k=10,
        )

        # Verify retrieve was called with top_k=10
        call_kwargs = mock_pipeline.retrieval_service.retrieve.call_args[1]
        assert call_kwargs["top_k"] == 10

    def test_document_filter_passed_through(self, mock_pipeline):
        """Test that document_ids filter is passed to retrieval."""
        mock_results = self._make_mock_results(1)
        mock_pipeline.retrieval_service.retrieve.return_value = mock_results
        mock_pipeline.llm_service.generate_response.return_value = "Answer."

        mock_pipeline.answer_question(
            question="test",
            session_id="s1",
            document_ids=["doc_a", "doc_b"],
        )

        call_kwargs = mock_pipeline.retrieval_service.retrieve.call_args[1]
        assert call_kwargs["document_ids"] == ["doc_a", "doc_b"]
