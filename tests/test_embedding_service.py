"""Tests for the EmbeddingService.

Tests cover:
- Embedding generation for text
- Query embedding (single text)
- Embedding dimension consistency
- Similarity computation
- Empty text handling
- Model loading check

NOTE: These tests require the sentence-transformers package and will
download the model on first run. Tests that need embeddings are
marked to skip if the model can't be loaded.
"""

import pytest
import numpy as np

from app.services.embedding_service import EmbeddingService


def _model_available() -> bool:
    """Check if sentence-transformers is installed and model loads."""
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    not _model_available(),
    reason="sentence-transformers not installed",
)]


class TestEmbeddingService:
    """Tests for the EmbeddingService class."""

    @pytest.fixture
    def service(self):
        return EmbeddingService()

    def test_embed_single_text(self, service):
        """Test embedding a single text string."""
        embedding = service.embed_query("Hello world")

        assert isinstance(embedding, list)
        assert len(embedding) > 0  # Should have a dimension
        assert all(isinstance(x, float) for x in embedding)

    def test_embed_multiple_texts(self, service):
        """Test embedding multiple text strings."""
        texts = ["First text", "Second text", "Third text"]
        embeddings = service.embed_texts(texts)

        assert len(embeddings) == 3
        assert all(len(e) == len(embeddings[0]) for e in embeddings)

    def test_embedding_dimension_consistency(self, service):
        """All embeddings should have the same dimension."""
        emb1 = service.embed_query("short text")
        emb2 = service.embed_query("a much longer text with more words and content here")

        assert len(emb1) == len(emb2)

    def test_embedding_dimension_matches_model(self, service):
        """Embedding dimension should match the model's reported dimension."""
        embedding = service.embed_query("test")
        assert len(embedding) == service.dimension

    def test_empty_text_embedding(self, service):
        """Empty text should return a zero vector."""
        embedding = service.embed_query("")
        assert all(x == 0.0 for x in embedding)

    def test_similar_texts_have_high_similarity(self, service):
        """Semantically similar texts should have high cosine similarity."""
        emb1 = service.embed_query("machine learning artificial intelligence")
        emb2 = service.embed_query("AI and ML technologies")

        similarity = service.compute_similarity(emb1, emb2)
        assert similarity > 0.3  # Should be reasonably similar

    def test_different_texts_have_lower_similarity(self, service):
        """Semantically different texts should have lower similarity."""
        emb1 = service.embed_query("machine learning algorithms")
        emb2 = service.embed_query("chocolate cake recipe ingredients")

        similarity = service.compute_similarity(emb1, emb2)
        assert similarity < 0.5  # Should be less similar

    def test_compute_similarity_identical_vectors(self, service):
        """Identical vectors should have similarity of 1.0."""
        emb = service.embed_query("test text")
        similarity = service.compute_similarity(emb, emb)
        assert abs(similarity - 1.0) < 0.01

    def test_compute_similarity_zero_vector(self, service):
        """Zero vectors should have similarity of 0.0."""
        dim = service.dimension
        zero = [0.0] * dim
        similarity = service.compute_similarity(zero, zero)
        assert similarity == 0.0

    def test_model_loaded_after_use(self, service):
        """After embedding, the model should be marked as loaded."""
        service.embed_query("test")
        assert service.is_model_loaded() is True

    def test_empty_list_returns_empty(self, service):
        """Embedding an empty list should return an empty list."""
        result = service.embed_texts([])
        assert result == []
