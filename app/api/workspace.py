"""Authenticated workspace, research, analytics, and export APIs."""
import hashlib
import io
import secrets
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.schemas import BatchSummarizeRequest
from app.database.database import get_db
from app.database.models import (User, LoginSession, Workspace, DocumentAccess,
    Document, ConversationSession, ConversationPreferences, DocumentProcessingJob, ChatMessage, ResearchReport)
from app.security import (password_hash, verify_password, current_user, workspace_id,
    accessible_ids, require_document, require_owned_document, scope_session)

router = APIRouter()


@router.post("/research/summarize")
def summarize_many(body: "BatchSummarizeRequest", request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    from app.api.routes import get_summarization_service
    docs = [require_document(id, request, user, db) for id in dict.fromkeys(body.document_ids)]
    if any(doc.status != "ready" for doc in docs):
        raise HTTPException(409, "Wait for all selected documents to finish indexing.")
    try:
        return {"summaries": [get_summarization_service().summarize(document_id=doc.id,
            document_name=doc.filename, summary_type=body.summary_type, length=body.length) for doc in docs]}
    except Exception:
        raise HTTPException(502, "Summary generation failed. Check your model provider and retry.")


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=10, max_length=128)
    name: str = Field(default="Researcher", min_length=1, max_length=100)


def login_cookie(response, user, db):
    token = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(),
        user_id=user.id, expires_at=datetime.utcnow() + timedelta(days=7)))
    db.commit()
    response.set_cookie("researchmind_session", token, httponly=True,
        secure=get_settings().cookie_secure, samesite="lax", max_age=604800, path="/")
    return {"id": user.id, "name": user.name, "email": user.email}


@router.post("/auth/register", status_code=202)
def register(body: Credentials, response: Response, db: Session = Depends(get_db)):
    from app.api.signup import request_signup
    return request_signup(body, db)


@router.post("/auth/login")
def login(body: Credentials, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email.strip().lower()).first()
    # Equalize expensive hashing work for unknown accounts.
    valid = verify_password(body.password, user.password_hash) if user else bool(password_hash(body.password)) and False
    if not valid:
        raise HTTPException(401, "Email or password is incorrect.")
    return login_cookie(response, user, db)


@router.get("/auth/me")
def me(user: str = Depends(current_user), db: Session = Depends(get_db)):
    if user == "local":
        return {"id": "local", "name": "Local researcher", "email": "", "local": True}
    record = db.get(User, user)
    return {"id": record.id, "name": record.name, "email": record.email}


@router.get("/settings")
def public_settings(user: str = Depends(current_user)):
    s = get_settings()
    return {"chunk_size": s.chunk_size, "chunk_overlap": s.chunk_overlap,
        "top_k": s.default_top_k, "hybrid_search": s.enable_hybrid_search,
        "reranking": s.enable_reranking, "max_file_size_mb": s.max_file_size_mb}


@router.post("/auth/logout")
def logout(request: Request, response: Response, user: str = Depends(current_user), db: Session = Depends(get_db)):
    digest = hashlib.sha256(request.cookies.get("researchmind_session", "").encode()).hexdigest()
    db.query(LoginSession).filter_by(token_hash=digest).delete()
    db.commit()
    response.delete_cookie("researchmind_session", path="/")
    return {"success": True}


class WorkspaceBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)


@router.delete("/workspaces/{id}")
def delete_workspace(id: str, user: str = Depends(current_user), db: Session = Depends(get_db)):
    w = db.query(Workspace).filter_by(id=id, user_id=user).first()
    if not w:
        raise HTTPException(404, "Workspace not found.")
    if db.query(DocumentAccess).filter_by(workspace_id=id).count():
        raise HTTPException(409, "Delete documents from this workspace before deleting it.")
    if db.query(ResearchReport).filter_by(workspace_id=id).count():
        raise HTTPException(409, "This workspace contains saved reports and cannot be deleted.")
    if db.query(ConversationSession).filter(ConversationSession.title.startswith(f"{user}:{id}:")).count():
        raise HTTPException(409, "Delete conversation history from this workspace before deleting it.")
    db.delete(w)
    db.commit()
    return {"success": True}


