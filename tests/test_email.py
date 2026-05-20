from __future__ import annotations

import smtplib

from app.utils.email import send_email


class RejectingSMTP:
    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def starttls(self):
        return None

    def login(self, *_args):
        raise smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")

    def send_message(self, _message):
        raise AssertionError("message should not send after failed login")


def test_send_email_logs_when_smtp_authentication_fails(app, monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", RejectingSMTP)
    app.config.update(
        MAIL_SERVER="smtp.gmail.com",
        MAIL_USERNAME="bad-user",
        MAIL_PASSWORD="bad-password",
        MAIL_DEFAULT_SENDER="bad-user@example.com",
    )

    with app.app_context():
        send_email("Verify", "member@example.com", "verification link")

    log_text = app.config["MAIL_LOG_FILE"].read_text(encoding="utf-8")
    assert "TO: member@example.com" in log_text
    assert "SUBJECT: Verify" in log_text
    assert "verification link" in log_text
