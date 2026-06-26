import math

from google import genai
from google.genai import types

from app.config import get_settings


def _client() -> genai.Client:
    return genai.Client(api_key=get_settings().gemini_api_key)


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


def embed_text(text: str, task_type: str) -> list[float]:
    s = get_settings()
    resp = _client().models.embed_content(
        model=s.embedding_model,
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=s.embedding_dim,
            task_type=task_type,
        ),
    )
    return _l2_normalize(list(resp.embeddings[0].values))
