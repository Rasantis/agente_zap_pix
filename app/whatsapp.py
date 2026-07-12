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

    media_id = ""
    if msg_type == "audio":
        media_id = (msg.get("audio") or {}).get("id", "")

    return ParsedMessage(message_id, from_phone, name, text, phone_number_id, msg_type, media_id)


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


async def download_media(media_id: str) -> tuple[bytes, str]:
    """Baixa uma mídia recebida (2 passos: id -> URL temporária -> binário).

    A URL retornada pela Meta expira em ~5 minutos e exige o mesmo Bearer token.
    Retorna (conteúdo, mime_type sem parâmetros — ex.: 'audio/ogg').
    """
    s = get_settings()
    headers = {"Authorization": f"Bearer {s.meta_access_token}"}
    async with httpx.AsyncClient(timeout=60) as client:
        meta = await client.get(
            f"https://graph.facebook.com/{s.meta_graph_version}/{media_id}", headers=headers
        )
        meta.raise_for_status()
        info = meta.json()
        arquivo = await client.get(info["url"], headers=headers)
        arquivo.raise_for_status()
        mime = (info.get("mime_type") or "application/octet-stream").split(";")[0].strip()
        return arquivo.content, mime


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
