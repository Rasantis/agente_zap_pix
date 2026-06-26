import hashlib
import hmac

import httpx

from app.config import get_settings
from app.models import ParsedMessage


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
    if msg.get("type") != "text":
        return None

    contacts = value.get("contacts") or [{}]
    name = contacts[0].get("profile", {}).get("name", "")

    return ParsedMessage(
        message_id=msg["id"],
        from_phone=msg["from"],
        contact_name=name,
        text=msg["text"]["body"],
        phone_number_id=value["metadata"]["phone_number_id"],
    )


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
