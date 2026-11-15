"""Durable Vercel Queue delivery, with a cross-instance processing lock."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.database.database import engine, get_db_context
from app.database.models import Document, DocumentProcessingJob

TOPIC = "researchmind-documents"


@lru_cache
def lock_engine():
    # Session advisory locks must bypass transaction poolers such as PgBouncer.
    url = get_settings().database_url_unpooled
    if not url:
        if "-pooler" in (engine.url.host or ""):
            raise RuntimeError("DATABASE_URL_UNPOOLED is required for document processing locks")
        return engine
    if url.startswith(("postgres://", "postgresql://")):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    return create_engine(url, poolclass=NullPool, pool_pre_ping=True)


async def dispatch(document_id):
    from vercel.queue import send
    try:
        await send(TOPIC, {"document_id": document_id})
    except Exception:
        with get_db_context() as db:
            job = db.query(DocumentProcessingJob).filter_by(document_id=document_id).first()
            doc = db.get(Document, document_id)
            if job and job.status == "queued":
                job.status = job.stage = "error"
                job.error_message = "Could not schedule processing. Please retry this document."
                if doc:
                    doc.status, doc.error_message = "error", job.error_message
                db.commit()
        raise


@contextmanager
def document_lock(document_id):
    key = int.from_bytes(hashlib.sha256(document_id.encode()).digest()[:8], "big", signed=True)
    # A session lock is released by PostgreSQL even if Vercel kills a Function.
    with lock_engine().connect() as connection:
        acquired = connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}).scalar()
        connection.commit()
        if not acquired:
            raise RuntimeError("Document is already being processed")
        try:
            yield
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
            connection.commit()


def process_cloud_document(document_id, processor=None):
    with document_lock(document_id):
        with get_db_context() as db:
            doc = db.get(Document, document_id)
            job = db.query(DocumentProcessingJob).filter_by(document_id=document_id).first()
            # Duplicate delivery of a successful or deleted document is a no-op.
            if not doc or not job or doc.status == "ready":
                return
            job.status = "running"
            job.attempts += 1
            job.updated_at = datetime.now(timezone.utc)
            doc.status = "processing"
            inputs = dict(document_id=doc.id, file_path=doc.file_path,
                original_filename=doc.filename, file_type=doc.file_type, file_size=doc.file_size)
            db.commit()

        def stage(name):
            with get_db_context() as db:
                job = db.query(DocumentProcessingJob).filter_by(document_id=document_id).one()
                job.stage = name
                job.updated_at = datetime.now(timezone.utc)
                db.commit()

        try:
            if processor is None:
                from app.api.routes import get_document_processor
                processor = get_document_processor()
            processor.process_upload(**inputs, on_stage=stage)
        except Exception:
            finish(document_id, "error", "Document processing failed. Check the source and AI settings, then retry.")
            raise  # Queue delivery remains unacknowledged and can retry.
        finish(document_id, "ready", None)


def finish(document_id, status, error):
    with get_db_context() as db:
        job = db.query(DocumentProcessingJob).filter_by(document_id=document_id).first()
        doc = db.get(Document, document_id)
        if job and doc:
            job.status = job.stage = status
            job.error_message = doc.error_message = error
            job.updated_at = datetime.now(timezone.utc)
            doc.status = status
            db.commit()
