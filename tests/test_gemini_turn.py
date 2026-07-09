import pytest

import app.gemini_client as gc
from app import prompts
from app.config import Settings
from app.models import TurnResult, TurnResultWire


def _settings():
    return Settings(
        gemini_api_key="k", meta_access_token="t", meta_phone_number_id="1",
        meta_verify_token="v", meta_app_secret="s", supabase_url="https://x.supabase.co",
        supabase_service_key="srv", calendly_url="https://calendly.com/e",
    )


def test_generate_turn_returns_parsed(monkeypatch):
    captured = {}

    class _Models:
        def generate_content(self, model, contents, config):
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config
            captured["system"] = config.system_instruction
            wire = TurnResultWire(
                resposta="olá",
                dados_lead={"nome": None, "empresa": None, "necessidade": None},
                classificacao={"etiqueta": "morno", "tema": ""},
                acao="continuar",
            )
            return type("R", (), {"parsed": wire})()

    class _Client:
        models = _Models()

    monkeypatch.setattr(gc, "get_settings", _settings)
    monkeypatch.setattr(gc, "_client", lambda: _Client())

    out = gc.generate_turn(
        history=[{"role": "user", "content": "oi"}, {"role": "model", "content": "olá!"}],
        context=["Trecho"],
        lead_data={"nome": "Ana"},
        message="vocês fazem site?",
        contact_name="Marcos",
        link_ja_enviado=True,
    )

    assert isinstance(out, TurnResult)
    assert out.resposta == "olá"
    assert captured["model"] == _settings().chat_model
    assert captured["config"].system_instruction == prompts.SYSTEM_INSTRUCTION
    assert captured["config"].temperature == 0.6
    assert captured["config"].response_mime_type == "application/json"
    assert captured["config"].response_schema is TurnResultWire
    # histórico (2) + turno atual (1) = 3 mensagens
    assert len(captured["contents"]) == 3
    assert "Marcos" in captured["contents"][-1].parts[0].text
    assert "JÁ FOI ENVIADO" in captured["contents"][-1].parts[0].text


def test_generate_turn_raises_when_parsed_none(monkeypatch):
    class _Models:
        def generate_content(self, model, contents, config):
            return type("R", (), {"parsed": None})()

    class _Client:
        models = _Models()

    monkeypatch.setattr(gc, "get_settings", _settings)
    monkeypatch.setattr(gc, "_client", lambda: _Client())

    with pytest.raises(ValueError):
        gc.generate_turn([], [], {}, "oi")


def test_wire_schema_has_no_defaults():
    # regressão do bug de produção: a API do Gemini rejeita "default" no response_schema
    import json

    schema = json.dumps(TurnResultWire.model_json_schema())
    assert '"default"' not in schema
