"""Cloud persistence, upload authorization and retry behavior without paid calls."""
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.database.database import get_db_context
from app.database.models import Document, DocumentProcessingJob, UploadTicket, StoredChunk, DocumentAccess
from app.main import app
from app.services.document_processor import DocumentProcessor
from app.services.postgres_vectors import PostgresCollection
from app.services.vector_store import VectorStore
from tests.signup_helpers import register_verified


@pytest.fixture
def cloud_settings(monkeypatch):
    settings = get_settings()
    with get_db_context() as db:
        original_ids = {row.id for row in db.query(Document).all()}
    for key, value in {"auth_required": True, "storage_backend": "vercel_blob",
            "vector_backend": "postgres", "processing_backend": "vercel_queue",
            "allowed_file_types": "pdf,docx,txt,md"}.items():
        monkeypatch.setattr(settings, key, value)
    try:
        yield settings
    finally:
        # Mocked queue submissions must not leak into the local worker tests.
        with get_db_context() as db:
            new_ids = [row.id for row in db.query(Document).all() if row.id not in original_ids]
            if new_ids:
                db.query(StoredChunk).filter(StoredChunk.document_id.in_(new_ids)).delete(synchronize_session=False)
                db.query(DocumentProcessingJob).filter(DocumentProcessingJob.document_id.in_(new_ids)).delete(synchronize_session=False)
                db.query(DocumentAccess).filter(DocumentAccess.document_id.in_(new_ids)).delete(synchronize_session=False)
                db.query(UploadTicket).filter(UploadTicket.document_id.in_(new_ids)).delete(synchronize_session=False)
                db.query(Document).filter(Document.id.in_(new_ids)).delete(synchronize_session=False)
                db.commit()


def signup(client):
    response = register_verified(client, {"email": f"{uuid.uuid4().hex}@example.com",
        "password": "a sufficiently long testing password", "name": "Cloud tester"})
    assert response.status_code == 201, response.text
    return client.get("/workspaces").json()[0]["id"]


def test_private_upload_ownership_finalization_and_queue(cloud_settings):
    with TestClient(app) as owner, TestClient(app) as stranger:
        workspace = signup(owner)
        signup(stranger)
        headers = {"X-Workspace-Id": workspace}
        reserved = owner.post("/documents/uploads", headers=headers,
            json={"filename": "evidence.md", "file_size": 20})
        assert reserved.status_code == 201, reserved.text
        ticket = reserved.json()
        body = {"ticket_id": ticket["id"], "pathname": ticket["pathname"]}
        assert stranger.post("/storage/upload-authorizations", json=body).status_code == 404
        assert owner.post("/storage/upload-authorizations", headers=headers,
            json={**body, "pathname": "sources/another.pdf"}).status_code == 403
        assert owner.post("/storage/upload-authorizations", headers=headers, json=body).status_code == 200
        fake_blob = Mock()
        fake_blob.head_blob.return_value = SimpleNamespace(size=20)
        with patch("app.api.cloud_uploads.blob_client", return_value=fake_blob), \
                patch("app.services.cloud_jobs.dispatch", new_callable=AsyncMock) as dispatch:
            completed = owner.post(f"/documents/uploads/{ticket['id']}/complete", headers=headers)
            assert completed.status_code == 202, completed.text
            assert completed.json()["status"] == "queued"
            document_id = completed.json()["id"]
            # Finalizing again creates neither a second document nor a second job.
            assert owner.post(f"/documents/uploads/{ticket['id']}/complete", headers=headers).status_code == 202
            dispatch.assert_awaited_once_with(document_id)
        assert stranger.get(f"/documents/{document_id}/file").status_code == 404
        assert owner.post("/storage/upload-authorizations", headers=headers, json=body).status_code == 403
        with get_db_context() as db:
            assert db.get(Document, document_id).file_path == "blob:" + ticket["pathname"]
            assert db.query(DocumentProcessingJob).filter_by(document_id=document_id).count() == 1