class RenameDocument(BaseModel):
    filename: str = Field(min_length=1, max_length=240)


@router.patch("/documents/{id}")
def rename_document(id: str, body: RenameDocument, request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    from pathlib import Path
    doc = require_document(id, request, user, db)
    if doc.status in {"queued", "processing"}:
        raise HTTPException(409, "Wait for processing to finish before renaming this document.")
    if Path(body.filename).suffix.lower() != f".{doc.file_type}" or "/" in body.filename or "\\" in body.filename:
        raise HTTPException(422, "Keep the original extension and use a filename without path separators.")
    # Update vector metadata as well so future source citations use the new title.
    from app.services.vector_store import VectorStore
    collection = VectorStore().collection
    chunks = collection.get(where={"document_id": id}, include=["metadatas"])
    if chunks["ids"]:
        metadata = [{**m, "document_name": body.filename} for m in chunks["metadatas"]]
        collection.update(ids=chunks["ids"], metadatas=metadata)
    doc.filename = body.filename
    db.commit()
    return {"id": id, "filename": doc.filename}


@router.post("/documents/{id}/reprocess", status_code=202)
async def reprocess_document(id: str, request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    from app.services.processing_jobs import enqueue
    doc = require_document(id, request, user, db)
    if doc.status != "error":
        raise HTTPException(409, "Only failed documents can be reprocessed.")
    enqueue(db, id)
    db.commit()
    if get_settings().processing_backend == "vercel_queue":
        from app.services.cloud_jobs import dispatch
        try:
            await dispatch(id)
        except Exception:
            raise HTTPException(503, "Could not schedule processing. Please retry shortly.") from None
    return {"id": id, "status": doc.status}


@router.delete("/chat/sessions/{id}")
def delete_session(id: str, request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    scoped = scope_session(id, request, user, db)
    session = db.query(ConversationSession).filter_by(session_id=scoped).first()
    if not session:
        raise HTTPException(404, "Conversation not found.")
    db.query(ConversationPreferences).filter_by(session_id=scoped).delete()
    db.delete(session)
    db.commit()
    return {"success": True}


class ConversationTitle(BaseModel):
    title: str = Field(min_length=1, max_length=120)


@router.patch("/chat/sessions/{id}")
def rename_session(id: str, body: ConversationTitle, request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    scoped = scope_session(id, request, user, db)
    session = db.query(ConversationSession).filter_by(session_id=scoped).first()
    if not session:
        raise HTTPException(404, "Conversation not found.")
    title = body.title.strip()
    if not title:
        raise HTTPException(422, "Conversation title cannot be blank.")
    preferences = db.get(ConversationPreferences, scoped)
    if not preferences:
        preferences = ConversationPreferences(session_id=scoped)
        db.add(preferences)
    preferences.display_title = title
    db.commit()
    return {"id": id, "title": title}


@router.get("/workspaces")
def workspaces(request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    workspace_id(request, user, db)
    return [{"id": w.id, "name": w.name, "created_at": w.created_at,
        "documents": db.query(DocumentAccess).filter_by(workspace_id=w.id).count()}
        for w in db.query(Workspace).filter_by(user_id=user).order_by(Workspace.created_at)]


@router.post("/workspaces", status_code=201)
def create_workspace(body: WorkspaceBody, user: str = Depends(current_user), db: Session = Depends(get_db)):
    w = Workspace(user_id=user, name=body.name.strip())
    db.add(w)
    db.commit()
    return {"id": w.id, "name": w.name}


@router.patch("/workspaces/{id}")
def rename_workspace(id: str, body: WorkspaceBody, user: str = Depends(current_user), db: Session = Depends(get_db)):
    w = db.query(Workspace).filter_by(id=id, user_id=user).first()
    if not w:
        raise HTTPException(404, "Workspace not found.")
    w.name = body.name.strip()
    db.commit()
    return {"id": w.id, "name": w.name}


@router.get("/documents/{id}/preview")
def preview(id: str, request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    from app.api.routes import get_document_processor
    doc = require_document(id, request, user, db)
    return {"id": id, "filename": doc.filename,
        "text": get_document_processor().get_document_content_preview(id, max_chars=30000)}


@router.get("/documents/{id}/file")
def source_file(id: str, request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    from pathlib import Path
    doc = require_owned_document(id, user, db)
    from app.services.source_storage import is_blob, blob_client
    if is_blob(doc.file_path):
        from urllib.parse import quote
        def content():
            with blob_client().stream_blob(doc.file_path[5:], access="private") as download:
                yield from download
        media = "application/pdf" if doc.file_type == "pdf" else "application/octet-stream"
        disposition = "inline" if doc.file_type == "pdf" else "attachment"
        return StreamingResponse(content(), media_type=media, headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(doc.filename, safe='')}",
            "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})
    path = Path(doc.file_path).resolve()
    if not path.is_relative_to(Path(get_settings().upload_dir).resolve()) or not path.is_file():
        raise HTTPException(404, "Source file unavailable.")
    media = "application/pdf" if doc.file_type == "pdf" else "application/octet-stream"
    return FileResponse(path, media_type=media, filename=doc.filename,
        content_disposition_type="inline" if doc.file_type == "pdf" else "attachment",
        headers={"X-Content-Type-Options": "nosniff"})


@router.get("/documents/{id}/status")
def document_status(id: str, request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    doc = require_document(id, request, user, db)
    job = db.query(DocumentProcessingJob).filter_by(document_id=id).first()
    return {"id": id, "status": doc.status, "stage": job.stage if job else doc.status,
        "attempts": job.attempts if job else 0, "updated_at": job.updated_at if job else doc.updated_at,
        "error_message": doc.error_message}


@router.get("/chat/sessions")
def sessions(request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    # Public session handles are stored in title metadata by the streaming route.
    prefix = f"{user}:{workspace_id(request, user, db)}:"
    rows = db.query(ConversationSession).filter(ConversationSession.title.startswith(prefix)).order_by(ConversationSession.updated_at.desc()).all()
    result = []
    for row in rows:
        handle = row.title[len(prefix):]
        first = db.query(ChatMessage).filter_by(session_id=row.session_id, role="user").first()
        preferences = db.get(ConversationPreferences, row.session_id)
        result.append({"id": handle, "title": preferences.display_title if preferences else first.content[:80] if first else "New research", "updated_at": row.updated_at})
    return result


@router.get("/analytics/overview")
def analytics(request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    ids = accessible_ids(request, user, db)
    docs = db.query(Document).filter(Document.id.in_(ids)).all()
    prefix = f"{user}:{workspace_id(request, user, db)}:"
    session_ids = [s.session_id for s in db.query(ConversationSession).filter(ConversationSession.title.startswith(prefix))]
    messages = db.query(ChatMessage).filter(ChatMessage.session_id.in_(session_ids), ChatMessage.role == "assistant").count()
    activity = {}
    for d in docs:
        day = d.created_at.date().isoformat()
        activity[day] = activity.get(day, 0) + 1
    return {"documents": len(docs), "questions": messages, "sessions": len(session_ids),
        "storage_bytes": sum(d.file_size for d in docs), "chunks": sum(d.total_chunks for d in docs),
        "success_rate": sum(d.status == "ready" for d in docs) / len(docs) if docs else None,
        "activity": [{"date": d, "documents": n} for d, n in sorted(activity.items())]}


@router.get("/knowledge-graph")
def graph(request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    import numpy as np
    from app.services.vector_store import VectorStore
    ids = accessible_ids(request, user, db)
    docs = db.query(Document).filter(Document.id.in_(ids), Document.status == "ready").limit(100).all()
    vs = VectorStore()
    centers = {}
    for d in docs:
        data = vs.collection.get(where={"document_id": d.id}, include=["embeddings"], limit=200)
        embeddings = data.get("embeddings")
        if embeddings is not None and len(embeddings):
            v = np.mean(embeddings, axis=0)
            centers[d.id] = v / max(float(np.linalg.norm(v)), 1e-9)
    edges = []
    for i, a in enumerate(docs):
        for b in docs[i + 1:]:
            if a.id in centers and b.id in centers:
                score = float(np.dot(centers[a.id], centers[b.id]))
                if score >= 0.35:
                    edges.append({"source": a.id, "target": b.id, "score": round(score, 3), "label": "Embedding cosine similarity"})
    return {"nodes": [{"id": d.id, "label": d.filename, "chunks": d.total_chunks} for d in docs], "edges": edges}


class ReportBody(BaseModel):
    title: str = Field(default="Research report", min_length=1, max_length=200)
    document_ids: list[str] = Field(min_length=1, max_length=20)
    report_type: Literal["Research summary", "Literature review", "Comparative report", "Technical report"] = "Research summary"
    tone: Literal["Academic", "Executive", "Accessible"] = "Academic"


@router.post("/reports/generate", status_code=201)
def generate_report(body: ReportBody, request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    from app.api.routes import get_rag_pipeline
    for id in body.document_ids:
        require_document(id, request, user, db)
    pipeline = get_rag_pipeline()
    result = pipeline.answer_question(
        question=f"Write a {body.tone.lower()} {body.report_type.lower()} with sections: Executive Summary, Introduction, Analysis, Findings, Limitations, Conclusion. Report only supported facts; mark unavailable details explicitly.",
        session_id=scope_session(secrets.token_hex(12), request, user, db),
        document_ids=body.document_ids, top_k=20)
    if result["no_answer_found"]:
        raise HTTPException(422, result["answer"])
    report = ResearchReport(user_id=user, workspace_id=workspace_id(request, user, db),
        title=body.title, content=result["answer"], sources_json=result["sources"])
    db.add(report)
    db.commit()
    return {"id": report.id, "title": report.title, "content": report.content}


@router.get("/reports")
def reports(request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": r.id, "title": r.title, "content": r.content, "created_at": r.created_at}
        for r in db.query(ResearchReport).filter_by(user_id=user, workspace_id=workspace_id(request, user, db)).order_by(ResearchReport.created_at.desc())]


class ReportEdit(BaseModel):
    content: str = Field(max_length=200000)


@router.patch("/reports/{id}")
def edit_report(id: str, body: ReportEdit, request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    report = db.query(ResearchReport).filter_by(id=id, user_id=user, workspace_id=workspace_id(request, user, db)).first()
    if not report:
        raise HTTPException(404, "Report not found.")
    report.content = body.content
    db.commit()
    return {"success": True}


@router.get("/reports/{id}/export")
def export_report(id: str, request: Request, format: Literal["md", "pdf", "docx"] = "md", user: str = Depends(current_user), db: Session = Depends(get_db)):
    report = db.query(ResearchReport).filter_by(id=id, user_id=user, workspace_id=workspace_id(request, user, db)).first()
    if not report:
        raise HTTPException(404, "Report not found.")
    references = "\n\nReferences (retrieved passages)\n" + "\n".join(
        f"{i}. {s['document_name']}, page {s.get('page_number') or 'unavailable'}: {s['content']}"
        for i, s in enumerate(report.sources_json or [], 1))
    text = f"{report.title}\n\n{report.content}{references}"
    if format == "docx":
        from docx import Document as WordDocument
        doc = WordDocument()
        doc.add_heading(report.title, 0)
        for p in (report.content + references).split("\n"):
            doc.add_paragraph(p)
        stream = io.BytesIO()
        doc.save(stream)
        data = stream.getvalue()
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif format == "pdf":
        import fitz
        doc = fitz.open()
        # Story handles pagination rather than truncating overflowing text.
        import html
        story = fitz.Story(html="<body>" + "".join(f"<p>{html.escape(p)}</p>" for p in text.split("\n")) + "</body>")
        stream = io.BytesIO()
        writer = fitz.DocumentWriter(stream)
        more = True
        while more:
            device = writer.begin_page(fitz.Rect(0, 0, 595, 842))
            more, _ = story.place(fitz.Rect(48, 48, 547, 794))
            story.draw(device)
            writer.end_page()
        writer.close()
        data = stream.getvalue()
        media = "application/pdf"
    else:
        data, media = text.encode(), "text/markdown; charset=utf-8"
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="research-report.{format}"'})
