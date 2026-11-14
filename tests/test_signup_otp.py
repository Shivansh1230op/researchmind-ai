import uuid
from datetime import datetime, timedelta
from unittest.mock import patch
from app.database.database import get_db_context
from app.database.models import SignupChallenge, User


def credentials():
    return {"email": f"{uuid.uuid4().hex}@example.com", "name": "Ada", "password": "a strong testing password"}


def test_account_requires_real_otp_and_code_cannot_be_replayed(api_client):
    body = credentials()
    with patch("app.api.signup.email_configured", return_value=True), patch("app.api.signup.send_signup_code") as send:
        response = api_client.post("/auth/register", json=body)
    assert response.status_code == 202
    challenge = response.json()["challenge_id"]
    code = send.call_args.args[1]
    assert code not in response.text
    with get_db_context() as db:
        assert db.query(User).filter_by(email=body["email"]).first() is None
        pending = db.get(SignupChallenge, challenge)
        assert pending.code_hash != code and pending.password_hash != body["password"]
    verified = api_client.post("/auth/register/verify", json={"challenge_id": challenge, "code": code})
    assert verified.status_code == 201
    assert "HttpOnly" in verified.headers["set-cookie"]
    assert api_client.post("/auth/register/verify", json={"challenge_id": challenge, "code": code}).status_code == 400


def test_resend_cooldown_invalidates_old_code_and_expiry(api_client):
    with patch("app.api.signup.email_configured", return_value=True), patch("app.api.signup.send_signup_code") as send:
        response = api_client.post("/auth/register", json=credentials())
        id = response.json()["challenge_id"]
        old = send.call_args.args[1]
        assert api_client.post("/auth/register/resend", json={"challenge_id": id}).status_code == 429
        with get_db_context() as db:
            db.get(SignupChallenge, id).sent_at = datetime.utcnow() - timedelta(seconds=61); db.commit()
        with patch("app.api.signup.secrets.randbelow", return_value=(int(old) + 1) % 1000000):
            assert api_client.post("/auth/register/resend", json={"challenge_id": id}).status_code == 200
        assert api_client.post("/auth/register/verify", json={"challenge_id": id, "code": old}).status_code == 400
        with get_db_context() as db:
            db.get(SignupChallenge, id).expires_at = datetime.utcnow() - timedelta(seconds=1); db.commit()
        assert api_client.post("/auth/register/verify", json={"challenge_id": id, "code": send.call_args.args[1]}).status_code == 400


def test_attempt_limit_and_missing_delivery_configuration(api_client):
    with patch("app.api.signup.email_configured", return_value=False):
        assert api_client.post("/auth/register", json=credentials()).status_code == 503
    with patch("app.api.signup.email_configured", return_value=True), patch("app.api.signup.send_signup_code") as send:
        id = api_client.post("/auth/register", json=credentials()).json()["challenge_id"]
        code = send.call_args.args[1]
    wrong = f"{(int(code)+1)%1000000:06d}"
    for _ in range(5):
        assert api_client.post("/auth/register/verify", json={"challenge_id": id, "code": wrong}).status_code == 400
    assert api_client.post("/auth/register/verify", json={"challenge_id": id, "code": code}).status_code == 429


def test_smtp_failure_does_not_create_user_or_claim_success(api_client):
    body = credentials()
    with patch("app.api.signup.email_configured", return_value=True), patch("app.api.signup.send_signup_code", side_effect=RuntimeError("secret SMTP credential")):
        response = api_client.post("/auth/register", json=body)
    assert response.status_code == 503
    assert "secret SMTP" not in response.text
    with get_db_context() as db:
        assert db.query(User).filter_by(email=body["email"]).first() is None


def test_email_transport_uses_tls_and_contains_matching_code():
    from types import SimpleNamespace
    from app.services.email_service import send_signup_code
    settings = SimpleNamespace(smtp_host="smtp.example.com", smtp_port=587, smtp_from_email="sender@example.com",
        smtp_username="sender", smtp_password="test-secret", smtp_starttls=True, smtp_use_ssl=False)
    with patch("app.services.email_service.get_settings", return_value=settings), patch("smtplib.SMTP") as smtp:
        send_signup_code("recipient@example.com", "123456")
    server = smtp.return_value.__enter__.return_value
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("sender", "test-secret")
    message = server.send_message.call_args.args[0]
    assert message["To"] == "recipient@example.com"
    assert "123456" in message.get_body(preferencelist=("plain",)).get_content()
    assert "123456" in message.get_body(preferencelist=("html",)).get_content()