def test_expired_and_mismatched_uploads(cloud_settings):
    with TestClient(app) as client:
        signup(client)
        ticket = client.post("/documents/uploads", json={"filename": "a.pdf", "file_size": 30}).json()
        with patch("app.api.cloud_uploads.blob_client") as storage:
            storage.return_value.head_blob.return_value = SimpleNamespace(size=31)
            assert client.post(f"/documents/uploads/{ticket['id']}/complete").status_code == 400
        with get_db_context() as db:
            db.get(UploadTicket, ticket["id"]).expires_at = datetime.utcnow() - timedelta(seconds=1)
            db.commit()
        assert client.post("/storage/upload-authorizations", json={"ticket_id": ticket["id"], "pathname": ticket["pathname"]}).status_code == 410
        assert client.post("/documents/uploads", json={"filename": "evil.exe", "file_size": 2}).status_code == 400
        assert client.post("/documents/uploads", json={"filename": "huge.pdf", "file_size": 60 * 1024**2}).status_code == 413


def test_durable_vectors_filter_documents_and_survive_new_instances(cloud_settings):
    collection = "test_cloud_" + uuid.uuid4().hex
    with get_db_context() as db:
        docs = [Document(filename=f"{i}.md", file_path="blob:sources/test.md", file_type="md", file_size=1) for i in range(2)]
        db.add_all(docs)
        db.commit()
        ids = [doc.id for doc in docs]
    store = PostgresCollection(collection)
    store.add(ids=["a", "b"], documents=["owned result", "other user's result"],
        embeddings=[[1., 0.], [1., 0.]], metadatas=[{"document_id": id, "document_name": "paper.md", "chunk_index": 0} for id in ids])
    # A new instance uses the database, not a previous Function's local state.
    fresh = PostgresCollection(collection)
    results = fresh.query([[1., 0.]], where={"document_id": {"$in": [ids[0]]}})
    assert results["documents"] == [["owned result"]]
    assert fresh.query([[1., 0.]], where={"document_id": {"$in": []}})["ids"] == [[]]
    fresh.update(ids=["a"], metadatas=[{"document_id": ids[0], "document_name": "renamed.md"}])
    assert store.get(ids=["a"])["metadatas"][0]["document_name"] == "renamed.md"
    fresh.delete(where={"document_id": ids[0]})
    assert fresh.count() == 1
    fresh.delete()


def test_cloud_processing_retries_and_acknowledges_duplicates(cloud_settings, tmp_path):
    from app.services import cloud_jobs
    from app.services.processing_jobs import enqueue
    path = tmp_path / "paper.md"
    path.write_text("A study found forty two observations.")
    with get_db_context() as db:
        doc = Document(filename=path.name, file_path=str(path), file_type="md", file_size=path.stat().st_size)
        db.add(doc)
        db.flush()
        enqueue(db, doc.id)
        db.commit()
        id = doc.id

    @contextmanager
    def lock(_):
        yield

    processor = DocumentProcessor()
    processor.vector_store = VectorStore("retry_" + uuid.uuid4().hex)
    with patch.object(cloud_jobs, "document_lock", lock), \
            patch.object(processor.embedding_service, "embed_texts", side_effect=RuntimeError("private provider response")):
        with pytest.raises(RuntimeError):
            cloud_jobs.process_cloud_document(id, processor)
    with get_db_context() as db:
        assert db.get(Document, id).status == "error"
        assert "private" not in db.get(Document, id).error_message
    with patch.object(cloud_jobs, "document_lock", lock), \
            patch.object(processor.embedding_service, "embed_texts", return_value=[[1., 0., 0.]]) as embed:
        cloud_jobs.process_cloud_document(id, processor)
        cloud_jobs.process_cloud_document(id, processor)
        embed.assert_called_once()
    with get_db_context() as db:
        assert db.get(Document, id).status == "ready"
        assert db.query(DocumentProcessingJob).filter_by(document_id=id).one().attempts == 2
    processor.vector_store.reset()


