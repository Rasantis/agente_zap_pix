import pytest

import app.orchestrator as orch
from app.config import Settings
from app.models import ParsedMessage, TurnResult


def _settings():
    return Settings(
        gemini_api_key="k", meta_access_token="t", meta_phone_number_id="1",
        meta_verify_token="v", meta_app_secret="s", supabase_url="https://x.supabase.co",
        supabase_service_key="srv", calendly_url="https://calendly.com/empresa",
    )


def test_should_send_calendly_by_action():
    assert orch.should_send_calendly({}, "mandar_calendly") is True


def test_should_send_calendly_by_fields():
    assert orch.should_send_calendly({"nome": "Ana", "necessidade": "site"}, "continuar") is True


def test_should_not_send_when_incomplete():
    assert orch.should_send_calendly({"nome": "Ana"}, "continuar") is False


@pytest.mark.asyncio
async def test_handle_message_sends_link_when_ready(monkeypatch):
    sent = []

    monkeypatch.setattr(orch, "get_settings", _settings)
    monkeypatch.setattr(orch.store, "get_conversation", lambda phone: None)
    monkeypatch.setattr(orch.rag, "retrieve", lambda text: [{"content": "doc"}])
    monkeypatch.setattr(
        orch.gemini_client, "generate_turn",
        lambda history, context, lead_data, message: TurnResult(
            resposta="Boa! Vamos agendar?",
            dados_lead={"nome": "Ana", "necessidade": "site"},
            classificacao={"etiqueta": "quente", "tema": "site"},
            acao="mandar_calendly",
        ),
    )
    monkeypatch.setattr(orch.store, "create_or_update_lead", lambda *a, **k: 7)
    monkeypatch.setattr(orch.store, "upsert_conversation", lambda *a, **k: {})

    async def fake_send(to, body):
        sent.append((to, body))

    monkeypatch.setattr(orch.whatsapp, "send_text", fake_send)

    await orch.handle_message(ParsedMessage("wamid.1", "5511999", "Ana", "quero um site", "PHONE"))

    # 1ª: resposta do bot; 2ª: link do Calendly
    assert len(sent) == 2
    assert "calendly.com/empresa" in sent[1][1]


@pytest.mark.asyncio
async def test_handle_message_no_link_when_incomplete(monkeypatch):
    sent = []

    monkeypatch.setattr(orch, "get_settings", _settings)
    monkeypatch.setattr(orch.store, "get_conversation", lambda phone: None)
    monkeypatch.setattr(orch.rag, "retrieve", lambda text: [])
    monkeypatch.setattr(
        orch.gemini_client, "generate_turn",
        lambda history, context, lead_data, message: TurnResult(resposta="Como posso ajudar?"),
    )

    def _fail(*a, **k):
        raise AssertionError("não deveria criar lead")

    monkeypatch.setattr(orch.store, "create_or_update_lead", _fail)
    monkeypatch.setattr(orch.store, "upsert_conversation", lambda *a, **k: {})

    async def fake_send(to, body):
        sent.append((to, body))

    monkeypatch.setattr(orch.whatsapp, "send_text", fake_send)

    await orch.handle_message(ParsedMessage("wamid.2", "5511888", "X", "oi", "PHONE"))

    assert len(sent) == 1
