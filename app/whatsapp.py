import hashlib
import hmac

import httpx

from app.config import get_settings
from app.models import ParsedMessage


IGNORED_TYPES = ("reaction",)  # reações (👍 etc.) não merecem resposta


def parse_incoming(payload: dict) -> ParsedMessage | None:
    try:
        value = payload["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError, TypeError):
        return None

    if not isinstance(value, dict):
        return None

    messages = value.get("messages")
    if not messages:
        return None

    msg = messages[0]
    msg_type = msg.get("type") or ""
    if not msg_type or msg_type in IGNORED_TYPES:
        return None

    contacts = value.get("contacts") or [{}]
    name = contacts[0].get("profile", {}).get("name", "")

    try:
        message_id = msg["id"]
        from_phone = msg["from"]
        phone_number_id = value["metadata"]["phone_number_id"]
    except (KeyError, TypeError):
        return None

    text = ""
    if msg_type == "text":
        text = (msg.get("text") or {}).get("body", "")
        if not text:
            return None  # texto sem body = malformado

    return ParsedMessage(message_id, from_phone, name, text, phone_number_id, msg_type)


def verify_signature(raw_body: bytes, signature_header: str | None, app_secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


async def send_text(to: str, body: str) -> None:
    s = get_settings()
    url = f"https://graph.facebook.com/{s.meta_graph_version}/{s.meta_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {s.meta_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": True, "body": body},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()


async def mark_read_and_typing(message_id: str) -> None:
    """Marca a mensagem recebida como lida (ticks azuis) e exibe 'digitando...'."""
    s = get_settings()
    url = f"https://graph.facebook.com/{s.meta_graph_version}/{s.meta_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {s.meta_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
        "typing_indicator": {"type": "text"},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
