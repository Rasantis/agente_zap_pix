from app.config import Settings
import app.rag as rag


def _settings():
    return Settings(
        gemini_api_key="k", meta_access_token="t", meta_phone_number_id="1",
        meta_verify_token="v", meta_app_secret="s", supabase_url="https://x.supabase.co",
        supabase_service_key="srv", calendly_url="https://calendly.com/e",
    )


def test_retrieve_embeds_query_and_searches(monkeypatch):
    captured = {}

    def fake_embed(text, task_type):
        captured["text"] = text
        captured["task_type"] = task_type
        return [0.1, 0.2]

    def fake_search(embedding, threshold, count):
        captured["embedding"] = embedding
        captured["threshold"] = threshold
        captured["count"] = count
        return [{"content": "doc1", "metadata": {}}]

    monkeypatch.setattr(rag, "get_settings", _settings)
    monkeypatch.setattr(rag.gemini_client, "embed_text", fake_embed)
    monkeypatch.setattr(rag.store, "search_documents", fake_search)

    out = rag.retrieve("vocês fazem site?", top_k=3, threshold=0.5)

    assert captured["task_type"] == "RETRIEVAL_QUERY"
    assert captured["embedding"] == [0.1, 0.2]
    assert captured["count"] == 3
    assert captured["threshold"] == 0.5
    assert out == [{"content": "doc1", "metadata": {}}]
