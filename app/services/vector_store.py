"""ChromaDB vector store service.

Manages the lifecycle of vector embeddings in ChromaDB:
- Adding chunks with their embeddings and metadata
- Semantic similarity search
- Metadata filtering (by document_id, file type, etc.)
- Deleting all vectors for a specific document
- Collection management

ChromaDB is an embedded database (no separate server needed) that
persists data to disk.  This makes it perfect for development and
small-to-medium production workloads.
"""

from typing import List, Dict, Optional, Any
import uuid

from app.core.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class VectorStore:
    """ChromaDB-backed vector store for document embeddings.

    The store maintains a single ChromaDB collection.  Each document
    chunk is stored with:
    - A unique ID
    - The embedding vector
    - The chunk text (as the "document")
    - Metadata: document_id, document_name, page_number, chunk_index
    """

    def __init__(self, collection_name: Optional[str] = None) -> None:
        settings = get_settings()
        self.persist_dir = settings.chroma_persist_dir
        self.collection_name = collection_name or settings.chroma_collection_name
        self._client = None
        self._collection = None

    @property
    def client(self):
        """Lazy-initialize the ChromaDB persistent client."""
        if self._client is None:
            import chromadb
            logger.info(f"Initializing ChromaDB at: {self.persist_dir}")
            self._client = chromadb.PersistentClient(path=self.persist_dir)
        return self._client

    @property
    def collection(self):
        """Get or create the ChromaDB collection."""
        if self._collection is None:
            logger.info(f"Getting/creating collection: {self.collection_name}")
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                f"Collection '{self.collection_name}' ready, "
                f"current count: {self._collection.count()}"
            )
        return self._collection

    def add_chunks(
        self,
        chunks: List[Any],  # List of TextChunk objects
        embeddings: List[List[float]],
        document_id: str,
    ) -> int:
        """Add document chunks with their embeddings to the vector store.

        Args:
            chunks: List of TextChunk objects from the text splitter.
            embeddings: Corresponding embedding vectors (same order).
            document_id: ID of the parent document.

        Returns:
            Number of chunks successfully added.
        """
        if not chunks or not embeddings:
            logger.warning("No chunks or embeddings to add")
            return 0

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Mismatch: {len(chunks)} chunks but {len(embeddings)} embeddings"
            )

        # Prepare data for ChromaDB batch insert
        ids = []
        documents = []
        metadatas = []

        for chunk, embedding in zip(chunks, embeddings):
            chunk_id = str(uuid.uuid4())
            ids.append(chunk_id)
            documents.append(chunk.content)
            metadatas.append({
                "document_id": document_id,
                "document_name": chunk.document_name,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
            })

        # Add in batches to avoid memory issues with large documents
        batch_size = 500
        added = 0

        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i + batch_size]
            batch_docs = documents[i:i + batch_size]
            batch_embeddings = embeddings[i:i + batch_size]
            batch_metadatas = metadatas[i:i + batch_size]

            self.collection.add(
                ids=batch_ids,
                documents=batch_docs,
                embeddings=batch_embeddings,
                metadatas=batch_metadatas,
            )
            added += len(batch_ids)

        logger.info(
            f"Added {added} chunks for document_id={document_id} "
            f"to collection '{self.collection_name}'"
        )
        return added

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Perform semantic similarity search.

        Args:
            query_embedding: Embedding of the search query.
            top_k: Number of results to return.
            document_ids: Optional filter — only return chunks from these documents.

        Returns:
            List of result dicts with keys: id, document, metadata, distance.
        """
        # Build the where filter if document_ids are specified
        where_filter = None
        if document_ids:
            if len(document_ids) == 1:
                where_filter = {"document_id": document_ids[0]}
            else:
                where_filter = {"document_id": {"$in": document_ids}}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        # Flatten the results (ChromaDB returns lists of lists)
        search_results = []
        if results and results.get("ids"):
            ids = results["ids"][0] if results["ids"] else []
            documents = results["documents"][0] if results["documents"] else []
            metadatas = results["metadatas"][0] if results["metadatas"] else []
            distances = results["distances"][0] if results["distances"] else []

            for idx in range(len(ids)):
                # ChromaDB returns cosine distance; convert to similarity score
                distance = distances[idx] if idx < len(distances) else 1.0
                similarity = 1.0 - distance  # cosine distance → similarity

                search_results.append({
                    "id": ids[idx],
                    "content": documents[idx] if idx < len(documents) else "",
                    "metadata": metadatas[idx] if idx < len(metadatas) else {},
                    "similarity_score": max(0.0, min(1.0, similarity)),
                    "distance": distance,
                })

        logger.info(
            f"Vector search returned {len(search_results)} results "
            f"(top_k={top_k}, filter={'yes' if where_filter else 'no'})"
        )
        return search_results

    def delete_document(self, document_id: str) -> int:
        """Delete all chunks associated with a document.

        Args:
            document_id: The ID of the document whose chunks should be deleted.

        Returns:
            Number of chunks deleted (best-effort count).
        """
        try:
            # First count how many chunks belong to this document
            count_before = self.collection.count()
            self.collection.delete(where={"document_id": document_id})
            count_after = self.collection.count()
            deleted = count_before - count_after
            logger.info(
                f"Deleted {deleted} chunks for document_id={document_id}"
            )
            return deleted
        except Exception as exc:
            logger.error(f"Failed to delete chunks for document_id={document_id}: {exc}")
            return 0

    def get_document_chunk_count(self, document_id: str) -> int:
        """Count how many chunks belong to a specific document."""
        try:
            results = self.collection.get(where={"document_id": document_id})
            return len(results["ids"]) if results and "ids" in results else 0
        except Exception as exc:
            logger.error(f"Failed to count chunks for document_id={document_id}: {exc}")
            return 0

    def get_all_documents(self) -> List[str]:
        """Return a list of unique document_ids in the store."""
        try:
            results = self.collection.get(include=["metadatas"])
            doc_ids = set()
            if results and results.get("metadatas"):
                for meta in results["metadatas"]:
                    if meta and "document_id" in meta:
                        doc_ids.add(meta["document_id"])
            return list(doc_ids)
        except Exception as exc:
            logger.error(f"Failed to get document list from vector store: {exc}")
            return []

    def get_collection_stats(self) -> Dict[str, int]:
        """Return basic statistics about the collection."""
        try:
            return {
                "total_chunks": self.collection.count(),
                "unique_documents": len(self.get_all_documents()),
            }
        except Exception as exc:
            logger.error(f"Failed to get collection stats: {exc}")
            return {"total_chunks": 0, "unique_documents": 0}

    def reset(self) -> None:
        """Delete the entire collection and recreate it (for testing/dev)."""
        try:
            self.client.delete_collection(self.collection_name)
            self._collection = None  # Force re-creation
            _ = self.collection  # Recreate
            logger.info(f"Collection '{self.collection_name}' reset")
        except Exception as exc:
            logger.error(f"Failed to reset collection: {exc}")
