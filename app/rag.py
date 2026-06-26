from app import gemini_client, store
from app.config import get_settings


def retrieve(query: str, top_k: int | None = None, threshold: float | None = None) -> list[dict]:
    s = get_settings()
    top_k = top_k if top_k is not None else s.rag_top_k
    threshold = threshold if threshold is not None else s.rag_match_threshold

    embedding = gemini_client.embed_text(query, task_type="RETRIEVAL_QUERY")
    return store.search_documents(embedding, threshold, top_k)
