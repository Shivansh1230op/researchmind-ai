from unittest.mock import patch


def register_verified(client, body):
    """Existing workflow tests still go through the real OTP verifier."""
    with patch("app.api.signup.email_configured", return_value=True), patch("app.api.signup.send_signup_code") as send:
        pending = client.post("/auth/register", json=body)
        assert pending.status_code == 202, pending.text
        code = send.call_args.args[1]
        return client.post("/auth/register/verify", json={"challenge_id": pending.json()["challenge_id"], "code": code})
