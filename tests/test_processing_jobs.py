"""Queue persistence, stage events, retry, and ownership without external models."""
import uuid
from unittest.mock import patch

from app.database.database import get_db_context
from app.database.models import Document, DocumentProcessingJob
from app.services.document_processor import DocumentProcessor
from app.services.processing_jobs import enqueue, recover_interrupted, run_next
from app.services.vector_store import VectorStore


def queued_document(tmp_path):
    path = tmp_path / "paper.md"
    path.write_text("# Findings\nThe controlled study measured 42 observations.", encoding="utf-8")
    with get_db_context() as db:
        document = Document(filename="paper.md", file_path=str(path), file_type="md", file_size=path.stat().st_size)
        db.add(document); db.flush(); enqueue(db, document.id); db.commit()
        return document.id


def test_queue_runs_actual_stages_and_preserves_document_id(tmp_path):
    document_id = queued_document(tmp_path)
    processor = DocumentProcessor()
    store = VectorStore(collection_name=f"jobs_{uuid.uuid4().hex[:12]}")
    processor.vector_store = store
    stages = []
    original_load = processor.loader.load_document
    original_split = processor.splitter.split_pages
    original_add = store.add_chunks

    def check_stage(expected):
        with get_db_context() as db:
            job = db.query(DocumentProcessingJob).filter_by(document_id=document_id).first()
            assert job.stage == expected
            stages.append(expected)

    def load(*args, **kwargs):
        check_stage("extracting"); return original_load(*args, **kwargs)

    def split(*args, **kwargs):
        check_stage("chunking"); return original_split(*args, **kwargs)

    def embed(texts):
        check_stage("embedding"); return [[1.0, 0.0, 0.0] for _ in texts]

    def add(*args, **kwargs):
        check_stage("indexing"); return original_add(*args, **kwargs)

    try:
        with patch.object(processor.loader, "load_document", side_effect=load), \
             patch.object(processor.splitter, "split_pages", side_effect=split), \
             patch.object(processor.embedding_service, "embed_texts", side_effect=embed), \
             patch.object(store, "add_chunks", side_effect=add):
            assert run_next(processor)
        assert stages == ["extracting", "chunking", "embedding", "indexing"]
        with get_db_context() as db:
            job = db.query(DocumentProcessingJob).filter_by(document_id=document_id).first()
            assert job.status == "ready" and job.attempts == 1
            assert db.get(Document, document_id).status == "ready"
            assert db.get(Document, document_id).metadata_json["num_pages"]
    finally:
        store.reset()


def test_failed_job_can_retry_and_recover_after_restart(tmp_path):
    document_id = queued_document(tmp_path)
    processor = DocumentProcessor()
    with patch.object(processor, "process_upload", side_effect=RuntimeError("private provider details")):
        assert run_next(processor)
    with get_db_context() as db:
        job = db.query(DocumentProcessingJob).filter_by(document_id=document_id).first()
        assert job.status == "error"
        assert "private provider details" not in job.error_message
        enqueue(db, document_id); db.commit()
        job.status = "running"; job.stage = "embedding"; db.commit()
    recover_interrupted()
    with get_db_context() as db:
        job = db.query(DocumentProcessingJob).filter_by(document_id=document_id).first()
        assert job.status == job.stage == "queued"
        assert db.get(Document, document_id).status == "queued"
        # Remove this test job so later tests do not accidentally process it.
        job.status = "error"; db.commit()
