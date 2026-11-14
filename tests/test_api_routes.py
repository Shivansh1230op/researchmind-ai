"""Tests for the API routes.

Tests cover:
- Health check endpoint
- Document upload (PDF, TXT)
- Document listing
- Document deletion
- Chat endpoint (with mocked LLM)
- Chat history retrieval
- Chat history clearing
- Error responses (404, 400, 422)
- API documentation (Swagger)

The LLM is mocked so tests don't require an API key.
"""

import io
import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_check_returns_200(self, api_client: TestClient):
        """Test that the health endpoint returns 200."""
        response = api_client.get("/health")
        assert response.status_code == 200

    def test_health_check_contains_version(self, api_client: TestClient):
        """Test that the health response includes the version."""
        response = api_client.get("/health")
        data = response.json()
        assert "version" in data
        assert "database" in data
        assert "vector_store" in data

    def test_root_endpoint(self, api_client: TestClient):
        """Test the root endpoint returns basic info."""
        response = api_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "docs" in data


class TestDocumentEndpoints:
    """Tests for document upload, listing, and deletion."""

    def test_upload_txt_document(self, api_client: TestClient):
        """Test uploading a TXT file."""
        file_content = b"This is a test document about artificial intelligence."
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}

        with patch("app.services.document_processor.DocumentProcessor.process_upload") as mock_proc:
            mock_proc.return_value = {
                "id": "test-doc-id",
                "filename": "test.txt",
                "file_type": "txt",
                "file_size": 48,
                "total_pages": 1,
                "total_chunks": 1,
                "status": "ready",
                "created_at": "2025-01-01T00:00:00",
                "extra_metadata": {},
            }

            response = api_client.post("/documents/upload", files=files)

        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "test.txt"
        assert data["status"] == "ready"

    def test_upload_unsupported_file_type(self, api_client: TestClient):
        """Test that unsupported file types are rejected."""
        files = {"file": ("test.exe", io.BytesIO(b"content"), "application/octet-stream")}

        response = api_client.post("/documents/upload", files=files)

        assert response.status_code == 400
        assert "unsupported" in response.json()["detail"].lower()

    def test_list_documents_empty(self, api_client: TestClient):
        """Test listing documents when none exist."""
        response = api_client.get("/documents")

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "total" in data
        assert isinstance(data["documents"], list)

    def test_delete_nonexistent_document(self, api_client: TestClient):
        """Test that deleting a non-existent document returns 404."""
        with patch("app.services.document_processor.DocumentProcessor.delete_document", return_value=False):
            response = api_client.delete("/documents/nonexistent-id")

        assert response.status_code == 404


