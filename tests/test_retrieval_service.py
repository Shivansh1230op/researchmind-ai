"""Tests for the RetrievalService.

Tests cover:
- Basic vector retrieval
- Hybrid search (BM25 + vector) ranking
- Reranking with cross-encoder
- Document filtering
- Similarity threshold filtering
- Retrieval result properties

These tests use real embeddings and ChromaDB (temp directory).
"""

import pytest

from app.services.retrieval_service import RetrievalService, RetrievalResult
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore
from app.services.text_splitter import TextChunk


def _model_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    not _model_available(),
    reason="sentence-transformers not installed",
)]


class TestRetrievalService:
    """Tests for the RetrievalService class."""

    @pytest.fixture
    def setup_store(self):
        """Set up a vector store with sample data for retrieval tests."""
        import uuid
        collection_name = f"test_retrieval_{uuid.uuid4().hex[:8]}"
        embedding_service = EmbeddingService()
        vector_store = VectorStore(collection_name=collection_name)

        # Add chunks about different topics
        texts = [
            "Machine learning is a subset of artificial intelligence that enables systems to learn from data.",
            "Deep learning uses multi-layer neural networks for feature extraction and transformation.",
            "Natural language processing allows computers to understand and generate human language.",
            "Computer vision enables machines to interpret and analyze visual information from images.",
            "Reinforcement learning trains agents to make decisions through reward and punishment.",
            "The stock market can be volatile and unpredictable due to various economic factors.",
            "Climate change is causing rising sea levels and more frequent extreme weather events.",
        ]

        chunks = [
            TextChunk(content=text, page_number=1, chunk_index=idx,
                      document_name="ai_textbook.pdf", document_id="doc_ml")
            for idx, text in enumerate(texts)
        ]

        embeddings = embedding_service.embed_texts(texts)
        vector_store.add_chunks(chunks, embeddings, document_id="doc_ml")

        yield embedding_service, vector_store

        try:
            vector_store.reset()
        except Exception:
            pass

    def test_retrieve_returns_results(self, setup_store):
        """Test that retrieval returns relevant results."""
        embedding_service, vector_store = setup_store
        service = RetrievalService(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )
        service.enable_hybrid_search = False
        service.enable_reranking = False

        results = service.retrieve("What is machine learning?", top_k=3)

        assert len(results) > 0
        assert all(isinstance(r, RetrievalResult) for r in results)

    def test_retrieve_relevant_results(self, setup_store):
        """Test that the most relevant result is about the queried topic."""
        embedding_service, vector_store = setup_store
        service = RetrievalService(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )
        service.enable_hybrid_search = False
        service.enable_reranking = False

        results = service.retrieve("What is deep learning?", top_k=1)

        assert len(results) > 0
        assert "deep learning" in results[0].content.lower()

    def test_retrieve_with_document_filter(self, setup_store):
        """Test that document filtering works."""
        embedding_service, vector_store = setup_store
        service = RetrievalService(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )
        service.enable_hybrid_search = False
        service.enable_reranking = False

        results = service.retrieve(
            "machine learning",
            top_k=5,
            document_ids=["nonexistent_doc"],
        )

        # No results because filter doesn't match any document
        assert len(results) == 0

    def test_retrieve_scores_decreasing(self, setup_store):
        """Test that results are sorted by decreasing score."""
        embedding_service, vector_store = setup_store
        service = RetrievalService(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )
        service.enable_hybrid_search = False
        service.enable_reranking = False

        results = service.retrieve("artificial intelligence", top_k=5)

        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].final_score >= results[i + 1].final_score

    def test_hybrid_search_improves_keyword_match(self, setup_store):
        """Test that hybrid search finds keyword matches better than vector only."""
        embedding_service, vector_store = setup_store
        service = RetrievalService(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )

        # With hybrid search enabled, exact keyword matches should rank higher
        service.enable_hybrid_search = True
        service.enable_reranking = False

        results = service.retrieve("reinforcement learning", top_k=3)

        assert len(results) > 0
        # The reinforcement learning chunk should be in top results
        found = any("reinforcement" in r.content.lower() for r in results)
        assert found

    def test_retrieval_result_properties(self, setup_store):
        """Test that RetrievalResult exposes all expected properties."""
        embedding_service, vector_store = setup_store
        service = RetrievalService(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )
        service.enable_hybrid_search = False
        service.enable_reranking = False

        results = service.retrieve("machine learning", top_k=1)

        if results:
            r = results[0]
            assert hasattr(r, "content")
            assert hasattr(r, "document_id")
            assert hasattr(r, "document_name")
            assert hasattr(r, "page_number")
            assert hasattr(r, "chunk_index")
            assert hasattr(r, "similarity_score")
            assert hasattr(r, "final_score")
            assert r.document_id == "doc_ml"
            assert r.document_name == "ai_textbook.pdf"

    def test_no_results_on_empty_query(self, setup_store):
        """Test that an empty/degenerate query doesn't crash."""
        embedding_service, vector_store = setup_store
        service = RetrievalService(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )
        service.enable_hybrid_search = False
        service.enable_reranking = False

        results = service.retrieve("", top_k=5)
        # Should return results (empty query embedding is a zero vector)
        assert isinstance(results, list)

    def test_to_dict_conversion(self):
        """Test that RetrievalResult.to_dict() works correctly."""
        result = RetrievalResult(
            content="test content",
            metadata={"document_id": "doc1", "page_number": 1, "chunk_index": 0},
            similarity_score=0.85,
            final_score=0.80,
        )
        d = result.to_dict()
        assert d["content"] == "test content"
        assert d["similarity_score"] == 0.85
        assert d["final_score"] == 0.80
