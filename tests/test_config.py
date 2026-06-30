from app.config import Settings


def test_settings_has_expected_defaults():
    s = Settings(
        gemini_api_key="k",
        meta_access_token="t",
        meta_phone_number_id="123",
        meta_verify_token="v",
        meta_app_secret="sec",
        supabase_url="https://x.supabase.co",
        supabase_service_key="srv",
        calendly_url="https://calendly.com/empresa",
    )
    assert s.meta_graph_version == "v23.0"
    assert s.chat_model == "gemini-2.5-flash"
    assert s.embedding_model == "gemini-embedding-001"
    assert s.embedding_dim == 768
    assert s.rag_top_k == 5
    assert s.rag_match_threshold == 0.6
    assert s.history_max_messages == 20


def test_pending_creds_are_optional():
    # app precisa subir e verificar o webhook antes do access token chegar
    s = Settings(
        _env_file=None,
        gemini_api_key="k",
        meta_phone_number_id="123",
        meta_verify_token="v",
        meta_app_secret="sec",
        supabase_url="https://x.supabase.co",
        supabase_service_key="srv",
    )
    assert s.meta_access_token == ""
    assert s.calendly_url == ""