class TestChatEndpoints:
    """Tests for the chat and chat history endpoints."""

    def test_chat_success(self, api_client: TestClient):
        """Test the chat endpoint with a mocked RAG pipeline."""
        mock_result = {
            "answer": "Machine learning is a subset of AI [doc.pdf, page 1].",
            "sources": [
                {
                    "document_id": "doc1",
                    "document_name": "doc.pdf",
                    "page_number": 1,
                    "chunk_index": 0,
                    "content": "Machine learning is a subset of AI.",
                    "similarity_score": 0.85,
                }
            ],
            "session_id": "test-session",
            "question": "What is ML?",
            "confidence": 0.85,
            "no_answer_found": False,
        }

        with patch("app.api.routes.get_rag_pipeline") as mock_get:
            mock_pipeline = MagicMock()
            mock_pipeline.answer_question.return_value = mock_result
            mock_get.return_value = mock_pipeline

            response = api_client.post("/chat", json={
                "question": "What is ML?",
                "session_id": "test-session",
            })

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == mock_result["answer"]
        assert len(data["sources"]) == 1
        assert data["no_answer_found"] is False

    def test_chat_empty_question_rejected(self, api_client: TestClient):
        """Test that empty questions are rejected."""
        response = api_client.post("/chat", json={
            "question": "",
            "session_id": "test-session",
        })

        assert response.status_code == 422  # Validation error

    def test_chat_missing_session_id(self, api_client: TestClient):
        """Test that missing session_id is rejected."""
        response = api_client.post("/chat", json={
            "question": "What is AI?",
        })

        assert response.status_code == 422

    def test_chat_no_answer_found(self, api_client: TestClient):
        """Test the no-answer-found response."""
        mock_result = {
            "answer": "I couldn't find this in the documents.",
            "sources": [],
            "session_id": "test-session",
            "question": "What is quantum physics?",
            "confidence": 0.0,
            "no_answer_found": True,
        }

        with patch("app.api.routes.get_rag_pipeline") as mock_get:
            mock_pipeline = MagicMock()
            mock_pipeline.answer_question.return_value = mock_result
            mock_get.return_value = mock_pipeline

            response = api_client.post("/chat", json={
                "question": "What is quantum physics?",
                "session_id": "test-session",
            })

        assert response.status_code == 200
        data = response.json()
        assert data["no_answer_found"] is True

    def test_chat_history_retrieval(self, api_client: TestClient):
        """Test getting chat history."""
        mock_history = [
            {
                "role": "user",
                "content": "What is AI?",
                "sources": None,
                "timestamp": "2025-01-01T00:00:00",
            },
            {
                "role": "assistant",
                "content": "AI is the simulation of human intelligence.",
                "sources": [],
                "timestamp": "2025-01-01T00:00:01",
            },
        ]

        with patch("app.api.routes.get_chat_memory") as mock_get:
            mock_memory = MagicMock()
            mock_memory.get_history.return_value = mock_history
            mock_get.return_value = mock_memory

            response = api_client.get("/chat/history", params={"session_id": "test"})

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["messages"]) == 2

    def test_clear_chat_history(self, api_client: TestClient):
        """Test clearing chat history."""
        with patch("app.api.routes.get_chat_memory") as mock_get:
            mock_memory = MagicMock()
            mock_memory.clear_history.return_value = 5
            mock_get.return_value = mock_memory

            response = api_client.post("/chat/clear", params={"session_id": "test"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Cleared 5 messages" in data["message"]


class TestSummarizationEndpoint:
    """Tests for the document summarization endpoint."""

    def test_summarize_success(self, api_client: TestClient):
        """Test successful document summarization."""
        from app.main import app
        from app.api.routes import get_db
        from app.database.database import SessionLocal

        mock_result = {
            "document_id": "doc1",
            "document_name": "test.pdf",
            "summary": "This document discusses AI and machine learning.",
            "summary_type": "comprehensive",
            "key_points": None,
            "definitions": None,
        }

        # Create a mock DB session that returns a document when queried
        mock_session = MagicMock()
        mock_doc = MagicMock()
        mock_doc.filename = "test.pdf"
        mock_doc.id = "doc1"
        mock_session.query.return_value.all.return_value = [mock_doc]
        mock_session.get.return_value = mock_doc
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_doc

        # Override the get_db dependency
        app.dependency_overrides[get_db] = lambda: mock_session

        try:
            with patch("app.api.routes.get_summarization_service") as mock_get:
                mock_service = MagicMock()
                mock_service.summarize.return_value = mock_result
                mock_get.return_value = mock_service

                response = api_client.post("/documents/summarize", json={
                    "document_id": "doc1",
                    "summary_type": "comprehensive",
                })
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200

    def test_summarize_nonexistent_document(self, api_client: TestClient):
        """Test summarizing a non-existent document returns 404."""
        from app.main import app
        from app.api.routes import get_db

        # Mock session returns None (document not found)
        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        app.dependency_overrides[get_db] = lambda: mock_session

        try:
            response = api_client.post("/documents/summarize", json={
                "document_id": "nonexistent",
                "summary_type": "comprehensive",
            })
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 404


class TestComparisonEndpoint:
    """Tests for the document comparison endpoint."""

    def test_compare_success(self, api_client: TestClient):
        """Test successful document comparison."""
        from app.main import app
        from app.api.routes import get_db

        mock_result = {
            "comparison": "Document A focuses on ML while Document B covers NLP.",
            "document_names": ["doc_a.pdf", "doc_b.pdf"],
            "aspects_covered": ["general"],
        }

        # Mock session returns a document for each query
        mock_session = MagicMock()
        mock_doc = MagicMock()
        mock_doc.filename = "doc.pdf"
        doc_a, doc_b = MagicMock(), MagicMock()
        doc_a.id, doc_b.id = "doc_a", "doc_b"
        mock_session.query.return_value.all.return_value = [doc_a, doc_b]
        mock_session.get.return_value = mock_doc
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_doc

        app.dependency_overrides[get_db] = lambda: mock_session

        try:
            with patch("app.api.routes.get_comparison_service") as mock_get:
                mock_service = MagicMock()
                mock_service.compare.return_value = mock_result
                mock_get.return_value = mock_service

                response = api_client.post("/documents/compare", json={
                    "document_ids": ["doc_a", "doc_b"],
                    "aspect": "general",
                })
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 200

    def test_compare_insufficient_documents(self, api_client: TestClient):
        """Test that comparing fewer than 2 documents is rejected."""
        response = api_client.post("/documents/compare", json={
            "document_ids": ["doc_a"],
            "aspect": "general",
        })

        assert response.status_code == 422  # min_length=2 validation


class TestAPIDocumentation:
    """Tests for API documentation endpoints."""

    def test_swagger_docs_available(self, api_client: TestClient):
        """Test that Swagger UI is accessible."""
        response = api_client.get("/docs")
        assert response.status_code == 200

    def test_openapi_schema_available(self, api_client: TestClient):
        """Test that the OpenAPI schema is accessible."""
        response = api_client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data
        assert "/chat" in data["paths"]
        assert "/documents/upload" in data["paths"]
        assert "/health" in data["paths"]
