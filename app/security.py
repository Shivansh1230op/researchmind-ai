"""Password hashing, revocable sessions, and resource authorization."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.database import get_db
from app.database.models import User, LoginSession, Workspace, DocumentAccess, Document


def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return f"{salt}:{digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    return hmac.compare_digest(password_hash(password, encoded.split(":")[0]), encoded)


def current_user(request: Request, db: Session = Depends(get_db)) -> str:
    if not get_settings().auth_required:
        return "local"
    token = request.cookies.get("researchmind_session", "")
    digest = hashlib.sha256(token.encode()).hexdigest()
    session = db.query(LoginSession).filter_by(token_hash=digest).first()
    if not session or session.expires_at < datetime.utcnow():
        raise HTTPException(401, "Please sign in to your research workspace.")
    # Cookie-authenticated mutations require a same-origin browser request.
    origin = request.headers.get("origin")
    allowed = get_settings().cors_origins.split(",")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in allowed:
        raise HTTPException(403, "Origin is not allowed.")
    return session.user_id


def workspace_id(request: Request, user: str, db: Session) -> str:
    selected = request.headers.get("x-workspace-id")
    if selected:
        ws = db.query(Workspace).filter_by(id=selected, user_id=user).first()
        if not ws:
            raise HTTPException(404, "Workspace not found.")
        return ws.id
    ws = db.query(Workspace).filter_by(user_id=user).order_by(Workspace.created_at).first()
    if not ws:
        ws = Workspace(user_id=user, name="My research")
        db.add(ws)
        db.commit()
    return ws.id


def accessible_ids(request: Request, user: str, db: Session) -> list[str]:
    if user == "local" and not request.headers.get("x-workspace-id"):
        return [d.id for d in db.query(Document).all()]
    ws = workspace_id(request, user, db)
    return [a.document_id for a in db.query(DocumentAccess).filter_by(user_id=user, workspace_id=ws)]


def require_document(document_id: str, request: Request, user: str, db: Session) -> Document:
    if document_id not in accessible_ids(request, user, db):
        raise HTTPException(404, "Document not found.")
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found.")
    return doc


def require_owned_document(document_id: str, user: str, db: Session) -> Document:
    """Source URLs have no workspace header, but still require ownership."""
    if user != "local" and not db.query(DocumentAccess).filter_by(document_id=document_id, user_id=user).first():
        raise HTTPException(404, "Document not found.")
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found.")
    return doc


def scope_session(session_id: str, request: Request, user: str, db: Session) -> str:
    if user == "local":
        return session_id
    ws = workspace_id(request, user, db)
    return hashlib.sha256(f"{user}:{ws}:{session_id}".encode()).hexdigest()
