"""Email ownership must be verified before an account or session is created."""
import re
import secrets
import threading
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.database.models import SignupChallenge, User
from app.security import password_hash, verify_password
from app.services.email_service import email_configured, send_signup_code

router = APIRouter()
COOLDOWN = 60
_send_locks = [threading.Lock() for _ in range(64)]


def deliver(challenge, code, db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Another signup request is in progress. Please try again shortly.")
    try:
        send_signup_code(challenge.email, code)
    except Exception:
        raise HTTPException(503, "We couldn't send your code. Wait a minute, then try again or contact support.")
    return {"challenge_id": challenge.id, "email": challenge.email, "expires_in": 600, "resend_after": COOLDOWN}


def request_signup(body, db):
    with _send_locks[hash(body.email.strip().lower()) % len(_send_locks)]:
        return _request_signup(body, db)


def _request_signup(body, db):
    email = body.email.strip().lower()
    if db.bind.dialect.name == "postgresql":
        import hashlib
        from sqlalchemy import text
        lock_key = int.from_bytes(hashlib.sha256(email.encode()).digest()[:8], "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
    if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+", email) or len(email) > 254:
        raise HTTPException(422, "Enter a valid email address.")
    if not body.name.strip():
        raise HTTPException(422, "Enter your name.")
    if not email_configured():
        raise HTTPException(503, "Email verification is not available yet. Please contact the administrator.")
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "An account with this email already exists. Please sign in.")
    now = datetime.utcnow()
    pending = db.query(SignupChallenge).filter_by(email=email).first()
    if pending:
        check_send_limits(pending, now)
    else:
        pending = SignupChallenge(email=email, window_started_at=now, send_count=0)
        db.add(pending)
    code = f"{secrets.randbelow(1000000):06d}"
    pending.id = secrets.token_urlsafe(32)
    pending.name = body.name.strip()
    pending.password_hash = password_hash(body.password)
    pending.code_hash = password_hash(code)
    pending.expires_at = now + timedelta(minutes=10)
    pending.sent_at = now
    pending.send_count += 1
    pending.attempts = 0
    pending.consumed = 0
    return deliver(pending, code, db)


def check_send_limits(challenge, now):
    remaining = COOLDOWN - int((now - challenge.sent_at).total_seconds())
    if remaining > 0:
        raise HTTPException(429, f"Please wait {remaining} seconds before requesting another code.", headers={"Retry-After": str(remaining)})
    if now - challenge.window_started_at >= timedelta(hours=1):
        challenge.window_started_at, challenge.send_count = now, 0
    if challenge.send_count >= 6:
        raise HTTPException(429, "Too many code requests. Please try again in an hour.")


class ChallengeBody(BaseModel):
    challenge_id: str = Field(min_length=20, max_length=64)


class VerifyBody(ChallengeBody):
    code: str = Field(pattern=r"^[0-9]{6}$", min_length=6, max_length=6)


@router.post("/auth/register/resend")
def resend(body: ChallengeBody, db: Session = Depends(get_db)):
    challenge = db.get(SignupChallenge, body.challenge_id)
    if not challenge:
        raise HTTPException(400, "This signup request is no longer valid. Please start again.")
    with _send_locks[hash(challenge.email) % len(_send_locks)]:
        return _resend(body, db)


def _resend(body, db):
    challenge = db.query(SignupChallenge).filter_by(id=body.challenge_id).populate_existing().first()
    if not challenge or challenge.consumed:
        raise HTTPException(400, "This signup request is no longer valid. Please start again.")
    if not email_configured():
        raise HTTPException(503, "Email verification is unavailable. Please contact the administrator.")
    now = datetime.utcnow()
    check_send_limits(challenge, now)
    code = f"{secrets.randbelow(1000000):06d}"
    challenge.code_hash = password_hash(code)
    challenge.sent_at, challenge.expires_at = now, now + timedelta(minutes=10)
    challenge.attempts = 0
    challenge.send_count += 1
    return deliver(challenge, code, db)


@router.post("/auth/register/verify", status_code=201)
def verify(body: VerifyBody, response: Response, db: Session = Depends(get_db)):
    challenge = db.get(SignupChallenge, body.challenge_id)
    if not challenge or challenge.consumed:
        raise HTTPException(400, "This code is no longer valid. Please start signup again.")
    if challenge.expires_at < datetime.utcnow():
        raise HTTPException(400, "Your code has expired. Please request a new code.")
    if challenge.attempts >= 5:
        raise HTTPException(429, "Too many incorrect attempts. Request a new code.")
    # Reserve an attempt atomically before checking the code.
    reserved = db.query(SignupChallenge).filter_by(id=challenge.id, attempts=challenge.attempts, consumed=0).update({"attempts": challenge.attempts + 1}, synchronize_session=False)
    db.commit()
    if not reserved:
        raise HTTPException(409, "Another verification is in progress. Please retry.")
    if not verify_password(body.code, challenge.code_hash):
        raise HTTPException(400, "That code is incorrect. Please check your email and try again.")
    claimed = db.query(SignupChallenge).filter_by(id=challenge.id, consumed=0, code_hash=challenge.code_hash).update({"consumed": 1}, synchronize_session=False)
    if not claimed:
        db.rollback()
        raise HTTPException(400, "This code has already been used or replaced.")
    user = User(email=challenge.email, name=challenge.name, password_hash=challenge.password_hash)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists. Please sign in.")
    from app.api.workspace import login_cookie
    return login_cookie(response, user, db)
