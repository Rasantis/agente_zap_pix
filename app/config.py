from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str
    meta_access_token: str
    meta_phone_number_id: str
    meta_verify_token: str
    meta_app_secret: str
    meta_graph_version: str = "v23.0"
    supabase_url: str
    supabase_service_key: str
    calendly_url: str
    chat_model: str = "gemini-2.5-flash"
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 768
    rag_top_k: int = 5
    rag_match_threshold: float = 0.6
    history_max_messages: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
