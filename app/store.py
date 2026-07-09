from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def _supabase() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_key)


def merge_lead_data(existing: dict, updates: dict) -> dict:
    merged = dict(existing or {})
    for key, value in (updates or {}).items():
        if value:
            merged[key] = value
    return merged


def get_conversation(phone: str) -> dict | None:
    res = _supabase().table("conversations").select("*").eq("phone", phone).limit(1).execute()
    return res.data[0] if res.data else None


def upsert_conversation(phone: str, messages: list, lead_data: dict, lead_id: int | None) -> dict:
    row = {"phone": phone, "messages": messages, "lead_data": lead_data, "lead_id": lead_id}
    res = _supabase().table("conversations").upsert(row, on_conflict="phone").execute()
    return res.data[0] if res.data else {}


def create_or_update_lead(
    conversation: dict | None,
    lead_data: dict,
    classificacao: dict,
    telefone: str,
) -> int:
    payload = {
        "nome": lead_data.get("nome"),
        "telefone": telefone,
        "empresa": lead_data.get("empresa"),
        "necessidade": lead_data.get("necessidade"),
        "etiqueta": (classificacao or {}).get("etiqueta"),
        "tema": (classificacao or {}).get("tema"),
        "status": "link_enviado",
    }
    existing_id = (conversation or {}).get("lead_id")
    sb = _supabase()
    if existing_id:
        sb.table("leads").update(payload).eq("id", existing_id).execute()
        return existing_id
    res = sb.table("leads").insert(payload).execute()
    return res.data[0]["id"]


def search_documents(embedding: list[float], threshold: float, count: int) -> list[dict]:
    res = _supabase().rpc(
        "match_documents",
        {"query_embedding": embedding, "match_threshold": threshold, "match_count": count},
    ).execute()
    return res.data or []


def insert_document(content: str, metadata: dict, embedding: list[float]) -> None:
    _supabase().table("documents").insert(
        {"content": content, "metadata": metadata, "embedding": embedding}
    ).execute()


def clear_documents() -> None:
    _supabase().table("documents").delete().neq("id", 0).execute()


def log_error(source: str, message_id: str, tb: str) -> None:
    """Grava o traceback em error_logs (visível via MCP, sem depender do painel do host)."""
    _supabase().table("error_logs").insert(
        {"source": source, "message_id": message_id, "traceback": tb}
    ).execute()