def test_cloud_download_is_private_and_temporary_copy_is_removed(cloud_settings):
    from app.services.source_storage import local_source
    @contextmanager
    def download(*args, **kwargs):
        assert kwargs == {"access": "private"}
        yield iter([b"# Synthetic document"])
    with patch("app.services.source_storage.blob_client") as storage:
        storage.return_value.stream_blob.side_effect = download
        with local_source("blob:sources/test.md", "md") as path:
            from pathlib import Path
            local = Path(path)
            assert local.read_bytes() == b"# Synthetic document"
        assert not local.exists()


def test_remote_embedding_tasks_normalization_and_provider_errors(monkeypatch):
    from app.services.embedding_service import EmbeddingService
    settings = get_settings()
    monkeypatch.setattr(settings, "embedding_backend", "gemini")
    monkeypatch.setattr(settings, "remote_embedding_dimension", 3)
    service = EmbeddingService()
    response = Mock(status_code=200)
    response.json.return_value = {"embeddings": [{"values": [3., 4., 0.]}]}
    with patch("requests.post", return_value=response) as post:
        assert service.embed_texts(["passage"])[0] == [.6, .8, 0.]
        assert post.call_args.kwargs["json"]["requests"][0]["taskType"] == "RETRIEVAL_DOCUMENT"
        service.embed_query("question")
        assert post.call_args.kwargs["json"]["requests"][0]["taskType"] == "RETRIEVAL_QUERY"
        response.status_code = 429
        with pytest.raises(RuntimeError, match="HTTP 429"):
            service.embed_query("question")


def test_vercel_runtime_requires_durable_database_and_sets_origins(monkeypatch):
    from infra.vercel_runtime import configure
    import os
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        configure()
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@db.example/test")
    monkeypatch.setenv("VERCEL_URL", "test-deployment.vercel.app")
    monkeypatch.setenv("CORS_ORIGINS", "https://custom.example")
    configure()
    import os
    assert "https://test-deployment.vercel.app" in os.environ["CORS_ORIGINS"]
    assert "https://custom.example" in os.environ["CORS_ORIGINS"]


def test_cloud_entrypoint_routes_and_lightweight_imports(tmp_path):
    import os
    import subprocess
    import sys
    env = {**os.environ, "DATABASE_URL": "postgresql://fake:fake@127.0.0.1:1/fake",
        "DEBUG": "false", "STORAGE_BACKEND": "vercel_blob", "VECTOR_BACKEND": "postgres",
        "PROCESSING_BACKEND": "vercel_queue", "EMBEDDING_BACKEND": "gemini",
        "UPLOAD_DIR": str(tmp_path / "uploads"), "CHROMA_PERSIST_DIR": str(tmp_path / "chroma"),
        "SAMPLE_DOCS_DIR": str(tmp_path / "samples")}
    code = """
import sys
from index import app
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from app.security import current_user
app.dependency_overrides[current_user] = lambda: 'local'
client = TestClient(app)
assert client.get('/api/auth/me').status_code == 200
assert client.post('/api/documents/uploads', json={}).status_code == 422
assert client.post('/api/chat/stream', json={}).status_code == 422
with patch('app.database.database.engine', MagicMock()):
    assert client.get('/api/ready').status_code == 200
assert not {'torch', 'chromadb', 'sentence_transformers'} & set(sys.modules)
print('Cloud routing and lightweight imports verified')
"""
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stdout + result.stderr


def test_internal_callback_requires_worker_secret(cloud_settings, monkeypatch):
    from fastapi import FastAPI
    from app.api.queue_internal import router
    monkeypatch.setattr(cloud_settings, "internal_worker_secret", "test-worker-secret")
    private = FastAPI()
    private.include_router(router)
    with TestClient(private) as client, patch("app.services.cloud_jobs.process_cloud_document") as process:
        message = {"document_id": "test-document"}
        assert client.post("/internal/process-document", json=message).status_code == 404
        assert client.post("/internal/process-document", json=message, headers={"Authorization": "Bearer invalid"}).status_code == 404
        assert client.post("/internal/process-document", json=message, headers={"Authorization": "Bearer test-worker-secret"}).status_code == 200
        process.assert_called_once_with("test-document")
        assert client.post("/api/internal/process-document", json=message, headers={"Authorization": "Bearer test-worker-secret"}).status_code == 404
