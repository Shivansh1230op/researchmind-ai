"""Embedding generation service using Sentence Transformers.

Uses a local Sentence Transformers model (all-MiniLM-L6-v2 by default)
so embeddings work offline and don't consume OpenAI API quota.
Falls back gracefully if the model isn't downloaded yet — it will be
downloaded automatically on first use.
"""

from typing import List, Optional
import threading
import time
import numpy as np

from app.core.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Generate vector embeddings for text using Sentence Transformers.

    The model is loaded lazily (on first call) so the service can be
    instantiated quickly and the model only loads when needed.
    """

    _models = {}
    _load_lock = threading.Lock()

    def __init__(self, model_name: Optional[str] = None) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model_name
        self.batch_size = settings.embedding_batch_size
        self._model = None  # Lazy-loaded
        self._dimension: Optional[int] = None

    @property
    def model(self):
        """Lazy-load the Sentence Transformers model on first access."""
        if self._model is None:
            with self._load_lock:
                if self.model_name not in self._models:
                    from sentence_transformers import SentenceTransformer
                    import torch
                    torch.set_num_threads(get_settings().embedding_cpu_threads)
                    started = time.perf_counter()
                    try:
                        # A warm cache must not wait for remote HEAD requests/retries.
                        model = SentenceTransformer(self.model_name, local_files_only=True)
                    except OSError:
                        logger.info("Embedding weights not cached; downloading once: %s", self.model_name)
                        model = SentenceTransformer(self.model_name)
                    self._models[self.model_name] = model
                    logger.info("Embedding model ready in %.2fs", time.perf_counter() - started)
                self._model = self._models[self.model_name]
                self._dimension = self._model.get_sentence_embedding_dimension()
        return self._model

    @property
    def dimension(self) -> int:
        """Return the embedding dimension (loads model if not loaded)."""
        if self._dimension is None:
            _ = self.model  # Trigger lazy load
        return self._dimension  # type: ignore

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of text strings.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (each a list of floats).
        """
        if not texts:
            return []

        # Filter out empty strings (replace with single space)
        clean_texts = [t if t.strip() else " " for t in texts]

        logger.info(f"Generating embeddings for {len(clean_texts)} texts")

        try:
            embeddings = self.model.encode(
                clean_texts,
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,  # L2-normalize for cosine similarity
            )
            # Convert numpy array to list of lists
            return embeddings.tolist()
        except Exception as exc:
            logger.error(f"Failed to generate embeddings: {exc}")
            raise

    def embed_query(self, text: str) -> List[float]:
        """Generate an embedding for a single query string.

        Args:
            text: The query text to embed.

        Returns:
            Embedding vector as a list of floats.
        """
        if not text or not text.strip():
            # Return zero vector for empty queries
            dim = self.dimension
            return [0.0] * dim

        embeddings = self.embed_texts([text])
        return embeddings[0] if embeddings else [0.0] * self.dimension

    def compute_similarity(
        self, embedding1: List[float], embedding2: List[float]
    ) -> float:
        """Compute cosine similarity between two embeddings.

        Since embeddings are L2-normalized during encoding, cosine
        similarity is just the dot product.

        Args:
            embedding1: First embedding vector.
            embedding2: Second embedding vector.

        Returns:
            Cosine similarity score (-1 to 1).
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        # Normalize in case they weren't pre-normalized
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def is_model_loaded(self) -> bool:
        """Check whether the embedding model has been loaded into memory."""
        return self._model is not None
