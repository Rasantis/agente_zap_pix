import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.config import Settings


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    s = Settings(
        gemini_api_key="k", meta_access_token="t", meta_phone_number_id="PHONE",
        meta_verify_token="VTOKEN", meta_app_secret="SECRET",
        supabase_url="https://x.supabase.co", supabase_service_key="srv",
        calendly_url="https://calendly.com/e",
    )
    monkeypatch.setattr(main, "get_settings", lambda: s)
    main._seen_ids.clear()

    async def _noop_typing(message_id):
        return None

    monkeypatch.setattr(main.whatsapp, "mark_read_and_typing", _noop_typing)
    return s


def test_verify_returns_challenge():
    client = TestClient(main.app)
    resp = client.get("/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "VTOKEN", "hub.challenge": "12345",
    })
    assert resp.status_code == 200
    assert resp.text == "12345"


def test_verify_wrong_token_403():
    client = TestClient(main.app)
    resp = client.get("/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "ERRADO", "hub.challenge": "12345",
    })
    assert resp.status_code == 403


def test_post_invalid_signature_403():
    client = TestClient(main.app)
    resp = client.post("/webhook", content=b"{}", headers={"X-Hub-Signature-256": "sha256=bad"})
    assert resp.status_code == 403


def test_post_valid_signature_200_and_processes(monkeypatch):
    calls = []

    async def fake_handle(parsed):
        calls.append(parsed)

    monkeypatch.setattr(main, "handle_message", fake_handle)

    body = json.dumps({
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "PHONE"},
            "contacts": [{"profile": {"name": "Ana"}}],
            "messages": [{"from": "5511999", "id": "wamid.X", "type": "text",
                          "text": {"body": "oi"}}],
        }}]}],
    }).encode()
    sig = "sha256=" + hmac.new(b"SECRET", body, hashlib.sha256).hexdigest()

    client = TestClient(main.app)
    resp = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sig})

    assert resp.status_code == 200
    assert len(calls) == 1
    assert calls[0].message_id == "wamid.X"

    # reentrega do mesmo message_id é ignorada (idempotência)
    client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sig})
    assert len(calls) == 1


def test_post_handle_error_sends_fallback(monkeypatch):
    sent = []

    async def boom(parsed):
        raise RuntimeError("gemini fora do ar")

    async def fake_send(to, body):
        sent.append((to, body))

    monkeypatch.setattr(main, "handle_message", boom)
    monkeypatch.setattr(main.whatsapp, "send_text", fake_send)

    body = json.dumps({
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "PHONE"},
            "contacts": [{"profile": {"name": "Ana"}}],
            "messages": [{"from": "5511777", "id": "wamid.ERR", "type": "text",
                          "text": {"body": "oi"}}],
        }}]}],
    }).encode()
    sig = "sha256=" + hmac.new(b"SECRET", body, hashlib.sha256).hexdigest()

    client = TestClient(main.app)
    resp = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sig})

    assert resp.status_code == 200
    assert len(sent) == 1
    assert "instabilidade" in sent[0][1]


def _signed(body: bytes):
    return "sha256=" + hmac.new(b"SECRET", body, hashlib.sha256).hexdigest()


def test_post_audio_sends_fallback(monkeypatch):
    sent = []

    async def fake_send(to, body):
        sent.append((to, body))

    async def _boom(parsed):
        raise AssertionError("handle_message não deve rodar para áudio")

    monkeypatch.setattr(main.whatsapp, "send_text", fake_send)
    monkeypatch.setattr(main, "handle_message", _boom)

    body = json.dumps({
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "PHONE"},
            "contacts": [{"profile": {"name": "Ana"}}],
            "messages": [{"from": "5511999", "id": "wamid.AUD1", "type": "audio",
                          "audio": {"mime_type": "audio/ogg; codecs=opus", "id": "123", "voice": True}}],
        }}]}],
    }).encode()

    client = TestClient(main.app)
    resp = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": _signed(body)})

    assert resp.status_code == 200
    assert len(sent) == 1
    assert "áudio" in sent[0][1] or "udios" in sent[0][1]


def test_post_text_marks_read_and_typing(monkeypatch):
    typed = []

    async def fake_typing(message_id):
        typed.append(message_id)

    async def fake_handle(parsed):
        return None

    monkeypatch.setattr(main.whatsapp, "mark_read_and_typing", fake_typing)
    monkeypatch.setattr(main, "handle_message", fake_handle)

    body = json.dumps({
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "PHONE"},
            "contacts": [{"profile": {"name": "Ana"}}],
            "messages": [{"from": "5511999", "id": "wamid.TYP1", "type": "text",
                          "text": {"body": "oi"}}],
        }}]}],
    }).encode()

    client = TestClient(main.app)
    resp = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": _signed(body)})

    assert resp.status_code == 200
    assert typed == ["wamid.TYP1"]


def test_post_typing_failure_does_not_block(monkeypatch):
    handled = []

    async def broken_typing(message_id):
        raise RuntimeError("graph fora do ar")

    async def fake_handle(parsed):
        handled.append(parsed.message_id)

    monkeypatch.setattr(main.whatsapp, "mark_read_and_typing", broken_typing)
    monkeypatch.setattr(main, "handle_message", fake_handle)

    body = json.dumps({
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "PHONE"},
            "contacts": [{"profile": {"name": "Ana"}}],
            "messages": [{"from": "5511999", "id": "wamid.TYP2", "type": "text",
                          "text": {"body": "oi"}}],
        }}]}],
    }).encode()

    client = TestClient(main.app)
    resp = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": _signed(body)})

    assert resp.status_code == 200
    assert handled == ["wamid.TYP2"]
