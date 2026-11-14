"""Retrieval service combining semantic vector search with optional
hybrid keyword search and reranking.

The retrieval pipeline supports three modes:
1. Pure vector search (default): cosine similarity in ChromaDB
2. Hybrid search: combines BM25 keyword search with vector search,
   weighted by configurable parameters
3. Reranking: re-orders retrieved chunks by cross-encoding similarity
   for improved precision (uses sentence-transformers CrossEncoder)
"""

import re
from typing import List, Dict, Optional, Any
from collections import defaultdict

from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore

logger = get_logger(__name__)


class RetrievalResult:
    """A single retrieval result with content, metadata, and scores."""

    def __init__(
        self,
        content: str,
        metadata: Dict[str, Any],
        similarity_score: float = 0.0,
        bm25_score: float = 0.0,
        rerank_score: float = 0.0,
        final_score: float = 0.0,
    ):
        self.content = content
        self.metadata = metadata
        self.similarity_score = similarity_score
        self.bm25_score = bm25_score
        self.rerank_score = rerank_score
        self.final_score = final_score

    @property
    def document_id(self) -> str:
        return self.metadata.get("document_id", "")

    @property
    def document_name(self) -> str:
        return self.metadata.get("document_name", "")

    @property
    def page_number(self) -> Optional[int]:
        return self.metadata.get("page_number")

    @property
    def chunk_index(self) -> int:
        return self.metadata.get("chunk_index", 0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "metadata": self.metadata,
            "similarity_score": self.similarity_score,
            "bm25_score": self.bm25_score,
            "rerank_score": self.rerank_score,
            "final_score": self.final_score,
        }


