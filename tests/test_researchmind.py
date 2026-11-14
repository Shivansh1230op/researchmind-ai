from tests.signup_helpers import register_verified
"""Critical multi-user boundary and SSE contract tests; no external model calls."""
import io
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import get_settings
from app.database.database import get_db_context
from app.database.models import Document, DocumentAccess, ResearchReport
from app.services.retrieval_service import RetrievalResult


@pytest.fixture
def secured():
    settings = get_settings()
    previous = settings.auth_required
    settings.auth_required = True
    try:
        with TestClient(app) as client:
            yield client
    finally:
        settings.auth_required = previous


def account(client):
    email = f"{uuid.uuid4().hex}@example.com"
    r = register_verified(client, {"email":email,"password":"correct horse battery","name":"Ada"})
    assert r.status_code == 201, r.text
    workspace = client.get("/workspaces").json()[0]["id"]
    return r.json()["id"], workspace, email


def document(owner, workspace):
    with get_db_context() as db:
        doc = Document(filename="evidence.md",file_path="unused.md",file_type="md",file_size=100,status="ready",total_chunks=1)
        db.add(doc); db.flush()
        db.add(DocumentAccess(document_id=doc.id,user_id=owner,workspace_id=workspace)); db.commit()
        return doc.id


def test_auth_login_logout_and_hashing(secured):
    _, _, email = account(secured)
    assert secured.get("/auth/me").json()["name"] == "Ada"
    assert secured.cookies.get("researchmind_session")
    assert secured.post("/auth/logout").status_code == 200
    assert secured.get("/documents").status_code == 401
    assert secured.post("/auth/login",json={"email":email,"password":"incorrect password"}).status_code == 401
    assert secured.post("/auth/login",json={"email":email,"password":"correct horse battery"}).status_code == 200


def test_document_and_workspace_isolation(secured):
    user, workspace, _ = account(secured)
    doc = document(user, workspace)
    assert doc in [d["id"] for d in secured.get("/documents").json()["documents"]]
    secured.post("/auth/logout")
    account(secured)
    assert secured.get("/documents").json()["total"] == 0
    for path in [f"/documents/{doc}/preview",f"/documents/{doc}/file",f"/documents/{doc}/status"]:
        assert secured.get(path).status_code == 404
    assert secured.delete(f"/documents/{doc}").status_code == 404
    assert secured.get("/documents",headers={"X-Workspace-Id":workspace}).status_code == 404
    assert secured.post("/chat/stream",json={"question":"Steal private evidence","session_id":"test","document_ids":[doc]}).status_code == 404


def test_workspace_scope_and_upload_validation(secured):
    user, workspace, _ = account(secured)
    document(user, workspace)
    other = secured.post("/workspaces",json={"name":"Another topic"}).json()["id"]
    assert secured.get("/documents",headers={"X-Workspace-Id":other}).json()["total"] == 0
    assert secured.post("/documents/upload",files={"file":("fake.pdf",b"not a pdf","application/pdf")}).status_code == 400
    assert secured.post("/documents/upload",files={"file":("fake.docx",b"not a zip")}).status_code == 400
    assert secured.post("/documents/upload",files={"file":("binary.txt",b"a\x00b")}).status_code == 400


def test_sse_tokens_sources_citation_validation_and_persistence(secured):
    user, workspace, _ = account(secured)
    doc = document(user, workspace)
    pipeline = MagicMock()
    pipeline.retrieval_service.retrieve.return_value = [RetrievalResult("Supported evidence",{"document_id":doc,"document_name":"evidence.md","chunk_index":0},final_score=.8)]
    pipeline._build_sources.return_value = [{"document_id":doc,"document_name":"evidence.md","page_number":None,"chunk_index":0,"content":"Supported evidence","similarity_score":.8}]
    pipeline.llm_service.stream_response.return_value = iter(["Supported ","answer [1] and invalid [99]."])
    pipeline.memory_service.get_history_messages.return_value = []
    pipeline._check_no_answer.return_value = False
    with patch("app.api.routes.get_rag_pipeline",return_value=pipeline):
        r = secured.post("/chat/stream",json={"question":"What is supported?","session_id":"citation-test","document_ids":[doc]})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    assert "event: token" in r.text and "event: sources" in r.text and "event: done" in r.text
    assert "reference unavailable" in r.text
    assert pipeline.memory_service.add_message.call_count == 2
    assert pipeline.retrieval_service.retrieve.call_args.kwargs["document_ids"] == [doc]


def test_provider_failure_is_error_event(secured):
    user, workspace, _ = account(secured)
    doc=document(user,workspace)
    with patch("app.api.routes.get_rag_pipeline",side_effect=RuntimeError("secret provider detail")):
        r=secured.post("/chat/stream",json={"question":"Explain","session_id":"fail","document_ids":[doc]})
    assert "event: error" in r.text
    assert "secret provider detail" not in r.text


def test_cross_origin_mutation_rejected(secured):
    account(secured)
    assert secured.post("/workspaces",json={"name":"Bad"},headers={"origin":"https://attacker.example"}).status_code == 403


def test_report_exports_are_real_documents(secured):
    user, workspace, _ = account(secured)
    with get_db_context() as db:
        report=ResearchReport(user_id=user,workspace_id=workspace,title="Evidence review",content="A supported finding.\n"*100,sources_json=[])
        db.add(report);db.commit();id=report.id
    for format, magic in [("pdf",b"%PDF"),("docx",b"PK"),("md",b"Evidence review")]:
        response=secured.get(f"/reports/{id}/export?format={format}")
        assert response.status_code==200,response.text
        assert response.content.startswith(magic)
    secured.post("/auth/logout");account(secured)
    assert secured.get(f"/reports/{id}/export").status_code==404
