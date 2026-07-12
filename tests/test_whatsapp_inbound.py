import hmac
import hashlib

from app.whatsapp import parse_incoming, verify_signature

TEXT_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [{
        "id": "102290129340398",
        "changes": [{
            "field": "messages",
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {"display_phone_number": "15550783881", "phone_number_id": "106540352242922"},
                "contacts": [{"profile": {"name": "Sheena Nelson"}, "wa_id": "16505551234"}],
                "messages": [{
                    "from": "16505551234",
                    "id": "wamid.HBgLM",
                    "timestamp": "1749416383",
                    "type": "text",
                    "text": {"body": "Vocês entregam no sábado?"},
                }],
            },
        }],
    }],
}

STATUS_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [{"changes": [{"value": {"statuses": [{"status": "delivered"}]}}]}],
}

IMAGE_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [{
        "changes": [{
            "field": "messages",
            "value": {
                "metadata": {"phone_number_id": "106540352242922"},
                "contacts": [{"profile": {"name": "Ana"}, "wa_id": "16505551234"}],
                "messages": [{
                    "from": "16505551234",
                    "id": "wamid.IMG",
                    "type": "image",
                    "image": {"id": "media-123"},
                }],
            },
        }],
    }],
}


def test_parse_incoming_text():
    m = parse_incoming(TEXT_PAYLOAD)
    assert m is not None
    assert m.message_id == "wamid.HBgLM"
    assert m.from_phone == "16505551234"
    assert m.contact_name == "Sheena Nelson"
    assert m.text == "Vocês entregam no sábado?"
    assert m.phone_number_id == "106540352242922"
    assert m.msg_type == "text"


def test_parse_incoming_status_returns_none():
    assert parse_incoming(STATUS_PAYLOAD) is None


def test_parse_incoming_malformed_returns_none():
    assert parse_incoming({}) is None


def test_parse_incoming_image_returns_msg_type():
    m = parse_incoming(IMAGE_PAYLOAD)
    assert m is not None
    assert m.msg_type == "image"
    assert m.text == ""
    assert m.message_id == "wamid.IMG"


AUDIO_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [{
        "changes": [{
            "field": "messages",
            "value": {
                "metadata": {"phone_number_id": "106540352242922"},
                "contacts": [{"profile": {"name": "Ana"}, "wa_id": "16505551234"}],
                "messages": [{
                    "from": "16505551234",
                    "id": "wamid.AUDIO",
                    "type": "audio",
                    "audio": {"mime_type": "audio/ogg; codecs=opus", "id": "1908647269898587", "voice": True},
                }],
            },
        }],
    }],
}


def test_parse_incoming_audio_returns_msg_type():
    m = parse_incoming(AUDIO_PAYLOAD)
    assert m is not None
    assert m.msg_type == "audio"
    assert m.text == ""
    assert m.media_id == "1908647269898587"


def test_parse_incoming_reaction_ignored():
    payload = {
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "1"},
            "messages": [{"from": "1", "id": "wamid.R", "type": "reaction",
                          "reaction": {"message_id": "wamid.X", "emoji": "👍"}}],
        }}]}],
    }
    assert parse_incoming(payload) is None


def test_parse_incoming_value_not_dict_returns_none():
    assert parse_incoming({"entry": [{"changes": [{"value": [1, 2, 3]}]}]}) is None


def test_verify_signature_ok():
    secret = "minha_app_secret"
    body = b'{"hello":"world"}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(body, sig, secret) is True


def test_verify_signature_bad():
    assert verify_signature(b"x", "md5=deadbeef", "secret") is False
    assert verify_signature(b"x", "sha256=deadbeef", "secret") is False
    assert verify_signature(b"x", None, "secret") is False
