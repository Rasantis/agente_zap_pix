from app.scheduling import build_calendly_message


def test_message_includes_url_and_name():
    msg = build_calendly_message({"nome": "Ana"}, "https://calendly.com/empresa")
    assert "https://calendly.com/empresa" in msg
    assert "Ana" in msg


def test_message_without_name():
    msg = build_calendly_message({}, "https://calendly.com/empresa")
    assert "https://calendly.com/empresa" in msg
