from tests.signup_helpers import register_verified
"""Real HTTP, SQL, extraction, chunking and Chroma; external model calls mocked."""
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import get_settings
from app.services.document_processor import DocumentProcessor
from app.services.rag_pipeline import RAGPipeline
from app.services.vector_store import VectorStore


def test_register_upload_retrieve_cite_resume_and_export():
    settings=get_settings()
    previous=settings.auth_required
    settings.auth_required=True
    store=VectorStore(collection_name=f"workflow_{uuid.uuid4().hex[:10]}")
    processor=DocumentProcessor()
    processor.vector_store=store
    pipeline=RAGPipeline()
    pipeline.vector_store=store
    pipeline.retrieval_service.vector_store=store
    pipeline.retrieval_service.enable_reranking=False
    try:
        with TestClient(app) as client, \
             patch("app.api.routes._document_processor",processor), \
             patch("app.api.routes._rag_pipeline",pipeline), \
             patch.object(processor.embedding_service,"embed_texts",return_value=[[1.0,0.0,0.0]]), \
             patch.object(pipeline.embedding_service,"embed_query",return_value=[1.0,0.0,0.0]), \
             patch.object(pipeline.llm_service,"stream_response",return_value=iter(["The study reports ","42 observations [1]."])), \
             patch.object(pipeline.llm_service,"generate_response",return_value="The study reports 42 observations (source: study.md, page 1)."):
            r=register_verified(client, {"email":f"{uuid.uuid4().hex}@example.com","password":"test password with enough entropy","name":"Researcher"})
            assert r.status_code==201
            w=client.get("/workspaces").json()[0]["id"]
            headers={"X-Workspace-Id":w}
            r=client.post("/documents/upload",headers=headers,files={"file":("study.md",b"# Study\nThe study reports 42 observations. The method is a controlled experiment.","text/markdown")})
            assert r.status_code==201,r.text
            doc=r.json()["id"]
            assert r.json()["status"]=="ready"
            assert client.get(f"/documents/{doc}/preview",headers=headers).json()["text"]
            r=client.post("/chat/stream",headers=headers,json={"question":"How many observations?","session_id":"workflow-session","document_ids":[doc]})
            assert "event: done" in r.text,r.text
            assert doc in r.text and "42 observations" in r.text
            history=client.get("/chat/history?session_id=workflow-session",headers=headers).json()
            assert len(history["messages"])==2
            assert history["messages"][1]["sources"][0]["document_id"]==doc
            assert client.get("/chat/sessions",headers=headers).json()[0]["id"]=="workflow-session"
            r=client.post("/reports/generate",headers=headers,json={"title":"Observation review","document_ids":[doc]})
            assert r.status_code==201,r.text
            report=r.json()["id"]
            assert client.get(f"/reports/{report}/export?format=pdf",headers=headers).content.startswith(b"%PDF")
            assert client.get(f"/reports/{report}/export?format=docx",headers=headers).content.startswith(b"PK")
    finally:
        settings.auth_required=previous
        store.reset()
