import email
import imaplib
import os
from email.message import Message
from email.utils import parsedate_to_datetime

from dotenv import load_dotenv

load_dotenv()


def _decode_part(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")


def _extract_message_body(message: Message) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() != "text/plain":
                continue
            if part.get_content_disposition() == "attachment":
                continue
            body = _decode_part(part)
            if body:
                return body
        return ""

    return _decode_part(message)


def fetch_emails(app_password: str | None = None) -> list[dict]:
    """Fetch transaction emails without persisting or deduplicating them."""
    password = app_password or os.getenv("APP_PASSWORD")
    if not password:
        raise RuntimeError("APP_PASSWORD is required to fetch emails.")

    emails: list[dict] = []
    try:
        with imaplib.IMAP4_SSL("imap.gmail.com", 993) as mail:
            mail.login("gappihertzd@gmail.com", password)
            mail.select("INBOX")

            status, data = mail.search(None, "SUBJECT", "gastos")
            if status != "OK":
                raise RuntimeError("Unable to search the Gmail inbox.")

            for message_number in data[0].split():
                status, message_data = mail.fetch(message_number, "(RFC822)")
                if status != "OK" or not message_data or message_data[0] is None:
                    continue

                raw_email = message_data[0][1]
                message = email.message_from_bytes(raw_email)
                message_id = message.get("Message-Id")
                message_date = message.get("Date")
                body = _extract_message_body(message)

                if not message_id or not message_date or not body:
                    continue

                emails.append(
                    {
                        "id": message_id,
                        "date": parsedate_to_datetime(message_date).date(),
                        "content": body,
                    }
                )
    except imaplib.IMAP4.error as error:
        raise RuntimeError("Unable to fetch Gmail messages.") from error

    return emails
