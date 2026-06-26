import math

from google import genai
from google.genai import types

from app import prompts
from app.config import get_settings
from app.models import TurnResult


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


def generate_turn(
    history: list[dict],
    context: list[str],
    lead_data: dict,
    message: str,
) -> TurnResult:
    s = get_settings()
    user_turn = prompts.build_user_turn(context, lead_data, message)

    contents = []
    for m in history:
        role = "user" if m.get("role") == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=m["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=user_turn)]))

    resp = _client().models.generate_content(
        model=s.chat_model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=prompts.SYSTEM_INSTRUCTION,
            temperature=0.3,
            response_mime_type="application/json",
            response_schema=TurnResult,
        ),
    )
    return resp.parsed
