import math

from google import genai
from google.genai import types

from app import prompts
from app.config import get_settings
from app.models import TurnResult, TurnResultWire


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


def transcribe_audio(audio_bytes: bytes, mime_type: str) -> str:
    """Transcreve uma voice note (áudio inline ≤ 20 MB) usando o próprio Gemini."""
    s = get_settings()
    resp = _client().models.generate_content(
        model=s.chat_model,
        contents=[
            "Transcreva este áudio em português do Brasil. "
            "Retorne APENAS o texto falado, sem comentários nem formatação.",
            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
        ],
    )
    return (resp.text or "").strip()


def generate_turn(
    history: list[dict],
    context: list[str],
    lead_data: dict,
    message: str,
    contact_name: str = "",
    link_ja_enviado: bool = False,
) -> TurnResult:
    s = get_settings()
    user_turn = prompts.build_user_turn(context, lead_data, message, contact_name, link_ja_enviado)

    contents = []
    for m in history:
        role = "user" if m.get("role") == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=m.get("content", ""))]))
    contents.append(types.Content(role="user", parts=[types.Part(text=user_turn)]))

    resp = _client().models.generate_content(
        model=s.chat_model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=prompts.SYSTEM_INSTRUCTION,
            temperature=0.6,
            response_mime_type="application/json",
            # o schema "wire" não tem defaults: a API do Gemini rejeita defaults
            response_schema=TurnResultWire,
        ),
    )
    wire = resp.parsed
    if wire is None:
        raise ValueError("Gemini não retornou JSON parseável para o turno")
    return TurnResult(**wire.model_dump())
