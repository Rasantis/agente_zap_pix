import app.gemini_client as gc
from app.config import Settings
from app.models import TurnResult


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
            captured["system"] = config.system_instruction
            return type("R", (), {"parsed": TurnResult(resposta="olá", acao="continuar")})()

    class _Client:
        models = _Models()

    monkeypatch.setattr(gc, "get_settings", _settings)
    monkeypatch.setattr(gc, "_client", lambda: _Client())

    out = gc.generate_turn(
        history=[{"role": "user", "content": "oi"}, {"role": "model", "content": "olá!"}],
        context=["Trecho"],
        lead_data={"nome": "Ana"},
        message="vocês fazem site?",
    )

    assert isinstance(out, TurnResult)
    assert out.resposta == "olá"
    assert captured["model"] == "gemini-2.5-flash"
    # histórico (2) + turno atual (1) = 3 mensagens
    assert len(captured["contents"]) == 3
