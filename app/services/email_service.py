"""Transactional SMTP delivery; codes and SMTP credentials never enter logs."""
import smtplib
import ssl
from email.message import EmailMessage
from app.core.config import get_settings


def email_configured():
    s = get_settings()
    return bool(s.smtp_host and s.smtp_from_email)


def send_signup_code(recipient: str, code: str):
    s = get_settings()
    if not email_configured():
        raise RuntimeError("Email delivery is not configured.")
    if not s.smtp_starttls and not s.smtp_use_ssl:
        raise RuntimeError("Configure TLS for email delivery.")
    message = EmailMessage()
    message["Subject"] = "Your ResearchMind AI verification code"
    message["From"] = s.smtp_from_email
    message["To"] = recipient
    message.set_content(f"Your ResearchMind AI verification code is {code}.\n\nIt expires in 10 minutes. Never share this code. If you didn't request an account, ignore this email.")
    message.add_alternative(f"""<html><body style="margin:0;background:#f3f5fa;font-family:Arial,sans-serif;padding:32px">
    <div style="max-width:480px;margin:auto;background:white;border-radius:16px;padding:36px">
    <p style="color:#5b66d8;font-weight:bold">ResearchMind AI</p><h1 style="font-size:26px;color:#17213a">Verify your email.</h1>
    <p style="color:#62708a;line-height:1.7">One small step before your next discovery. Enter this code to finish creating your account.</p>
    <div style="background:#f0f3ff;border-radius:10px;padding:22px;text-align:center;letter-spacing:10px;font-size:32px;font-weight:bold;color:#4359be">{code}</div>
    <p style="font-size:13px;color:#62708a;line-height:1.7">This code expires in 10 minutes. Never share it with anyone.</p>
    <p style="font-size:11px;color:#8a94a7">Didn't request this? You can safely ignore this email.</p></div></body></html>""", subtype="html")
    transport = smtplib.SMTP_SSL if s.smtp_use_ssl else smtplib.SMTP
    options = {"host": s.smtp_host, "port": s.smtp_port, "timeout": 15}
    if s.smtp_use_ssl:
        options["context"] = ssl.create_default_context()
    with transport(**options) as server:
        if s.smtp_starttls and not s.smtp_use_ssl:
            server.starttls(context=ssl.create_default_context())
        if s.smtp_username:
            server.login(s.smtp_username, s.smtp_password)
        server.send_message(message)
