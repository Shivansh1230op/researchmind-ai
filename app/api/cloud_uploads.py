"""Authenticated reservations for direct browser-to-private-Blob uploads."""
from datetime import datetime, timedelta
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.database.database import get_db
from app.database.models import Document, DocumentAccess, UploadTicket
from app.models.schemas import DocumentMetadata
from app.security import current_user, workspace_id
from app.services.processing_jobs import enqueue
from app.services.source_storage import blob_client

router = APIRouter()


class ReserveUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=240)
    file_size: int = Field(gt=0)


class AuthorizeUpload(BaseModel):
    ticket_id: str
    pathname: str


def ticket_for_user(db, id, request, user, lock=False):
    query = db.query(UploadTicket).filter_by(id=id, user_id=user,
        workspace_id=workspace_id(request, user, db))
    ticket = (query.with_for_update() if lock else query).first()
    if ticket is None:
        raise HTTPException(404, "Upload not found.")
    if ticket.expires_at < datetime.utcnow() and not ticket.document_id:
        raise HTTPException(410, "Upload expired. Please select the file again.")
    return ticket


@router.post("/documents/uploads", status_code=201)
def reserve_upload(body: ReserveUpload, request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    if get_settings().storage_backend != "vercel_blob":
        raise HTTPException(404, "Cloud uploads are not enabled.")
    filename = Path(body.filename.replace("\\", "/")).name
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in get_settings().allowed_extensions:
        raise HTTPException(400, "Supported files: PDF, DOCX, TXT and Markdown.")
    if body.file_size > get_settings().max_file_size_bytes:
        raise HTTPException(413, "File exceeds the configured size limit.")
    ticket = UploadTicket(user_id=user, workspace_id=workspace_id(request, user, db),
        filename=filename, pathname=f"sources/{uuid.uuid4().hex}.{extension}",
        file_size=body.file_size, expires_at=datetime.utcnow() + timedelta(hours=1))
    db.add(ticket)
    db.commit()
    return {"id": ticket.id, "pathname": ticket.pathname}


@router.post("/storage/upload-authorizations")
def authorize_upload(body: AuthorizeUpload, request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    ticket = ticket_for_user(db, body.ticket_id, request, user)
    if ticket.pathname != body.pathname or ticket.document_id:
        raise HTTPException(403, "This upload is not authorized.")
    return {"maximumSizeInBytes": ticket.file_size}


@router.post("/documents/uploads/{id}/complete", response_model=DocumentMetadata, status_code=202)
async def complete_upload(id: str, request: Request, user: str = Depends(current_user), db: Session = Depends(get_db)):
    ticket = ticket_for_user(db, id, request, user, lock=True)
    if ticket.document_id:
        document = db.get(Document, ticket.document_id)
        if not document:
            raise HTTPException(410, "This document was deleted.")
        return DocumentMetadata.model_validate(document)
    try:
        metadata = await run_in_threadpool(blob_client().head_blob, ticket.pathname)
    except FileNotFoundError:
        raise HTTPException(409, "Upload has not finished yet.") from None
    if metadata.size != ticket.file_size:
        raise HTTPException(400, "Uploaded file size does not match the reservation.")
    document = Document(id=ticket.id, filename=ticket.filename,
        file_path="blob:" + ticket.pathname, file_type=Path(ticket.filename).suffix[1:].lower(),
        file_size=ticket.file_size, status="queued")
    db.add(document)
    db.flush()
    db.add(DocumentAccess(document_id=document.id, user_id=user, workspace_id=ticket.workspace_id))
    enqueue(db, document.id)
    ticket.document_id = document.id
    db.commit()
    from app.services.cloud_jobs import dispatch
    try:
        await dispatch(document.id)
    except Exception:
        raise HTTPException(503, "Upload saved, but processing could not be scheduled. Retry it in your library.") from None
    return DocumentMetadata.model_validate(document)
