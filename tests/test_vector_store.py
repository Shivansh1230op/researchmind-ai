"""Tests for the VectorStore service.

Tests cover:
- Adding chunks with embeddings
- Semantic search returns relevant results
- Metadata filtering by document_id
- Deleting chunks for a specific document
- Collection statistics
- Search with no results

These tests use the real ChromaDB (persisted to a temp directory).
"""

import pytest

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


class TestVectorStore:
    """Tests for the VectorStore class."""

    @pytest.fixture
    def store(self):
        """Provide a VectorStore with a unique test collection."""
        import uuid
        collection_name = f"test_{uuid.uuid4().hex[:8]}"
        vs = VectorStore(collection_name=collection_name)
        yield vs
        try:
            vs.reset()
        except Exception:
            pass

    @pytest.fixture
    def embedding_service(self):
        from app.services.embedding_service import EmbeddingService
        return EmbeddingService()

    def _make_chunks(self, texts, doc_id="test_doc_1", doc_name="test.pdf"):
        """Helper to create TextChunk objects from text strings."""
        return [
            TextChunk(
                content=text,
                page_number=1,
                chunk_index=idx,
                document_name=doc_name,
                document_id=doc_id,
            )
            for idx, text in enumerate(texts)
        ]

    def test_add_chunks(self, store, embedding_service):
        """Test adding chunks to the vector store."""
        texts = [
            "Artificial intelligence is the simulation of human intelligence.",
            "Machine learning is a subset of artificial intelligence.",
            "Deep learning uses neural networks with many layers.",
        ]
        chunks = self._make_chunks(texts)
        embeddings = embedding_service.embed_texts(texts)

        added = store.add_chunks(chunks, embeddings, document_id="test_doc_1")

        assert added == 3
        assert store.collection.count() == 3

    def test_search_returns_results(self, store, embedding_service):
        """Test that semantic search returns relevant results."""
        texts = [
            "Python is a popular programming language for data science.",
            "Machine learning algorithms learn patterns from data.",
            "The weather today is sunny and warm.",
            "Neural networks are inspired by the human brain.",
        ]
        chunks = self._make_chunks(texts)
        embeddings = embedding_service.embed_texts(texts)
        store.add_chunks(chunks, embeddings, document_id="test_doc_1")

        query_embedding = embedding_service.embed_query("What is machine learning?")
        results = store.search(query_embedding, top_k=2)

        assert len(results) == 2
        # The most relevant result should be about ML
        assert "machine learning" in results[0]["content"].lower()

    def test_search_with_document_filter(self, store, embedding_service):
        """Test that document_ids filter works correctly."""
        texts_doc1 = ["Machine learning is powerful for pattern recognition."]
        texts_doc2 = ["Climate change affects global temperatures significantly."]

        chunks1 = self._make_chunks(texts_doc1, doc_id="doc1")
        chunks2 = self._make_chunks(texts_doc2, doc_id="doc2", doc_name="climate.pdf")

        emb1 = embedding_service.embed_texts(texts_doc1)
        emb2 = embedding_service.embed_texts(texts_doc2)

        store.add_chunks(chunks1, emb1, document_id="doc1")
        store.add_chunks(chunks2, emb2, document_id="doc2")

        query_emb = embedding_service.embed_query("What is machine learning?")
        results = store.search(query_emb, top_k=5, document_ids=["doc1"])

        # All results should be from doc1
        for result in results:
            assert result["metadata"]["document_id"] == "doc1"

    def test_delete_document(self, store, embedding_service):
        """Test that deleting a document removes its chunks."""
        texts = ["Test content about AI and ML."]
        chunks = self._make_chunks(texts, doc_id="to_delete")
        embeddings = embedding_service.embed_texts(texts)
        store.add_chunks(chunks, embeddings, document_id="to_delete")

        assert store.get_document_chunk_count("to_delete") == 1

        deleted = store.delete_document("to_delete")
        assert deleted == 1
        assert store.get_document_chunk_count("to_delete") == 0

    def test_delete_nonexistent_document(self, store):
        """Deleting a non-existent document should not raise."""
        deleted = store.delete_document("nonexistent_doc")
        assert deleted >= 0  # Should not crash

    def test_search_no_results(self, store, embedding_service):
        """Test search on empty collection."""
        query_emb = embedding_service.embed_query("test query")
        results = store.search(query_emb, top_k=5)

        assert len(results) == 0

    def test_get_collection_stats(self, store, embedding_service):
        """Test that collection stats are correct."""
        texts = ["Content one.", "Content two.", "Content three."]
        chunks = self._make_chunks(texts, doc_id="stats_doc")
        embeddings = embedding_service.embed_texts(texts)
        store.add_chunks(chunks, embeddings, document_id="stats_doc")

        stats = store.get_collection_stats()
        assert stats["total_chunks"] == 3
        assert stats["unique_documents"] == 1

    def test_get_all_documents(self, store, embedding_service):
        """Test getting list of document IDs in the store."""
        chunks1 = self._make_chunks(["Doc 1 content"], doc_id="doc_a")
        chunks2 = self._make_chunks(["Doc 2 content"], doc_id="doc_b")

        emb1 = embedding_service.embed_texts(["Doc 1 content"])
        emb2 = embedding_service.embed_texts(["Doc 2 content"])

        store.add_chunks(chunks1, emb1, document_id="doc_a")
        store.add_chunks(chunks2, emb2, document_id="doc_b")

        doc_ids = store.get_all_documents()
        assert "doc_a" in doc_ids
        assert "doc_b" in doc_ids

    def test_metadata_preserved(self, store, embedding_service):
        """Test that metadata (page number, chunk index) is stored correctly."""
        chunks = [
            TextChunk(content="Page 1 content", page_number=1, chunk_index=0,
                      document_name="test.pdf", document_id="meta_doc"),
            TextChunk(content="Page 2 content", page_number=2, chunk_index=1,
                      document_name="test.pdf", document_id="meta_doc"),
        ]
        embeddings = embedding_service.embed_texts(["Page 1 content", "Page 2 content"])
        store.add_chunks(chunks, embeddings, document_id="meta_doc")

        query_emb = embedding_service.embed_query("Page 2 content")
        results = store.search(query_emb, top_k=1)

        assert results[0]["metadata"]["page_number"] == 2
        assert results[0]["metadata"]["chunk_index"] == 1
        assert results[0]["metadata"]["document_name"] == "test.pdf"
