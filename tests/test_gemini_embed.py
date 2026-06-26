import math

import app.gemini_client as gc
from app.config import Settings


def _settings():
    return Settings(
        gemini_api_key="k", meta_access_token="t", meta_phone_number_id="1",
        meta_verify_token="v", meta_app_secret="s", supabase_url="https://x.supabase.co",
        supabase_service_key="srv", calendly_url="https://calendly.com/e",
    )


def test_l2_normalize():
    assert gc._l2_normalize([3.0, 4.0]) == [0.6, 0.8]


def test_l2_normalize_zero_vector():
    assert gc._l2_normalize([0.0, 0.0]) == [0.0, 0.0]


def test_embed_text_calls_api_and_normalizes(monkeypatch):
    class _Emb:
        values = [3.0, 4.0]

    class _Resp:
        embeddings = [_Emb()]

    class _Models:
        def embed_content(self, model, contents, config):
            assert model == "gemini-embedding-001"
            assert config.output_dimensionality == 768
            assert config.task_type == "RETRIEVAL_QUERY"
            return _Resp()

    class _Client:
        models = _Models()

    monkeypatch.setattr(gc, "get_settings", _settings)
    monkeypatch.setattr(gc, "_client", lambda: _Client())

    out = gc.embed_text("oi", task_type="RETRIEVAL_QUERY")
    assert math.isclose(out[0], 0.6) and math.isclose(out[1], 0.8)
