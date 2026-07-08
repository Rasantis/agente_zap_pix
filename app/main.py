import logging
from collections import OrderedDict

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app import whatsapp
from app.config import get_settings
from app.orchestrator import handle_message

app = FastAPI()
logger = logging.getLogger("agente_zap")

FALLBACK_MSG = "Tive uma instabilidade aqui do meu lado. Pode mandar a mensagem de novo, por favor?"
FALLBACK_AUDIO = "Ainda não consigo ouvir áudios por aqui. Pode me escrever, por favor?"
FALLBACK_UNSUPPORTED = "Por enquanto eu só consigo ler mensagens de texto. Pode escrever pra mim, por favor?"

_seen_ids: "OrderedDict[str, None]" = OrderedDict()
_SEEN_MAX = 1000


def _already_seen(message_id: str) -> bool:
    if message_id in _seen_ids:
        return True
    _seen_ids[message_id] = None
    if len(_seen_ids) > _SEEN_MAX:
        _seen_ids.popitem(last=False)
    return False


@app.get("/webhook")
def verify(request: Request):
    s = get_settings()
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == s.meta_verify_token:
        return PlainTextResponse(p.get("hub.challenge"))
    return PlainTextResponse("forbidden", status_code=403)


async def process_event(payload: dict) -> None:
    parsed = whatsapp.parse_incoming(payload)
    if parsed is None:
        return
    if _already_seen(parsed.message_id):
        return
    try:
        await whatsapp.mark_read_and_typing(parsed.message_id)
    except Exception:
        logger.warning("Indicador de digitação falhou para %s", parsed.message_id)
    if parsed.msg_type != "text":
        msg = FALLBACK_AUDIO if parsed.msg_type == "audio" else FALLBACK_UNSUPPORTED
        try:
            await whatsapp.send_text(parsed.from_phone, msg)
        except Exception:
            logger.exception("Falha ao enviar fallback de mídia para %s", parsed.from_phone)
        return
    try:
        await handle_message(parsed)
    except Exception:
        logger.exception("Falha ao processar mensagem %s", parsed.message_id)
        try:
            await whatsapp.send_text(parsed.from_phone, FALLBACK_MSG)
        except Exception:
            logger.exception("Falha ao enviar fallback para %s", parsed.from_phone)


@app.post("/webhook")
async def receive(request: Request, background_tasks: BackgroundTasks):
    s = get_settings()
    raw = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not whatsapp.verify_signature(raw, signature, s.meta_app_secret):
        return JSONResponse({"error": "invalid signature"}, status_code=403)

    payload = await request.json()
    background_tasks.add_task(process_event, payload)
    return PlainTextResponse("ok")
