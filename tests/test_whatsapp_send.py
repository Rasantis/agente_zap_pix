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


@pytest.mark.asyncio
async def test_mark_read_and_typing_posts_status(monkeypatch):
    sink = {}
    monkeypatch.setattr(wa, "get_settings", lambda: Settings(
        gemini_api_key="k", meta_access_token="TOK", meta_phone_number_id="PHONE",
        meta_verify_token="v", meta_app_secret="s", supabase_url="https://x.supabase.co",
        supabase_service_key="srv", calendly_url="https://calendly.com/e",
    ))
    monkeypatch.setattr(wa.httpx, "AsyncClient", lambda *a, **k: _FakeClient(sink))

    await wa.mark_read_and_typing("wamid.ABC")

    assert sink["url"] == "https://graph.facebook.com/v23.0/PHONE/messages"
    assert sink["json"]["status"] == "read"
    assert sink["json"]["message_id"] == "wamid.ABC"
    assert sink["json"]["typing_indicator"] == {"type": "text"}


@pytest.mark.asyncio
async def test_download_media_two_steps(monkeypatch):
    calls = []

    class _Resp:
        def __init__(self, json_data=None, content=b""):
            self._json = json_data
            self.content = content

        def raise_for_status(self):
            return None

        def json(self):
            return self._json

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            calls.append((url, headers))
            if "graph.facebook.com" in url:
                return _Resp(json_data={
                    "url": "https://mmg.whatsapp.net/arquivo-temporario",
                    "mime_type": "audio/ogg; codecs=opus",
                })
            return _Resp(content=b"BYTES-DO-AUDIO")

    monkeypatch.setattr(wa, "get_settings", lambda: Settings(
        gemini_api_key="k", meta_access_token="TOK", meta_phone_number_id="PHONE",
        meta_verify_token="v", meta_app_secret="s", supabase_url="https://x.supabase.co",
        supabase_service_key="srv", calendly_url="https://calendly.com/e",
    ))
    monkeypatch.setattr(wa.httpx, "AsyncClient", _Client)

    content, mime = await wa.download_media("1908647269898587")

    assert content == b"BYTES-DO-AUDIO"
    assert mime == "audio/ogg"  # parâmetros (;codecs=opus) removidos
    assert calls[0][0] == "https://graph.facebook.com/v23.0/1908647269898587"
    assert calls[0][1]["Authorization"] == "Bearer TOK"
    assert calls[1][0] == "https://mmg.whatsapp.net/arquivo-temporario"
    assert calls[1][1]["Authorization"] == "Bearer TOK"  # o download exige o MESMO token
