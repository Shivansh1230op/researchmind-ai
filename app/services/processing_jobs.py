"""Persistent ingestion queue for a single API process.

The database owns job state; a local worker performs one job at a time. On
process restart interrupted jobs are requeued and their index is replaced
idempotently. Multi-process deployments should use a dedicated queue instead.
"""
import threading
from datetime import datetime, timezone

from app.database.database import get_db_context
from app.database.models import Document, DocumentProcessingJob
from app.core.logging_config import get_logger

logger = get_logger(__name__)
_run_lock = threading.Lock()


def enqueue(db, document_id: str):
    job = db.query(DocumentProcessingJob).filter_by(document_id=document_id).first()
    if job and job.status in {"queued", "running"}:
        raise ValueError("Document already has an active processing job.")
    if job is None:
        job = DocumentProcessingJob(document_id=document_id)
        db.add(job)
    job.status = "queued"
    job.stage = "queued"
    job.error_message = None
    job.updated_at = datetime.now(timezone.utc)
    document = db.get(Document, document_id)
    document.status = "queued"
    document.error_message = None
    return job


def recover_interrupted():
    """Run once before starting the sole local worker, never concurrently."""
    with get_db_context() as db:
        jobs = db.query(DocumentProcessingJob).filter_by(status="running").all()
        for job in jobs:
            job.status = "queued"
            job.stage = "queued"
            job.updated_at = datetime.now(timezone.utc)
            document = db.get(Document, job.document_id)
            if document:
                document.status = "queued"
        db.commit()


def run_next(processor=None) -> bool:
    if not _run_lock.acquire(blocking=False):
        return False
    try:
        with get_db_context() as db:
            job = db.query(DocumentProcessingJob).filter_by(status="queued").order_by(DocumentProcessingJob.created_at).first()
            if not job:
                return False
            job_id, document_id = job.id, job.document_id
            claimed = db.query(DocumentProcessingJob).filter_by(id=job_id, status="queued").update(
                {"status": "running", "attempts": DocumentProcessingJob.attempts + 1,
                 "updated_at": datetime.now(timezone.utc)})
            db.commit()
            if not claimed:
                return False
            document = db.get(Document, document_id)
            if not document:
                db.query(DocumentProcessingJob).filter_by(id=job_id).delete()
                db.commit()
                return True
            inputs = dict(document_id=document.id, file_path=document.file_path,
                original_filename=document.filename, file_type=document.file_type, file_size=document.file_size)

        def stage(name):
            with get_db_context() as db:
                row = db.get(DocumentProcessingJob, job_id)
                row.stage = name
                row.updated_at = datetime.now(timezone.utc)
                doc = db.get(Document, document_id)
                doc.status = "processing"
                db.commit()

        try:
            if processor is None:
                from app.api.routes import get_document_processor
                processor = get_document_processor()
            processor.process_upload(**inputs, on_stage=stage)
            status, error = "ready", None
        except Exception:
            logger.exception("Background document job failed: %s", job_id)
            status = "error"
            error = "Processing failed. Check source content and embedding model configuration, then retry."
        with get_db_context() as db:
            row = db.get(DocumentProcessingJob, job_id)
            row.status = status
            row.stage = status
            row.error_message = error
            row.updated_at = datetime.now(timezone.utc)
            doc = db.get(Document, document_id)
            doc.status = status
            doc.error_message = error
            db.commit()
        return True
    finally:
        _run_lock.release()


class ProcessingWorker:
    def __init__(self):
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name="document-processing", daemon=True)

    def start(self):
        recover_interrupted()
        self.thread.start()

    def run(self):
        from app.core.config import get_settings
        if get_settings().preload_embeddings:
            try:
                from app.api.routes import get_document_processor
                # Warm once while the user opens the app, rather than on upload.
                _ = get_document_processor().embedding_service.model
            except Exception:
                logger.exception("Embedding warmup failed; uploads will report model errors normally")
        while not self.stop_event.is_set():
            try:
                if run_next():
                    continue
            except Exception:
                logger.exception("Processing queue iteration failed")
            self.stop_event.wait(1)

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=5)
