import hashlib
import re


def normalize_message_body(message_body: str) -> str:
    return re.sub(r"\s+", " ", message_body.strip().lower())


def calculate_body_hash(message_body: str) -> str:
    normalized_body = normalize_message_body(message_body)
    return hashlib.sha256(normalized_body.encode("utf-8")).hexdigest()
