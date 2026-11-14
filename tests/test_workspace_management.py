from tests.signup_helpers import register_verified
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import get_settings
from app.database.database import get_db_context
from app.database.models import ConversationSession, ChatMessage, Document, DocumentAccess
from app.security import scope_session
from app.services.chat_memory import ChatMemoryService


@pytest.fixture
def authenticated():
    settings = get_settings(); previous = settings.auth_required; settings.auth_required = True
    try:
        with TestClient(app) as client:
            user = register_verified(client, {"email": f"{uuid.uuid4().hex}@example.com", "password": "long testing password", "name": "Ada"}).json()["id"]
            workspace = client.get("/workspaces").json()[0]["id"]
            yield client, user, workspace
    finally:
        settings.auth_required = previous


def test_background_upload_returns_accepted_and_owned_status(authenticated):
    client, user, workspace = authenticated
    response = client.post("/documents/upload?background=true", files={"file": ("queued.md", b"# A study\nA new finding.")})
    assert response.status_code == 202, response.text
    document_id = response.json()["id"]
    assert response.json()["status"] == "queued"
    status = client.get(f"/documents/{document_id}/status").json()
    assert status["stage"] == "queued" and status["attempts"] == 0
    assert client.delete(f"/documents/{document_id}").status_code == 409
    assert client.patch(f"/documents/{document_id}", json={"filename": "new.md"}).status_code == 409
    with get_db_context() as db:
        access = db.get(DocumentAccess, document_id)
        assert access.user_id == user and access.workspace_id == workspace
        # Keep test queue isolated from other worker tests.
        from app.database.models import DocumentProcessingJob
        job = db.query(DocumentProcessingJob).filter_by(document_id=document_id).first()
        job.status = "error"; db.get(Document, document_id).status = "error"; db.commit()


def test_conversation_rename_delete_and_workspace_isolation(authenticated):
    import hashlib
    client, user, workspace = authenticated
    handle = "saved-conversation"
    internal = hashlib.sha256(f"{user}:{workspace}:{handle}".encode()).hexdigest()
    memory = ChatMemoryService()
    memory.add_message(internal, "user", "What did the study find?")
    with get_db_context() as db:
        row = db.query(ConversationSession).filter_by(session_id=internal).first()
        row.title = f"{user}:{workspace}:{handle}"; db.commit()
    assert client.patch(f"/chat/sessions/{handle}", json={"title": "Reviewed findings"}).status_code == 200
    assert client.get("/chat/sessions").json()[0]["title"] == "Reviewed findings"
    assert client.patch(f"/chat/sessions/{handle}", json={"title": "   "}).status_code == 422
    other = client.post("/workspaces", json={"name": "Other research"}).json()["id"]
    assert client.patch(f"/chat/sessions/{handle}", headers={"X-Workspace-Id": other}, json={"title": "Stolen"}).status_code == 404
    assert client.delete(f"/chat/sessions/{handle}", headers={"X-Workspace-Id": other}).status_code == 404
    assert client.delete(f"/workspaces/{workspace}").status_code == 409
    assert client.delete(f"/chat/sessions/{handle}").status_code == 200
    assert client.get("/chat/sessions").json() == []
    with get_db_context() as db:
        assert db.query(ChatMessage).filter_by(session_id=internal).count() == 0


def test_batch_summary_checks_all_documents_before_provider_call(authenticated):
    client, user, workspace = authenticated
    with get_db_context() as db:
        doc = Document(filename="study.txt", file_path="unused", file_type="txt", file_size=20, status="ready")
        db.add(doc); db.flush(); db.add(DocumentAccess(document_id=doc.id, user_id=user, workspace_id=workspace)); db.commit(); id = doc.id
    service = MagicMock()
    service.summarize.return_value = {"document_id": id, "summary": "A grounded summary.", "sources": []}
    with patch("app.api.routes.get_summarization_service", return_value=service):
        bad = client.post("/research/summarize", json={"document_ids": [id, "inaccessible"], "summary_type": "executive", "length": "short"})
        assert bad.status_code == 404
        service.summarize.assert_not_called()
        good = client.post("/research/summarize", json={"document_ids": [id], "summary_type": "academic", "length": "long"})
        assert good.status_code == 200, good.text
        assert service.summarize.call_args.kwargs["length"] == "long"
        assert service.summarize.call_args.kwargs["summary_type"] == "academic"
