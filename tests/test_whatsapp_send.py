import pytest

import app.whatsapp as wa
from app.config import Settings


class _FakeResp:
    def __init__(self):
        self.calls = []

    def raise_for_status(self):
        return None


class _FakeClient:
    def __init__(self, sink):
        self.sink = sink

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        self.sink["url"] = url
        self.sink["headers"] = headers
        self.sink["json"] = json
        return _FakeResp()


@pytest.mark.asyncio
async def test_send_text_posts_to_graph_api(monkeypatch):
    sink = {}
    monkeypatch.setattr(wa, "get_settings", lambda: Settings(
        gemini_api_key="k", meta_access_token="TOK", meta_phone_number_id="PHONE",
        meta_verify_token="v", meta_app_secret="s", supabase_url="https://x.supabase.co",
        supabase_service_key="srv", calendly_url="https://calendly.com/e",
    ))
    monkeypatch.setattr(wa.httpx, "AsyncClient", lambda *a, **k: _FakeClient(sink))

    await wa.send_text("16505551234", "Olá!")

    assert sink["url"] == "https://graph.facebook.com/v23.0/PHONE/messages"
    assert sink["headers"]["Authorization"] == "Bearer TOK"
    assert sink["json"]["to"] == "16505551234"
    assert sink["json"]["text"]["body"] == "Olá!"
    assert sink["json"]["type"] == "text"
