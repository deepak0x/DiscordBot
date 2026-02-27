"""
Email service — sends emails via Gmail SMTP with a resume attachment.
Always call via asyncio.to_thread() from async contexts.
"""
import os
import smtplib
import logging
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config

logger = logging.getLogger(__name__)


def send_email(
    to_email: str,
    subject: str,
    body: str,
    resume_path: str,
    from_email: str | None = None,
) -> None:
    """
    Send a plain-text email with a PDF resume attachment.

    Raises:
        ValueError: if required credentials are missing.
        FileNotFoundError: if the resume file does not exist.
        smtplib.SMTPException: on delivery failure.
    """
    sender = from_email or config.SMTP_EMAIL

    if not os.path.exists(resume_path):
        raise FileNotFoundError(f"Resume not found: {resume_path}")

    msg = MIMEMultipart()
    msg["From"]    = sender
    msg["To"]      = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    # Attach resume
    with open(resume_path, "rb") as fh:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(fh.read())
    encoders.encode_base64(part)
    filename = os.path.basename(resume_path)
    part.add_header("Content-Disposition", f"attachment; filename={filename}")
    msg.attach(part)

    # Send
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(config.SMTP_EMAIL, config.SMTP_PASSWORD)
        server.send_message(msg)

    logger.info("Email sent → %s (from %s)", to_email, sender)