class RetrievalService:
    """High-level retrieval service combining vector search, hybrid
    search, and reranking.

    The service is initialized with shared instances of EmbeddingService
    and VectorStore to avoid reloading models.
    """

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        vector_store: Optional[VectorStore] = None,
    ) -> None:
        settings = get_settings()
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStore()
        self.enable_hybrid_search = settings.enable_hybrid_search
        self.enable_reranking = settings.enable_reranking
        self.bm25_weight = settings.bm25_weight
        self.vector_weight = settings.vector_weight
        self.similarity_threshold = settings.similarity_threshold
        self._reranker = None  # Lazy-loaded
        self._reranker_failed = False

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
        rerank: Optional[bool] = None,
    ) -> List[RetrievalResult]:
        """Retrieve relevant chunks for a query.

        Pipeline:
        1. Embed the query
        2. Vector search in ChromaDB (retrieve top_k * 3 for reranking headroom)
        3. Optionally add BM25 keyword scores (hybrid search)
        4. Combine and normalize scores
        5. Optionally rerank with cross-encoder
        6. Return top_k results above the similarity threshold

        Args:
            query: Natural language query.
            top_k: Number of final results to return.
            document_ids: Optional filter to specific documents.

        Returns:
            List of RetrievalResult objects, sorted by final score.
        """
        settings = get_settings()
        logger.info(
            f"Retrieving for query: '{query[:80]}...' "
            f"(top_k={top_k}, hybrid={self.enable_hybrid_search}, "
            f"rerank={self.enable_reranking})"
        )

        # Step 1: Embed the query
        query_embedding = self.embedding_service.embed_query(query)

        # Step 2: Vector search — retrieve more candidates for reranking
        use_reranking = self.enable_reranking if rerank is None else self.enable_reranking and rerank
        search_k = top_k * 3 if use_reranking else top_k
        vector_results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=search_k,
            document_ids=document_ids,
        )

        if not vector_results:
            logger.info("No results from vector search")
            return []

        # Convert to RetrievalResult objects
        results = [
            RetrievalResult(
                content=r["content"],
                metadata=r["metadata"],
                similarity_score=r["similarity_score"],
            )
            for r in vector_results
        ]

        # Step 3: Optional hybrid search with BM25
        if self.enable_hybrid_search:
            results = self._add_bm25_scores(query, results)
            results = self._combine_scores(results)
        else:
            # Use vector similarity score as final score
            for r in results:
                r.final_score = r.similarity_score

        # Step 4: Optional reranking with cross-encoder
        if use_reranking and len(results) > 1:
            results = self._rerank(query, results)

        # Step 5: Filter by similarity threshold and return top_k
        results = [
            r for r in results
            if r.final_score >= self.similarity_threshold
        ]
        results = results[:top_k]

        logger.info(
            f"Retrieval complete: {len(results)} results after "
            f"filtering (threshold={self.similarity_threshold})"
        )
        return results

    def _add_bm25_scores(
        self, query: str, results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """Add BM25-like keyword matching scores to results.

        Uses a simple BM25 approximation: term frequency × inverse document
        frequency, computed on the retrieved chunks.  This is lightweight
        and doesn't require an external library.
        """
        # Tokenize query
        query_terms = self._tokenize(query)
        if not query_terms:
            return results

        # Build a mini "corpus" from the retrieved chunks for IDF computation
        chunk_texts = [r.content for r in results]
        n_docs = len(chunk_texts)

        # Compute document frequency for each query term
        df = defaultdict(int)
        for term in query_terms:
            for text in chunk_texts:
                if term in text.lower():
                    df[term] += 1

        # Compute BM25 scores
        k1 = 1.5  # BM25 term frequency saturation parameter
        b = 0.75  # BM25 length normalization parameter

        for idx, result in enumerate(results):
            text = result.content.lower()
            doc_len = len(text.split())
            avg_len = sum(len(t.split()) for t in chunk_texts) / n_docs if n_docs > 0 else 0

            score = 0.0
            for term in query_terms:
                # Term frequency in this document
                tf = text.count(term)

                if tf == 0 or df[term] == 0:
                    continue

                # IDF: log(N / df)
                idf = max(0, (n_docs - df[term] + 0.5) / (df[term] + 0.5))

                # BM25 term score
                norm = 1 - b + b * (doc_len / avg_len) if avg_len > 0 else 1
                score += idf * (tf * (k1 + 1)) / (tf + k1 * norm)

            result.bm25_score = float(score)

        logger.info(f"BM25 scores computed for {len(results)} results")
        return results

    def _combine_scores(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Combine vector similarity and BM25 scores into a final score.

        Scores are min-max normalized before combining to ensure they're
        on the same scale.
        """
        if not results:
            return results

        # Normalize vector scores
        vec_scores = [r.similarity_score for r in results]
        vec_min, vec_max = min(vec_scores), max(vec_scores)
        vec_range = vec_max - vec_min if vec_max > vec_min else 1.0

        # Normalize BM25 scores
        bm25_scores = [r.bm25_score for r in results]
        bm25_min, bm25_max = min(bm25_scores), max(bm25_scores)
        bm25_range = bm25_max - bm25_min if bm25_max > bm25_min else 1.0

        for r in results:
            norm_vec = (r.similarity_score - vec_min) / vec_range if vec_max > vec_min else r.similarity_score
            norm_bm25 = (r.bm25_score - bm25_min) / bm25_range if bm25_range > 0 else 0.0
            r.final_score = self.vector_weight * norm_vec + self.bm25_weight * norm_bm25

        # Sort by final score (descending)
        results.sort(key=lambda x: x.final_score, reverse=True)
        return results

    def _rerank(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Rerank results using a cross-encoder for higher precision.

        Uses sentence-transformers' CrossEncoder which jointly encodes the
        query and each chunk, producing a more accurate relevance score
        than independent embeddings.  This is more expensive but gives
        better top-k precision.
        """
        try:
            reranker = self._get_reranker()
            if reranker is None:
                return results

            # Prepare query-document pairs
            pairs = [(query, r.content[:512]) for r in results]

            # Get cross-encoder scores
            scores = reranker.predict(pairs)

            # Normalize cross-encoder scores to 0-1 range using sigmoid.
            # Cross-encoders output raw logits that can be negative,
            # so we apply sigmoid: 1 / (1 + exp(-x)) to bound to [0, 1].
            import math
            normalized_scores = [1.0 / (1.0 + math.exp(-float(s))) for s in scores]

            # Update rerank scores and blend with existing final score
            for idx, result in enumerate(results):
                result.rerank_score = normalized_scores[idx]
                # Blend: 60% existing retrieval score + 40% reranker score
                result.final_score = 0.6 * result.final_score + 0.4 * result.rerank_score

            # Sort by updated final score
            results.sort(key=lambda x: x.final_score, reverse=True)

            logger.info(f"Reranked {len(results)} results with cross-encoder")
            return results

        except Exception as exc:
            logger.warning(f"Reranking failed, keeping original order: {exc}")
            return results

    def _get_reranker(self):
        """Lazy-load the cross-encoder reranker model."""
        if self._reranker_failed:
            return None
        if self._reranker is None:
            try:
                from sentence_transformers import CrossEncoder
                logger.info("Loading cross-encoder reranker: cross-encoder/ms-marco-MiniLM-L-6-v2")
                self._reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", local_files_only=True)
            except ImportError:
                logger.warning("sentence-transformers not available, skipping reranking")
                self._reranker_failed = True
                return None
            except Exception as exc:
                logger.warning(f"Failed to load reranker model: {exc}")
                self._reranker_failed = True
                return None
        return self._reranker

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Simple tokenizer: lowercase, split on non-alphanumeric, filter short tokens."""
        tokens = re.findall(r"\b\w+\b", text.lower())
        # Filter out very short tokens and common stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "in", "on", "at", "to", "for", "of", "with", "by", "from",
            "as", "about", "into", "through", "during", "and", "or",
            "not", "no", "but", "if", "then", "else", "when", "this",
            "that", "these", "those", "it", "its", "i", "you", "he",
            "she", "we", "they", "what", "which", "who", "whom", "how",
        }
        return [t for t in tokens if len(t) > 2 and t not in stop_words]
