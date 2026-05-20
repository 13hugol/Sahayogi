from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path

from flask import current_app


def send_email(subject: str, recipient: str, body: str) -> bool:
    mail_server = current_app.config.get("MAIL_SERVER")
    sender = current_app.config["MAIL_DEFAULT_SENDER"]
    if not mail_server:
        log_email(subject, recipient, body)
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(body)
    try:
        with smtplib.SMTP(mail_server, current_app.config["MAIL_PORT"]) as client:
            if current_app.config["MAIL_USE_TLS"]:
                client.starttls()
            if current_app.config["MAIL_USERNAME"]:
                client.login(current_app.config["MAIL_USERNAME"], current_app.config["MAIL_PASSWORD"])
            client.send_message(message)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        current_app.logger.warning("Email delivery failed for %s: %s", recipient, exc)
        log_email(subject, recipient, body)
        return False


def log_email(subject: str, recipient: str, body: str) -> None:
    log_file = Path(current_app.config["MAIL_LOG_FILE"])
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"TO: {recipient}\nSUBJECT: {subject}\n{body}\n{'-' * 60}\n")
