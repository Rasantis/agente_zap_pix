from app import gemini_client, rag, scheduling, store, whatsapp
from app.config import get_settings
from app.models import ParsedMessage

REQUIRED_FIELDS = ("nome", "necessidade")


def should_send_calendly(lead_data: dict, acao: str) -> bool:
    if acao == "mandar_calendly":
        return True
    return all((lead_data or {}).get(field) for field in REQUIRED_FIELDS)


async def handle_message(parsed: ParsedMessage) -> None:
    s = get_settings()

    conv = store.get_conversation(parsed.from_phone) or {}
    history = conv.get("messages", [])
    lead_data = conv.get("lead_data", {})

    context_rows = rag.retrieve(parsed.text)
    context = [r.get("content", "") for r in context_rows]

    turn = gemini_client.generate_turn(history, context, lead_data, parsed.text)

    lead_data = store.merge_lead_data(lead_data, turn.dados_lead.model_dump())

    new_history = (history + [
        {"role": "user", "content": parsed.text},
        {"role": "model", "content": turn.resposta},
    ])[-s.history_max_messages:]

    send_link = should_send_calendly(lead_data, turn.acao)
    lead_id = conv.get("lead_id")
    if send_link:
        lead_id = store.create_or_update_lead(
            conv, lead_data, turn.classificacao.model_dump(), parsed.from_phone
        )

    store.upsert_conversation(parsed.from_phone, new_history, lead_data, lead_id)

    await whatsapp.send_text(parsed.from_phone, turn.resposta)
    if send_link:
        await whatsapp.send_text(
            parsed.from_phone, scheduling.build_calendly_message(lead_data, s.calendly_url)
        )
