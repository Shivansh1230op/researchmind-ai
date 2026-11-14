"""Document processing service — orchestrates the full upload pipeline.

When a document is uploaded, this service:
1. Validates the file (type, size)
2. Saves the file to disk
3. Creates a Document record in the database
4. Extracts text (with page-level metadata)
5. Splits text into chunks (preserving page numbers)
6. Generates embeddings for all chunks
7. Stores chunks + embeddings + metadata in ChromaDB
8. Updates the Document status to "ready"

This keeps the upload route handler thin — it delegates all the heavy
work to this service.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Optional

from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.database.database import get_db_context
from app.database.models import Document, DocumentAccess, DocumentProcessingJob
from app.services.document_loader import DocumentLoader
from app.services.text_splitter import TextSplitter
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore

logger = get_logger(__name__)


class DocumentProcessor:
    """Orchestrates the full document processing pipeline.

    Holds shared service instances to avoid re-initialization on each
    upload.  Thread-safe for concurrent uploads since ChromaDB and
    the embedding model handle their own concurrency.
    """

    def __init__(self) -> None:
        self.loader = DocumentLoader()
        self.splitter = TextSplitter()
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore()

    def process_upload(
        self,
        file_path: str,
        original_filename: str,
        file_type: str,
        file_size: int,
        on_created=None,
        document_id: Optional[str] = None,
        on_stage=None,
    ) -> Dict:
        """Process an uploaded file through the full pipeline.

        Args:
            file_path: Path where the file is saved on disk.
            original_filename: Original name of the uploaded file.
            file_type: File extension without dot (e.g. "pdf").
            file_size: Size of the file in bytes.

        Returns:
            Dict with document metadata including the generated document_id.

        Raises:
            ValueError: If validation or processing fails.
        """
        logger.info(
            f"Processing upload: {original_filename} "
            f"(type={file_type}, size={file_size} bytes)"
        )

        # Validate file
        valid, error_msg = self.loader.validate_file(original_filename, file_size)
        if not valid:
            raise ValueError(error_msg)

        # Create database record
        doc_id = document_id or self._create_document_record(
            original_filename, file_path, file_type, file_size
        )
        if on_created:
            on_created(doc_id)

        try:
            # Step 1: Extract text with page-level metadata
            if on_stage:
                on_stage("extracting")
            pages, doc_metadata = self.loader.load_document(file_path, file_type)

            # Update document record with metadata
            self._update_document(
                doc_id,
                total_pages=int(doc_metadata.get("num_pages", len(pages))),
                extra_metadata=doc_metadata,
            )

            # Step 2: Split text into chunks
            if on_stage:
                on_stage("chunking")
            chunks = self.splitter.split_pages(
                pages=pages,
                document_name=original_filename,
                document_id=doc_id,
            )

            if not chunks:
                raise ValueError("No text content could be extracted from the document")

            # Step 3: Generate embeddings
            if on_stage:
                on_stage("embedding")
            chunk_texts = [c.content for c in chunks]
            embeddings = self.embedding_service.embed_texts(chunk_texts)

            # Step 4: Store in ChromaDB
            if on_stage:
                on_stage("indexing")
            if document_id:
                self.vector_store.delete_document(doc_id)
            added = self.vector_store.add_chunks(
                chunks=chunks,
                embeddings=embeddings,
                document_id=doc_id,
            )

            # Step 5: Update document status to ready
            self._update_document(
                doc_id,
                total_chunks=added,
                status="ready",
                error_message=None,
            )

            logger.info(
                f"Document processed successfully: {original_filename} "
                f"(id={doc_id}, pages={len(pages)}, chunks={added})"
            )

            # Return document metadata
            with get_db_context() as db:
                doc = db.query(Document).filter_by(id=doc_id).first()
                return {
                    "id": doc.id,
                    "filename": doc.filename,
                    "file_type": doc.file_type,
                    "file_size": doc.file_size,
                    "total_pages": doc.total_pages,
                    "total_chunks": doc.total_chunks,
                    "status": doc.status,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "extra_metadata": doc.metadata_json,
                }

        except Exception as exc:
            # Mark document as error
            logger.error(f"Document processing failed: {exc}")
            self._update_document(
                doc_id,
                status="error",
                error_message="Processing failed. Check source content and model configuration, then retry.",
            )
            raise

    def _create_document_record(
        self,
        filename: str,
        file_path: str,
        file_type: str,
        file_size: int,
    ) -> str:
        """Create a new Document record in the database.

        Returns:
            The generated document ID.
        """
        with get_db_context() as db:
            doc = Document(
                filename=filename,
                file_path=file_path,
                file_type=file_type,
                file_size=file_size,
                status="processing",
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            return doc.id

    def _update_document(
        self,
        doc_id: str,
        **kwargs,
    ) -> None:
        """Update fields on an existing Document record."""
        with get_db_context() as db:
            doc = db.query(Document).filter_by(id=doc_id).first()
            if doc:
                for key, value in kwargs.items():
                    if key == "extra_metadata":
                        doc.metadata_json = value
                    elif hasattr(doc, key):
                        setattr(doc, key, value)
                db.commit()

    def delete_document(self, document_id: str) -> bool:
        """Delete a document: remove from ChromaDB, DB, and disk.

        Args:
            document_id: ID of the document to delete.

        Returns:
            True if deletion succeeded, False if document not found.
        """
        logger.info(f"Deleting document: {document_id}")

        with get_db_context() as db:
            doc = db.query(Document).filter_by(id=document_id).first()
            if not doc:
                logger.warning(f"Document not found: {document_id}")
                return False

            filename = doc.filename
            file_path = doc.file_path

            # Delete from ChromaDB (removes all chunks)
            deleted_chunks = self.vector_store.delete_document(document_id)
            logger.info(f"Deleted {deleted_chunks} chunks from vector store")

            # Delete file from disk
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Deleted file from disk: {file_path}")
                except Exception as exc:
                    logger.warning(f"Failed to delete file from disk: {exc}")

            # Delete from database
            db.query(DocumentProcessingJob).filter_by(document_id=document_id).delete()
            db.query(DocumentAccess).filter_by(document_id=document_id).delete()
            db.delete(doc)
            db.commit()

        logger.info(f"Document deleted successfully: {filename} (id={document_id})")
        return True

    def get_document_content_preview(
        self, document_id: str, max_chars: int = 2000
    ) -> Optional[str]:
        """Get a preview of the document's text content.

        Returns the first few chunks concatenated, useful for the
        document preview panel in the UI.
        """
        try:
            results = self.vector_store.collection.get(
                where={"document_id": document_id},
                include=["documents", "metadatas"],
            )

            if not results or not results.get("ids"):
                return None

            documents = results.get("documents", [])
            metadatas = results.get("metadatas", [])

            # Sort by chunk_index and take first few
            indexed = []
            for doc, meta in zip(documents, metadatas):
                chunk_idx = meta.get("chunk_index", 0) if meta else 0
                indexed.append((chunk_idx, doc))

            indexed.sort(key=lambda x: x[0])

            preview = "\n\n".join(doc for _, doc in indexed[:3] if doc)
            if len(preview) > max_chars:
                preview = preview[:max_chars] + "..."

            return preview
        except Exception as exc:
            logger.error(f"Failed to get document preview: {exc}")
            return None
