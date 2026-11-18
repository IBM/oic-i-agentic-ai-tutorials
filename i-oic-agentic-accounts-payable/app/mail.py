"""Gmail AP inbox: IMAP intake of invoice attachments and SMTP notifications to suppliers.

Uses a Google app password (Google Account → Security → 2-Step Verification → App passwords).
Until GMAIL_USER / GMAIL_APP_PASSWORD are set, intake and email actions report 'not configured'.
"""

import email
import imaplib
import smtplib
import ssl
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr

from app import config

ATTACHMENT_TYPES = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff")


def configured() -> bool:
    return bool(config.GMAIL_USER and config.GMAIL_APP_PASSWORD and "placeholder" not in config.GMAIL_USER)


def _decode(value: str | None) -> str:
    out = []
    for part, enc in decode_header(value or ""):
        out.append(part.decode(enc or "utf-8", errors="ignore") if isinstance(part, bytes) else part)
    return "".join(out)


def fetch_invoices(limit: int = 10) -> list[dict]:
    """Return unread messages with invoice attachments and mark them read."""
    if not configured():
        raise RuntimeError("Gmail is not configured — set GMAIL_USER and GMAIL_APP_PASSWORD in .env")
    found = []
    with imaplib.IMAP4_SSL("imap.gmail.com", 993) as imap:
        imap.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
        imap.select("INBOX")
        _typ, data = imap.search(None, "UNSEEN")
        for num in (data[0].split() or [])[-limit:]:
            _typ, msg_data = imap.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            sender = parseaddr(_decode(msg.get("From")))[1]
            subject = _decode(msg.get("Subject"))
            for part in msg.walk():
                name = _decode(part.get_filename())
                if name and name.lower().endswith(ATTACHMENT_TYPES):
                    found.append({"filename": name, "data": part.get_payload(decode=True), "sender": sender,
                                  "subject": subject, "message_id": msg.get("Message-ID", "")})
            imap.store(num, "+FLAGS", "\\Seen")
    return found


def send(to: str, subject: str, html: str, reply_to_message_id: str = "") -> str:
    if not configured():
        raise RuntimeError("Gmail is not configured — set GMAIL_USER and GMAIL_APP_PASSWORD in .env")
    recipient = config.VENDOR_EMAIL_OVERRIDE or to
    msg = MIMEMultipart("alternative")
    msg["From"] = config.GMAIL_USER
    msg["To"] = recipient
    msg["Subject"] = subject
    if reply_to_message_id:
        msg["In-Reply-To"] = msg["References"] = reply_to_message_id
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as smtp:
        smtp.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
        smtp.sendmail(config.GMAIL_USER, [recipient], msg.as_string())
    return recipient


def render(paragraphs: list[str], table: list[tuple[str, str]] | None = None) -> str:
    rows = "".join(f"<tr><td style='padding:4px 16px 4px 0;color:#525252'>{k}</td><td style='padding:4px 0'>{v}</td></tr>"
                   for k, v in table or [])
    body = "".join(f"<p style='margin:0 0 12px'>{p}</p>" for p in paragraphs)
    table_html = f"<table style='margin:8px 0 16px'>{rows}</table>" if rows else ""
    return (f"<div style=\"font-family:'IBM Plex Sans',Arial,sans-serif;font-size:14px;color:#161616;max-width:640px\">"
            f"{body}{table_html}"
            f"<p style='margin:16px 0 0;color:#6f6f6f;font-size:12px'>Sent by the Accounts Payable agent · "
            f"IBM watsonx Orchestrate</p></div>")
