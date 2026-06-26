# Agente de WhatsApp (Qualificador + Agendador com RAG) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir um bot de WhatsApp (Meta Cloud API) em Python/FastAPI que responde dúvidas via RAG (Gemini + Supabase/pgvector), qualifica o lead com coleta leve, classifica (quente/morno/frio + tema) e sempre encaminha para agendamento enviando o link do Calendly.

**Architecture:** Serviço único FastAPI. O webhook valida a assinatura da Meta, responde 200 na hora e processa em background. Cada turno faz 1 chamada ao Gemini com saída estruturada (JSON) que devolve resposta + dados do lead extraídos + classificação + ação. RAG via embeddings Gemini (768 dims) e busca de similaridade por cosseno no Supabase. Ingestão da base de conhecimento é um CLI offline separado.

**Tech Stack:** Python 3.11+, FastAPI, httpx, `google-genai`, `supabase` (supabase-py), `pydantic-settings`, `pypdf`, `python-docx`, `pytest`, `pytest-asyncio`.

## Global Constraints

- **SDK do Gemini:** usar `google-genai` (`from google import genai`). NÃO usar `google-generativeai` (descontinuado).
- **Modelo de chat:** `gemini-2.5-flash`. **Modelo de embeddings:** `gemini-embedding-001`.
- **Embeddings:** dimensão fixa **768** (`output_dimensionality=768`), **sempre normalizados L2**. Coluna Postgres `extensions.vector(768)`. Mesma dimensão na ingestão (`task_type="RETRIEVAL_DOCUMENT"`) e na consulta (`task_type="RETRIEVAL_QUERY"`).
- **Meta Graph API:** versão `v23.0`. Endpoint de envio `POST https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/messages`.
- **Webhook:** GET responde `hub.challenge` em texto puro quando `hub.verify_token` confere; POST valida `X-Hub-Signature-256` (HMAC-SHA256 com App Secret) e **responde 200 rápido**, processando em background.
- **Idempotência:** ignorar mensagens com `message_id` já visto.
- **Segredos:** sempre via `.env` (nunca versionado). `.env.example` versionado.
- **Idioma das mensagens ao cliente:** português do Brasil, tom de WhatsApp (curto).
- **Campos mínimos para agendar:** `nome` + `necessidade` (empresa é desejável, não bloqueante).
- **Anti-alucinação:** responder dúvidas apenas com base no contexto do RAG; sem contexto, dizer que vai confirmar com um humano.
- **TDD, DRY, YAGNI, commits frequentes.** Cada tarefa termina com um deliverable testável.

**Estrutura de arquivos (decomposição):**

```
agente_zap/
├─ app/
│  ├─ __init__.py
│  ├─ config.py        # get_settings() — pydantic-settings
│  ├─ models.py        # ParsedMessage (dataclass) + TurnResult/DadosLead/Classificacao (pydantic)
│  ├─ whatsapp.py      # parse_incoming() · verify_signature() · send_text()
│  ├─ prompts.py       # SYSTEM_INSTRUCTION · build_user_turn()
│  ├─ gemini_client.py # embed_text() · generate_turn()
│  ├─ store.py         # acesso ao Supabase (conversations, leads, documents) + merge_lead_data()
│  ├─ rag.py           # retrieve()
│  ├─ scheduling.py    # build_calendly_message()
│  ├─ orchestrator.py  # should_send_calendly() · handle_message()
│  └─ main.py          # FastAPI: GET/POST /webhook
├─ ingest/
│  ├─ __init__.py
│  ├─ chunker.py       # chunk_text()
│  └─ ingest.py        # load_documents() · ingest() · CLI
├─ db/
│  └─ schema.sql
├─ tests/
│  ├─ __init__.py
│  └─ test_*.py
├─ .env.example
├─ requirements.txt
└─ README.md
```

---

### Task 1: Scaffolding do projeto + configuração

**Files:**
- Create: `requirements.txt`, `.gitignore`, `app/__init__.py`, `tests/__init__.py`, `pytest.ini`, `app/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `app.config.Settings` (pydantic settings) e `app.config.get_settings() -> Settings` (com `@lru_cache`). Campos: `gemini_api_key, meta_access_token, meta_phone_number_id, meta_verify_token, meta_app_secret, meta_graph_version="v23.0", supabase_url, supabase_service_key, calendly_url, chat_model="gemini-2.5-flash", embedding_model="gemini-embedding-001", embedding_dim=768, rag_top_k=5, rag_match_threshold=0.6, history_max_messages=20`.

- [ ] **Step 1: Inicializar git e estrutura**

```bash
cd "D:/Users/rafa2/OneDrive/Desktop/agente_zap"
git init
mkdir -p app ingest db tests
```

- [ ] **Step 2: Criar `requirements.txt`**

```
fastapi==0.115.*
uvicorn[standard]==0.30.*
httpx==0.27.*
google-genai==1.*
supabase==2.*
pydantic-settings==2.*
pypdf==5.*
python-docx==1.*
pytest==8.*
pytest-asyncio==0.24.*
```

- [ ] **Step 3: Criar `.gitignore`**

```
.env
__pycache__/
*.pyc
.venv/
conhecimento/
```

- [ ] **Step 4: Criar `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
pythonpath = .
```

- [ ] **Step 5: Instalar dependências**

Run:
```bash
python -m venv .venv && . .venv/Scripts/activate && pip install -r requirements.txt
```
Expected: instalação sem erros.

- [ ] **Step 6: Criar `app/__init__.py` e `tests/__init__.py` (vazios)**

```bash
touch app/__init__.py tests/__init__.py ingest/__init__.py
```

- [ ] **Step 7: Escrever o teste que falha (`tests/test_config.py`)**

```python
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
```

- [ ] **Step 8: Rodar o teste e ver falhar**

Run: `pytest tests/test_config.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 9: Implementar `app/config.py`**

```python
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
```

- [ ] **Step 10: Rodar o teste e ver passar**

Run: `pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add requirements.txt .gitignore pytest.ini app/ ingest/__init__.py tests/
git commit -m "chore: scaffolding do projeto + config via pydantic-settings"
```

---

### Task 2: Modelos de domínio

**Files:**
- Create: `app/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `ParsedMessage` (dataclass): `message_id: str, from_phone: str, contact_name: str, text: str, phone_number_id: str`.
  - `DadosLead` (pydantic): `nome: str | None = None, empresa: str | None = None, necessidade: str | None = None`.
  - `Classificacao` (pydantic): `etiqueta: str = "morno", tema: str = ""`.
  - `TurnResult` (pydantic): `resposta: str, dados_lead: DadosLead, classificacao: Classificacao, acao: str = "continuar"`.

- [ ] **Step 1: Escrever o teste que falha (`tests/test_models.py`)**

```python
from app.models import ParsedMessage, TurnResult


def test_parsed_message_fields():
    m = ParsedMessage(
        message_id="wamid.1",
        from_phone="5511999",
        contact_name="Ana",
        text="oi",
        phone_number_id="106",
    )
    assert m.from_phone == "5511999"


def test_turn_result_defaults():
    t = TurnResult(resposta="olá")
    assert t.acao == "continuar"
    assert t.dados_lead.nome is None
    assert t.classificacao.etiqueta == "morno"


def test_turn_result_from_dict():
    t = TurnResult(
        resposta="vamos agendar",
        dados_lead={"nome": "Ana", "necessidade": "site"},
        classificacao={"etiqueta": "quente", "tema": "site institucional"},
        acao="mandar_calendly",
    )
    assert t.dados_lead.nome == "Ana"
    assert t.acao == "mandar_calendly"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_models.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 3: Implementar `app/models.py`**

```python
from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass
class ParsedMessage:
    message_id: str
    from_phone: str
    contact_name: str
    text: str
    phone_number_id: str


class DadosLead(BaseModel):
    nome: str | None = None
    empresa: str | None = None
    necessidade: str | None = None


class Classificacao(BaseModel):
    etiqueta: str = "morno"
    tema: str = ""


class TurnResult(BaseModel):
    resposta: str
    dados_lead: DadosLead = Field(default_factory=DadosLead)
    classificacao: Classificacao = Field(default_factory=Classificacao)
    acao: str = "continuar"
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_models.py -v`
Expected: PASS (3 testes).

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat: modelos de domínio (ParsedMessage, TurnResult)"
```

---

### Task 3: Schema do banco (Supabase)

**Files:**
- Create: `db/schema.sql`

**Interfaces:**
- Produces (no banco): tabelas `documents`, `leads`, `conversations`; função RPC `match_documents(query_embedding, match_threshold, match_count)`; índice HNSW em `documents.embedding`.

> Esta tarefa não tem teste unitário automatizado; o deliverable é o schema aplicado e verificado no Supabase. Pré-requisito: ter um projeto Supabase (URL + service key).

- [ ] **Step 1: Escrever `db/schema.sql`**

```sql
-- Extensão pgvector (instalada no schema extensions, boa prática)
create extension if not exists vector with schema extensions;

-- Trigger genérico para atualizar updated_at
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- Base de conhecimento (RAG)
create table if not exists public.documents (
  id        bigint primary key generated always as identity,
  content   text not null,
  metadata  jsonb default '{}'::jsonb,
  embedding extensions.vector(768)
);
create index if not exists documents_embedding_hnsw
  on public.documents using hnsw (embedding extensions.vector_cosine_ops);

-- Leads etiquetados (criado antes de conversations por causa da FK)
create table if not exists public.leads (
  id          bigint primary key generated always as identity,
  nome        text,
  telefone    text,
  empresa     text,
  necessidade text,
  etiqueta    text check (etiqueta in ('quente','morno','frio')),
  tema        text,
  status      text default 'novo',
  created_at  timestamptz not null default now()
);

-- Estado da conversa por número de WhatsApp
create table if not exists public.conversations (
  id         bigint primary key generated always as identity,
  phone      text unique not null,
  messages   jsonb not null default '[]'::jsonb,
  lead_data  jsonb not null default '{}'::jsonb,
  lead_id    bigint references public.leads(id),
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);
drop trigger if exists conversations_set_updated_at on public.conversations;
create trigger conversations_set_updated_at
  before update on public.conversations
  for each row execute function public.set_updated_at();

-- RLS habilitado (o servidor usa a service key, que ignora RLS)
alter table public.documents enable row level security;
alter table public.leads enable row level security;
alter table public.conversations enable row level security;

-- RPC de similaridade por cosseno
create or replace function public.match_documents(
  query_embedding extensions.vector(768),
  match_threshold float,
  match_count int
)
returns setof public.documents
language sql stable
set search_path = extensions, public
as $$
  select *
  from public.documents
  where embedding <=> query_embedding < 1 - match_threshold
  order by embedding <=> query_embedding asc
  limit least(match_count, 50);
$$;
```

- [ ] **Step 2: Aplicar o schema no Supabase**

Opção A (recomendada): colar o conteúdo de `db/schema.sql` no **SQL Editor** do painel Supabase e executar.
Opção B: via Supabase MCP / CLI aplicando como migration.

- [ ] **Step 3: Verificar**

No SQL Editor, rodar:
```sql
select table_name from information_schema.tables
where table_schema='public' and table_name in ('documents','leads','conversations');
select proname from pg_proc where proname='match_documents';
```
Expected: as 3 tabelas e a função `match_documents` aparecem.

- [ ] **Step 4: Commit**

```bash
git add db/schema.sql
git commit -m "feat: schema do banco (documents, leads, conversations, match_documents)"
```

---

### Task 4: WhatsApp — parsing de entrada + verificação de assinatura

**Files:**
- Create: `app/whatsapp.py`
- Test: `tests/test_whatsapp_inbound.py`

**Interfaces:**
- Consumes: `app.models.ParsedMessage`.
- Produces:
  - `parse_incoming(payload: dict) -> ParsedMessage | None` (retorna `None` para eventos sem `messages` ou não-texto).
  - `verify_signature(raw_body: bytes, signature_header: str | None, app_secret: str) -> bool`.

- [ ] **Step 1: Escrever o teste que falha (`tests/test_whatsapp_inbound.py`)**

```python
import hmac
import hashlib

from app.whatsapp import parse_incoming, verify_signature

TEXT_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [{
        "id": "102290129340398",
        "changes": [{
            "field": "messages",
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {"display_phone_number": "15550783881", "phone_number_id": "106540352242922"},
                "contacts": [{"profile": {"name": "Sheena Nelson"}, "wa_id": "16505551234"}],
                "messages": [{
                    "from": "16505551234",
                    "id": "wamid.HBgLM",
                    "timestamp": "1749416383",
                    "type": "text",
                    "text": {"body": "Vocês entregam no sábado?"},
                }],
            },
        }],
    }],
}

STATUS_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [{"changes": [{"value": {"statuses": [{"status": "delivered"}]}}]}],
}


def test_parse_incoming_text():
    m = parse_incoming(TEXT_PAYLOAD)
    assert m is not None
    assert m.message_id == "wamid.HBgLM"
    assert m.from_phone == "16505551234"
    assert m.contact_name == "Sheena Nelson"
    assert m.text == "Vocês entregam no sábado?"
    assert m.phone_number_id == "106540352242922"


def test_parse_incoming_status_returns_none():
    assert parse_incoming(STATUS_PAYLOAD) is None


def test_parse_incoming_malformed_returns_none():
    assert parse_incoming({}) is None


def test_verify_signature_ok():
    secret = "minha_app_secret"
    body = b'{"hello":"world"}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(body, sig, secret) is True


def test_verify_signature_bad():
    assert verify_signature(b"x", "sha256=deadbeef", "secret") is False
    assert verify_signature(b"x", None, "secret") is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_whatsapp_inbound.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.whatsapp'`.

- [ ] **Step 3: Implementar parsing + assinatura em `app/whatsapp.py`**

```python
import hashlib
import hmac

from app.models import ParsedMessage


def parse_incoming(payload: dict) -> ParsedMessage | None:
    try:
        value = payload["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError, TypeError):
        return None

    messages = value.get("messages")
    if not messages:
        return None

    msg = messages[0]
    if msg.get("type") != "text":
        return None

    contacts = value.get("contacts") or [{}]
    name = contacts[0].get("profile", {}).get("name", "")

    return ParsedMessage(
        message_id=msg["id"],
        from_phone=msg["from"],
        contact_name=name,
        text=msg["text"]["body"],
        phone_number_id=value["metadata"]["phone_number_id"],
    )


def verify_signature(raw_body: bytes, signature_header: str | None, app_secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_whatsapp_inbound.py -v`
Expected: PASS (5 testes).

- [ ] **Step 5: Commit**

```bash
git add app/whatsapp.py tests/test_whatsapp_inbound.py
git commit -m "feat: parsing do webhook da Meta + verificação de assinatura"
```

---

### Task 5: WhatsApp — envio de mensagem (`send_text`)

**Files:**
- Modify: `app/whatsapp.py`
- Test: `tests/test_whatsapp_send.py`

**Interfaces:**
- Consumes: `app.config.get_settings`.
- Produces: `async def send_text(to: str, body: str) -> None` (POST para a Graph API; levanta exceção em erro HTTP).

- [ ] **Step 1: Escrever o teste que falha (`tests/test_whatsapp_send.py`)**

```python
import pytest

import app.whatsapp as wa
from app.config import Settings


class _FakeResp:
    def __init__(self):
        self.calls = []

    def raise_for_status(self):
        return None


class _FakeClient:
    def __init__(self, sink):
        self.sink = sink

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        self.sink["url"] = url
        self.sink["headers"] = headers
        self.sink["json"] = json
        return _FakeResp()


@pytest.mark.asyncio
async def test_send_text_posts_to_graph_api(monkeypatch):
    sink = {}
    monkeypatch.setattr(wa, "get_settings", lambda: Settings(
        gemini_api_key="k", meta_access_token="TOK", meta_phone_number_id="PHONE",
        meta_verify_token="v", meta_app_secret="s", supabase_url="https://x.supabase.co",
        supabase_service_key="srv", calendly_url="https://calendly.com/e",
    ))
    monkeypatch.setattr(wa.httpx, "AsyncClient", lambda *a, **k: _FakeClient(sink))

    await wa.send_text("16505551234", "Olá!")

    assert sink["url"] == "https://graph.facebook.com/v23.0/PHONE/messages"
    assert sink["headers"]["Authorization"] == "Bearer TOK"
    assert sink["json"]["to"] == "16505551234"
    assert sink["json"]["text"]["body"] == "Olá!"
    assert sink["json"]["type"] == "text"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_whatsapp_send.py -v`
Expected: FAIL com `AttributeError: module 'app.whatsapp' has no attribute 'send_text'`.

- [ ] **Step 3: Adicionar imports e `send_text` ao topo/fim de `app/whatsapp.py`**

No topo do arquivo, adicionar:
```python
import httpx

from app.config import get_settings
```

No fim do arquivo, adicionar:
```python
async def send_text(to: str, body: str) -> None:
    s = get_settings()
    url = f"https://graph.facebook.com/{s.meta_graph_version}/{s.meta_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {s.meta_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": True, "body": body},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_whatsapp_send.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/whatsapp.py tests/test_whatsapp_send.py
git commit -m "feat: envio de mensagem de texto via WhatsApp Cloud API"
```

---

### Task 6: Chunker (divisão de texto para ingestão)

**Files:**
- Create: `ingest/chunker.py`
- Test: `tests/test_chunker.py`

**Interfaces:**
- Produces: `chunk_text(text: str, max_chars: int = 2000, overlap_chars: int = 300) -> list[str]` (≈500 tokens por chunk, ≈15% overlap; respeita parágrafos e faz hard-split de parágrafos gigantes).

- [ ] **Step 1: Escrever o teste que falha (`tests/test_chunker.py`)**

```python
from ingest.chunker import chunk_text


def test_empty_returns_empty():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_short_text_single_chunk():
    out = chunk_text("Parágrafo curto.", max_chars=2000)
    assert out == ["Parágrafo curto."]


def test_long_text_splits_with_overlap():
    paras = "\n\n".join(f"Parágrafo número {i} com algum conteúdo." for i in range(200))
    out = chunk_text(paras, max_chars=500, overlap_chars=100)
    assert len(out) > 1
    # cada chunk respeita o limite com folga do overlap
    assert all(len(c) <= 500 + 100 for c in out)


def test_huge_paragraph_hard_split():
    out = chunk_text("x" * 1200, max_chars=500, overlap_chars=100)
    assert len(out) >= 3
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_chunker.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'ingest.chunker'`.

- [ ] **Step 3: Implementar `ingest/chunker.py`**

```python
def chunk_text(text: str, max_chars: int = 2000, overlap_chars: int = 300) -> list[str]:
    if not text or not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(para) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            start = 0
            step = max(1, max_chars - overlap_chars)
            while start < len(para):
                chunks.append(para[start:start + max_chars].strip())
                start += step
            continue

        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current.strip())
            current = current[-overlap_chars:] + "\n\n" + para
        else:
            current = f"{current}\n\n{para}" if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_chunker.py -v`
Expected: PASS (4 testes).

- [ ] **Step 5: Commit**

```bash
git add ingest/chunker.py tests/test_chunker.py
git commit -m "feat: chunker de texto para ingestão do RAG"
```

---

### Task 7: Prompts (instrução de sistema + montagem do turno)

**Files:**
- Create: `app/prompts.py`
- Test: `tests/test_prompts.py`

**Interfaces:**
- Produces:
  - `SYSTEM_INSTRUCTION: str`.
  - `build_user_turn(context: list[str], lead_data: dict, message: str) -> str` (inclui contexto do RAG, estado do lead e a mensagem do cliente).

- [ ] **Step 1: Escrever o teste que falha (`tests/test_prompts.py`)**

```python
from app.prompts import SYSTEM_INSTRUCTION, build_user_turn


def test_system_instruction_mentions_rules():
    assert "JSON" in SYSTEM_INSTRUCTION
    assert "mandar_calendly" in SYSTEM_INSTRUCTION


def test_build_user_turn_includes_parts():
    out = build_user_turn(
        context=["Trecho A", "Trecho B"],
        lead_data={"nome": "Ana"},
        message="vocês fazem site?",
    )
    assert "Trecho A" in out
    assert "Trecho B" in out
    assert "nome=Ana" in out
    assert "vocês fazem site?" in out


def test_build_user_turn_empty_context():
    out = build_user_turn(context=[], lead_data={}, message="oi")
    assert "nenhum trecho" in out.lower()
    assert "oi" in out
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_prompts.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.prompts'`.

- [ ] **Step 3: Implementar `app/prompts.py`**

```python
SYSTEM_INSTRUCTION = """Você é o assistente virtual de atendimento da empresa no WhatsApp.

Seus objetivos, nesta ordem:
1. Responder dúvidas do cliente usando APENAS o CONTEXTO fornecido. Se o contexto não tiver a resposta, diga com transparência que vai confirmar com um humano — NUNCA invente informações, preços ou prazos.
2. Ao longo da conversa, coletar de forma natural e leve: o nome do cliente, a necessidade/dor dele e o nome da empresa.
3. Assim que tiver pelo menos o nome e a necessidade, conduzir o cliente para agendar uma conversa com o time (ação "mandar_calendly").

Regras:
- Seja cordial, objetivo e escreva em português do Brasil, em tom de WhatsApp (mensagens curtas).
- Não peça todos os dados de uma vez; colete no fluxo natural da conversa.
- Sempre que o cliente demonstrar interesse em falar com alguém, contratar ou agendar, use a ação "mandar_calendly".
- Classifique o lead: etiqueta "quente" (interesse claro/urgência), "morno" (interesse sem urgência) ou "frio" (curiosidade/sem fit), e um "tema" curto resumindo o assunto.
- A "resposta" é o texto que será enviado ao cliente. NÃO inclua o link de agendamento na resposta; isso é feito automaticamente quando a ação for "mandar_calendly".

Responda SEMPRE no formato JSON do schema fornecido."""


def build_user_turn(context: list[str], lead_data: dict, message: str) -> str:
    ctx = "\n---\n".join(context) if context else "(nenhum trecho relevante encontrado)"
    estado = ", ".join(f"{k}={v}" for k, v in (lead_data or {}).items() if v) or "(vazio)"
    return (
        f"CONTEXTO DA BASE DE CONHECIMENTO:\n{ctx}\n\n"
        f"DADOS JÁ COLETADOS DO LEAD: {estado}\n\n"
        f"MENSAGEM DO CLIENTE: {message}"
    )
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_prompts.py -v`
Expected: PASS (3 testes).

- [ ] **Step 5: Commit**

```bash
git add app/prompts.py tests/test_prompts.py
git commit -m "feat: prompts (system instruction + montagem do turno)"
```

---

### Task 8: Gemini client — `embed_text` (com normalização L2)

**Files:**
- Create: `app/gemini_client.py`
- Test: `tests/test_gemini_embed.py`

**Interfaces:**
- Consumes: `app.config.get_settings`.
- Produces:
  - `_l2_normalize(vec: list[float]) -> list[float]`.
  - `embed_text(text: str, task_type: str) -> list[float]` (vetor de 768 floats, normalizado).

- [ ] **Step 1: Escrever o teste que falha (`tests/test_gemini_embed.py`)**

```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_gemini_embed.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.gemini_client'`.

- [ ] **Step 3: Implementar `app/gemini_client.py` (parte de embeddings)**

```python
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_gemini_embed.py -v`
Expected: PASS (3 testes).

- [ ] **Step 5: Commit**

```bash
git add app/gemini_client.py tests/test_gemini_embed.py
git commit -m "feat: gemini embed_text com normalização L2"
```

---

### Task 9: Gemini client — `generate_turn` (saída estruturada)

**Files:**
- Modify: `app/gemini_client.py`
- Test: `tests/test_gemini_turn.py`

**Interfaces:**
- Consumes: `app.prompts.SYSTEM_INSTRUCTION`, `app.prompts.build_user_turn`, `app.models.TurnResult`.
- Produces: `generate_turn(history: list[dict], context: list[str], lead_data: dict, message: str) -> TurnResult`. `history` é uma lista de `{"role": "user"|"model", "content": str}`.

- [ ] **Step 1: Escrever o teste que falha (`tests/test_gemini_turn.py`)**

```python
import app.gemini_client as gc
from app.config import Settings
from app.models import TurnResult


def _settings():
    return Settings(
        gemini_api_key="k", meta_access_token="t", meta_phone_number_id="1",
        meta_verify_token="v", meta_app_secret="s", supabase_url="https://x.supabase.co",
        supabase_service_key="srv", calendly_url="https://calendly.com/e",
    )


def test_generate_turn_returns_parsed(monkeypatch):
    captured = {}

    class _Models:
        def generate_content(self, model, contents, config):
            captured["model"] = model
            captured["contents"] = contents
            captured["system"] = config.system_instruction
            return type("R", (), {"parsed": TurnResult(resposta="olá", acao="continuar")})()

    class _Client:
        models = _Models()

    monkeypatch.setattr(gc, "get_settings", _settings)
    monkeypatch.setattr(gc, "_client", lambda: _Client())

    out = gc.generate_turn(
        history=[{"role": "user", "content": "oi"}, {"role": "model", "content": "olá!"}],
        context=["Trecho"],
        lead_data={"nome": "Ana"},
        message="vocês fazem site?",
    )

    assert isinstance(out, TurnResult)
    assert out.resposta == "olá"
    assert captured["model"] == "gemini-2.5-flash"
    # histórico (2) + turno atual (1) = 3 mensagens
    assert len(captured["contents"]) == 3
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_gemini_turn.py -v`
Expected: FAIL com `AttributeError: module 'app.gemini_client' has no attribute 'generate_turn'`.

- [ ] **Step 3: Adicionar imports e `generate_turn` em `app/gemini_client.py`**

No topo, adicionar aos imports existentes:
```python
from app import prompts
from app.models import TurnResult
```

No fim do arquivo, adicionar:
```python
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_gemini_turn.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/gemini_client.py tests/test_gemini_turn.py
git commit -m "feat: gemini generate_turn com saída estruturada (TurnResult)"
```

---

### Task 10: Store (acesso ao Supabase)

**Files:**
- Create: `app/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: `app.config.get_settings`.
- Produces:
  - `merge_lead_data(existing: dict, updates: dict) -> dict` (não sobrescreve com valores vazios).
  - `get_conversation(phone: str) -> dict | None`.
  - `upsert_conversation(phone: str, messages: list, lead_data: dict, lead_id: int | None) -> dict`.
  - `create_or_update_lead(conversation: dict | None, lead_data: dict, classificacao: dict, telefone: str) -> int`.
  - `search_documents(embedding: list[float], threshold: float, count: int) -> list[dict]`.
  - `insert_document(content: str, metadata: dict, embedding: list[float]) -> None`.
  - `clear_documents() -> None`.

- [ ] **Step 1: Escrever o teste que falha (`tests/test_store.py`)**

```python
from unittest.mock import MagicMock

import app.store as store


def test_merge_lead_data_keeps_existing_when_empty():
    out = store.merge_lead_data({"nome": "Ana"}, {"nome": "", "empresa": "ACME"})
    assert out == {"nome": "Ana", "empresa": "ACME"}


def test_merge_lead_data_overwrites_with_value():
    out = store.merge_lead_data({"nome": "Ana"}, {"nome": "Ana Paula"})
    assert out["nome"] == "Ana Paula"


def test_search_documents_calls_rpc(monkeypatch):
    fake_sb = MagicMock()
    fake_sb.rpc.return_value.execute.return_value.data = [{"content": "x", "metadata": {}}]
    monkeypatch.setattr(store, "_supabase", lambda: fake_sb)

    rows = store.search_documents([0.1, 0.2], 0.6, 5)

    fake_sb.rpc.assert_called_once_with(
        "match_documents",
        {"query_embedding": [0.1, 0.2], "match_threshold": 0.6, "match_count": 5},
    )
    assert rows == [{"content": "x", "metadata": {}}]


def test_create_lead_inserts_when_no_existing(monkeypatch):
    fake_sb = MagicMock()
    fake_sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": 42}]
    monkeypatch.setattr(store, "_supabase", lambda: fake_sb)

    lead_id = store.create_or_update_lead(
        conversation=None,
        lead_data={"nome": "Ana", "necessidade": "site"},
        classificacao={"etiqueta": "quente", "tema": "site"},
        telefone="5511999",
    )
    assert lead_id == 42
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_store.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.store'`.

- [ ] **Step 3: Implementar `app/store.py`**

```python
from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def _supabase() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_key)


def merge_lead_data(existing: dict, updates: dict) -> dict:
    merged = dict(existing or {})
    for key, value in (updates or {}).items():
        if value:
            merged[key] = value
    return merged


def get_conversation(phone: str) -> dict | None:
    res = _supabase().table("conversations").select("*").eq("phone", phone).limit(1).execute()
    return res.data[0] if res.data else None


def upsert_conversation(phone: str, messages: list, lead_data: dict, lead_id: int | None) -> dict:
    row = {"phone": phone, "messages": messages, "lead_data": lead_data, "lead_id": lead_id}
    res = _supabase().table("conversations").upsert(row, on_conflict="phone").execute()
    return res.data[0]


def create_or_update_lead(
    conversation: dict | None,
    lead_data: dict,
    classificacao: dict,
    telefone: str,
) -> int:
    payload = {
        "nome": lead_data.get("nome"),
        "telefone": telefone,
        "empresa": lead_data.get("empresa"),
        "necessidade": lead_data.get("necessidade"),
        "etiqueta": (classificacao or {}).get("etiqueta"),
        "tema": (classificacao or {}).get("tema"),
        "status": "link_enviado",
    }
    existing_id = (conversation or {}).get("lead_id")
    sb = _supabase()
    if existing_id:
        sb.table("leads").update(payload).eq("id", existing_id).execute()
        return existing_id
    res = sb.table("leads").insert(payload).execute()
    return res.data[0]["id"]


def search_documents(embedding: list[float], threshold: float, count: int) -> list[dict]:
    res = _supabase().rpc(
        "match_documents",
        {"query_embedding": embedding, "match_threshold": threshold, "match_count": count},
    ).execute()
    return res.data or []


def insert_document(content: str, metadata: dict, embedding: list[float]) -> None:
    _supabase().table("documents").insert(
        {"content": content, "metadata": metadata, "embedding": embedding}
    ).execute()


def clear_documents() -> None:
    _supabase().table("documents").delete().neq("id", 0).execute()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_store.py -v`
Expected: PASS (4 testes).

- [ ] **Step 5: Commit**

```bash
git add app/store.py tests/test_store.py
git commit -m "feat: store (conversations, leads, documents) no Supabase"
```

---

### Task 11: RAG — `retrieve`

**Files:**
- Create: `app/rag.py`
- Test: `tests/test_rag.py`

**Interfaces:**
- Consumes: `app.gemini_client.embed_text`, `app.store.search_documents`, `app.config.get_settings`.
- Produces: `retrieve(query: str, top_k: int | None = None, threshold: float | None = None) -> list[dict]` (cada item é uma linha de `documents` com `content`/`metadata`).

- [ ] **Step 1: Escrever o teste que falha (`tests/test_rag.py`)**

```python
import app.rag as rag


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

    monkeypatch.setattr(rag.gemini_client, "embed_text", fake_embed)
    monkeypatch.setattr(rag.store, "search_documents", fake_search)

    out = rag.retrieve("vocês fazem site?", top_k=3, threshold=0.5)

    assert captured["task_type"] == "RETRIEVAL_QUERY"
    assert captured["embedding"] == [0.1, 0.2]
    assert captured["count"] == 3
    assert captured["threshold"] == 0.5
    assert out == [{"content": "doc1", "metadata": {}}]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_rag.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.rag'`.

- [ ] **Step 3: Implementar `app/rag.py`**

```python
from app import gemini_client, store
from app.config import get_settings


def retrieve(query: str, top_k: int | None = None, threshold: float | None = None) -> list[dict]:
    s = get_settings()
    top_k = top_k if top_k is not None else s.rag_top_k
    threshold = threshold if threshold is not None else s.rag_match_threshold

    embedding = gemini_client.embed_text(query, task_type="RETRIEVAL_QUERY")
    return store.search_documents(embedding, threshold, top_k)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_rag.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/rag.py tests/test_rag.py
git commit -m "feat: RAG retrieve (embed query + match_documents)"
```

---

### Task 12: Mensagem de agendamento (`scheduling`)

**Files:**
- Create: `app/scheduling.py`
- Test: `tests/test_scheduling.py`

**Interfaces:**
- Produces: `build_calendly_message(lead_data: dict, calendly_url: str) -> str`.

- [ ] **Step 1: Escrever o teste que falha (`tests/test_scheduling.py`)**

```python
from app.scheduling import build_calendly_message


def test_message_includes_url_and_name():
    msg = build_calendly_message({"nome": "Ana"}, "https://calendly.com/empresa")
    assert "https://calendly.com/empresa" in msg
    assert "Ana" in msg


def test_message_without_name():
    msg = build_calendly_message({}, "https://calendly.com/empresa")
    assert "https://calendly.com/empresa" in msg
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_scheduling.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.scheduling'`.

- [ ] **Step 3: Implementar `app/scheduling.py`**

```python
def build_calendly_message(lead_data: dict, calendly_url: str) -> str:
    nome = (lead_data or {}).get("nome")
    saudacao = f"Perfeito, {nome}! " if nome else "Perfeito! "
    return (
        f"{saudacao}Para a gente seguir, é só escolher o melhor horário "
        f"para uma conversa com o nosso time pelo link abaixo:\n\n"
        f"{calendly_url}\n\n"
        "Assim que você agendar, já fica confirmado. Qualquer dúvida, é só me chamar por aqui. 😊"
    )
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_scheduling.py -v`
Expected: PASS (2 testes).

- [ ] **Step 5: Commit**

```bash
git add app/scheduling.py tests/test_scheduling.py
git commit -m "feat: mensagem de agendamento com link do Calendly"
```

---

### Task 13: Orquestrador (cérebro do turno)

**Files:**
- Create: `app/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `app.rag.retrieve`, `app.gemini_client.generate_turn`, `app.store` (get_conversation, merge_lead_data, create_or_update_lead, upsert_conversation), `app.scheduling.build_calendly_message`, `app.whatsapp.send_text`, `app.config.get_settings`, `app.models.ParsedMessage`.
- Produces:
  - `should_send_calendly(lead_data: dict, acao: str) -> bool`.
  - `async def handle_message(parsed: ParsedMessage) -> None`.

- [ ] **Step 1: Escrever o teste que falha (`tests/test_orchestrator.py`)**

```python
import pytest

import app.orchestrator as orch
from app.config import Settings
from app.models import ParsedMessage, TurnResult


def _settings():
    return Settings(
        gemini_api_key="k", meta_access_token="t", meta_phone_number_id="1",
        meta_verify_token="v", meta_app_secret="s", supabase_url="https://x.supabase.co",
        supabase_service_key="srv", calendly_url="https://calendly.com/empresa",
    )


def test_should_send_calendly_by_action():
    assert orch.should_send_calendly({}, "mandar_calendly") is True


def test_should_send_calendly_by_fields():
    assert orch.should_send_calendly({"nome": "Ana", "necessidade": "site"}, "continuar") is True


def test_should_not_send_when_incomplete():
    assert orch.should_send_calendly({"nome": "Ana"}, "continuar") is False


@pytest.mark.asyncio
async def test_handle_message_sends_link_when_ready(monkeypatch):
    sent = []

    monkeypatch.setattr(orch, "get_settings", _settings)
    monkeypatch.setattr(orch.store, "get_conversation", lambda phone: None)
    monkeypatch.setattr(orch.rag, "retrieve", lambda text: [{"content": "doc"}])
    monkeypatch.setattr(
        orch.gemini_client, "generate_turn",
        lambda history, context, lead_data, message: TurnResult(
            resposta="Boa! Vamos agendar?",
            dados_lead={"nome": "Ana", "necessidade": "site"},
            classificacao={"etiqueta": "quente", "tema": "site"},
            acao="mandar_calendly",
        ),
    )
    monkeypatch.setattr(orch.store, "create_or_update_lead", lambda *a, **k: 7)
    monkeypatch.setattr(orch.store, "upsert_conversation", lambda *a, **k: {})

    async def fake_send(to, body):
        sent.append((to, body))

    monkeypatch.setattr(orch.whatsapp, "send_text", fake_send)

    await orch.handle_message(ParsedMessage("wamid.1", "5511999", "Ana", "quero um site", "PHONE"))

    # 1ª: resposta do bot; 2ª: link do Calendly
    assert len(sent) == 2
    assert "calendly.com/empresa" in sent[1][1]


@pytest.mark.asyncio
async def test_handle_message_no_link_when_incomplete(monkeypatch):
    sent = []

    monkeypatch.setattr(orch, "get_settings", _settings)
    monkeypatch.setattr(orch.store, "get_conversation", lambda phone: None)
    monkeypatch.setattr(orch.rag, "retrieve", lambda text: [])
    monkeypatch.setattr(
        orch.gemini_client, "generate_turn",
        lambda history, context, lead_data, message: TurnResult(resposta="Como posso ajudar?"),
    )

    def _fail(*a, **k):
        raise AssertionError("não deveria criar lead")

    monkeypatch.setattr(orch.store, "create_or_update_lead", _fail)
    monkeypatch.setattr(orch.store, "upsert_conversation", lambda *a, **k: {})

    async def fake_send(to, body):
        sent.append((to, body))

    monkeypatch.setattr(orch.whatsapp, "send_text", fake_send)

    await orch.handle_message(ParsedMessage("wamid.2", "5511888", "X", "oi", "PHONE"))

    assert len(sent) == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_orchestrator.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.orchestrator'`.

- [ ] **Step 3: Implementar `app/orchestrator.py`**

```python
from app import gemini_client, rag, scheduling, store, whatsapp
from app.config import get_settings
from app.models import ParsedMessage

REQUIRED_FIELDS = ("nome", "necessidade")


def should_send_calendly(lead_data: dict, acao: str) -> bool:
    if acao == "mandar_calendly":
        return True
    return all((lead_data or {}).get(field) for field in REQUIRED_FIELDS)


async def handle_message(parsed: ParsedMessage) -> None:
    s = get_settings()

    conv = store.get_conversation(parsed.from_phone) or {}
    history = conv.get("messages", [])
    lead_data = conv.get("lead_data", {})

    context_rows = rag.retrieve(parsed.text)
    context = [r.get("content", "") for r in context_rows]

    turn = gemini_client.generate_turn(history, context, lead_data, parsed.text)

    lead_data = store.merge_lead_data(lead_data, turn.dados_lead.model_dump())

    new_history = (history + [
        {"role": "user", "content": parsed.text},
        {"role": "model", "content": turn.resposta},
    ])[-s.history_max_messages:]

    send_link = should_send_calendly(lead_data, turn.acao)
    lead_id = conv.get("lead_id")
    if send_link:
        lead_id = store.create_or_update_lead(
            conv, lead_data, turn.classificacao.model_dump(), parsed.from_phone
        )

    store.upsert_conversation(parsed.from_phone, new_history, lead_data, lead_id)

    await whatsapp.send_text(parsed.from_phone, turn.resposta)
    if send_link:
        await whatsapp.send_text(
            parsed.from_phone, scheduling.build_calendly_message(lead_data, s.calendly_url)
        )
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_orchestrator.py -v`
Expected: PASS (5 testes).

- [ ] **Step 5: Commit**

```bash
git add app/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: orquestrador do turno (RAG + Gemini + lead + envio)"
```

---

### Task 14: Webhook FastAPI (`main.py`)

**Files:**
- Create: `app/main.py`
- Test: `tests/test_webhook.py`

**Interfaces:**
- Consumes: `app.whatsapp` (parse_incoming, verify_signature), `app.orchestrator.handle_message`, `app.config.get_settings`.
- Produces: app FastAPI `app` com `GET /webhook` (verificação) e `POST /webhook` (recebimento + background). Dedup em memória por `message_id`.

- [ ] **Step 1: Escrever o teste que falha (`tests/test_webhook.py`)**

```python
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.config import Settings


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    s = Settings(
        gemini_api_key="k", meta_access_token="t", meta_phone_number_id="PHONE",
        meta_verify_token="VTOKEN", meta_app_secret="SECRET",
        supabase_url="https://x.supabase.co", supabase_service_key="srv",
        calendly_url="https://calendly.com/e",
    )
    monkeypatch.setattr(main, "get_settings", lambda: s)
    main._seen_ids.clear()
    return s


def test_verify_returns_challenge():
    client = TestClient(main.app)
    resp = client.get("/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "VTOKEN", "hub.challenge": "12345",
    })
    assert resp.status_code == 200
    assert resp.text == "12345"


def test_verify_wrong_token_403():
    client = TestClient(main.app)
    resp = client.get("/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "ERRADO", "hub.challenge": "12345",
    })
    assert resp.status_code == 403


def test_post_invalid_signature_403():
    client = TestClient(main.app)
    resp = client.post("/webhook", content=b"{}", headers={"X-Hub-Signature-256": "sha256=bad"})
    assert resp.status_code == 403


def test_post_valid_signature_200_and_processes(monkeypatch):
    calls = []

    async def fake_handle(parsed):
        calls.append(parsed)

    monkeypatch.setattr(main, "handle_message", fake_handle)

    body = json.dumps({
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "PHONE"},
            "contacts": [{"profile": {"name": "Ana"}}],
            "messages": [{"from": "5511999", "id": "wamid.X", "type": "text",
                          "text": {"body": "oi"}}],
        }}]}],
    }).encode()
    sig = "sha256=" + hmac.new(b"SECRET", body, hashlib.sha256).hexdigest()

    client = TestClient(main.app)
    resp = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sig})

    assert resp.status_code == 200
    assert len(calls) == 1
    assert calls[0].message_id == "wamid.X"

    # reentrega do mesmo message_id é ignorada (idempotência)
    client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sig})
    assert len(calls) == 1


def test_post_handle_error_sends_fallback(monkeypatch):
    sent = []

    async def boom(parsed):
        raise RuntimeError("gemini fora do ar")

    async def fake_send(to, body):
        sent.append((to, body))

    monkeypatch.setattr(main, "handle_message", boom)
    monkeypatch.setattr(main.whatsapp, "send_text", fake_send)

    body = json.dumps({
        "entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "PHONE"},
            "contacts": [{"profile": {"name": "Ana"}}],
            "messages": [{"from": "5511777", "id": "wamid.ERR", "type": "text",
                          "text": {"body": "oi"}}],
        }}]}],
    }).encode()
    sig = "sha256=" + hmac.new(b"SECRET", body, hashlib.sha256).hexdigest()

    client = TestClient(main.app)
    resp = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sig})

    assert resp.status_code == 200
    assert len(sent) == 1
    assert "instabilidade" in sent[0][1]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_webhook.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 3: Implementar `app/main.py`**

```python
import logging
from collections import OrderedDict

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app import whatsapp
from app.config import get_settings
from app.orchestrator import handle_message

app = FastAPI()
logger = logging.getLogger("agente_zap")

FALLBACK_MSG = "Tive uma instabilidade aqui do meu lado 😅 Pode mandar a mensagem de novo, por favor?"

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
```

> Nota: `TestClient` executa `BackgroundTasks` de forma síncrona após a resposta, por isso o teste consegue verificar `calls`.

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_webhook.py -v`
Expected: PASS (5 testes).

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_webhook.py
git commit -m "feat: webhook FastAPI (verificação + recebimento + dedup)"
```

---

### Task 15: Ingestão da base de conhecimento (CLI)

**Files:**
- Create: `ingest/ingest.py`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `ingest.chunker.chunk_text`, `app.gemini_client.embed_text`, `app.store` (insert_document, clear_documents).
- Produces:
  - `load_documents(folder: str) -> list[tuple[str, dict]]`.
  - `ingest(folder: str, reset: bool = False) -> int` (retorna nº de chunks indexados).

- [ ] **Step 1: Escrever o teste que falha (`tests/test_ingest.py`)**

```python
import ingest.ingest as ing


def test_load_documents_reads_txt_and_md(tmp_path):
    (tmp_path / "a.txt").write_text("Conteúdo A", encoding="utf-8")
    (tmp_path / "faq.md").write_text("Pergunta? Resposta.", encoding="utf-8")
    (tmp_path / "ignora.xyz").write_text("nope", encoding="utf-8")

    docs = ing.load_documents(str(tmp_path))
    textos = sorted(t for t, _ in docs)
    assert textos == ["Conteúdo A", "Pergunta? Resposta."]
    assert all("fonte" in meta for _, meta in docs)


def test_ingest_chunks_embeds_and_upserts(tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("Parágrafo um.\n\nParágrafo dois.", encoding="utf-8")

    upserts = []
    monkeypatch.setattr(ing, "chunk_text", lambda text: ["c1", "c2"])
    monkeypatch.setattr(ing.gemini_client, "embed_text", lambda text, task_type: [0.1])
    monkeypatch.setattr(ing.store, "insert_document",
                        lambda content, metadata, embedding: upserts.append(content))
    monkeypatch.setattr(ing.store, "clear_documents", lambda: upserts.append("CLEARED"))

    count = ing.ingest(str(tmp_path), reset=True)

    assert count == 2
    assert upserts[0] == "CLEARED"
    assert "c1" in upserts and "c2" in upserts
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_ingest.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'ingest.ingest'`.

- [ ] **Step 3: Implementar `ingest/ingest.py`**

```python
import pathlib
import sys

from app import gemini_client, store
from ingest.chunker import chunk_text


def _read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_pdf(path: pathlib.Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def _read_docx(path: pathlib.Path) -> str:
    import docx

    document = docx.Document(str(path))
    return "\n\n".join(p.text for p in document.paragraphs if p.text.strip())


LOADERS = {
    ".txt": _read_text,
    ".md": _read_text,
    ".pdf": _read_pdf,
    ".docx": _read_docx,
}


def load_documents(folder: str) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for path in sorted(pathlib.Path(folder).rglob("*")):
        loader = LOADERS.get(path.suffix.lower())
        if not loader:
            continue
        text = loader(path)
        if text and text.strip():
            out.append((text, {"fonte": path.name}))
    return out


def ingest(folder: str, reset: bool = False) -> int:
    if reset:
        store.clear_documents()

    total = 0
    for text, metadata in load_documents(folder):
        for chunk in chunk_text(text):
            embedding = gemini_client.embed_text(chunk, task_type="RETRIEVAL_DOCUMENT")
            store.insert_document(chunk, dict(metadata), embedding)
            total += 1
    return total


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--reset"]
    reset = "--reset" in sys.argv
    folder = args[0] if args else "./conhecimento"
    count = ingest(folder, reset=reset)
    print(f"Indexados {count} chunks de '{folder}'.")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `pytest tests/test_ingest.py -v`
Expected: PASS (2 testes).

- [ ] **Step 5: Commit**

```bash
git add ingest/ingest.py tests/test_ingest.py
git commit -m "feat: CLI de ingestão da base de conhecimento (RAG)"
```

---

### Task 16: README, `.env.example` e checklist de E2E manual

**Files:**
- Create: `.env.example`, `README.md`

**Interfaces:** nenhuma (documentação).

- [ ] **Step 1: Criar `.env.example`**

```
GEMINI_API_KEY=
META_ACCESS_TOKEN=
META_PHONE_NUMBER_ID=
META_VERIFY_TOKEN=
META_APP_SECRET=
META_GRAPH_VERSION=v23.0
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
CALENDLY_URL=
CHAT_MODEL=gemini-2.5-flash
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIM=768
RAG_TOP_K=5
RAG_MATCH_THRESHOLD=0.6
HISTORY_MAX_MESSAGES=20
```

- [ ] **Step 2: Criar `README.md`**

````markdown
# Agente de WhatsApp — Qualificador + Agendador (RAG)

Bot de WhatsApp (Meta Cloud API) que responde dúvidas via RAG (Gemini + Supabase/pgvector),
qualifica o lead com coleta leve, classifica e encaminha para agendamento (Calendly).

## Pré-requisitos

- Python 3.11+
- Projeto Supabase (URL + service key)
- Chave da API do Gemini (Google AI Studio)
- Conta Meta Business verificada + número dedicado + token permanente (System User) + App Secret
- Link do Calendly

## Setup

```bash
python -m venv .venv && . .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env   # preencha os valores
```

Aplique o schema do banco: cole `db/schema.sql` no SQL Editor do Supabase.

## Indexar a base de conhecimento

Coloque PDFs/Word/txt e um `faq.md` numa pasta (ex.: `./conhecimento/`) e rode:

```bash
python -m ingest.ingest ./conhecimento --reset
```

## Rodar o servidor

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Exponha via HTTPS público (ngrok em dev) e configure o webhook no painel da Meta apontando
para `https://SEU_DOMINIO/webhook`, com o mesmo `META_VERIFY_TOKEN`, inscrito no campo `messages`.

## Testes

```bash
pytest -v
```

## Checklist de E2E manual

1. `uvicorn app.main:app --port 8000` e `ngrok http 8000`.
2. No painel da Meta, configurar o webhook com a URL do ngrok + verify token; confirmar que a verificação (GET) passa.
3. Indexar uma base mínima (`faq.md`) com `python -m ingest.ingest ./conhecimento --reset`.
4. Enviar uma mensagem do WhatsApp para o número de teste.
5. Conferir: o bot responde; a tabela `conversations` tem a linha do número; ao completar nome + necessidade, chega o link do Calendly e a tabela `leads` recebe a linha com `etiqueta`/`tema` e `status=link_enviado`.
````

- [ ] **Step 3: Rodar a suíte completa**

Run: `pytest -v`
Expected: todos os testes PASS.

- [ ] **Step 4: Commit**

```bash
git add .env.example README.md
git commit -m "docs: README, .env.example e checklist de E2E"
```

---

## Notas de produção (pós-MVP, fora do escopo de implementação inicial)

- **Durabilidade do background:** `BackgroundTasks` roda em processo; se o servidor reiniciar no meio, a mensagem se perde. Caminho de escala: fila (Supabase Queue / Redis + worker) e dedup persistente (tabela `processed_messages`).
- **Rate limits do Gemini (free ~10 RPM):** adicionar retry com backoff e considerar habilitar billing para volume real.
- **Resiliência de envio:** retry com backoff no `send_text` (3 tentativas) + log estruturado de falhas.
- **Fallback do Gemini:** já implementado no MVP (try/except no `process_event` envia mensagem educada de instabilidade). Evoluir para distinguir timeout vs erro permanente e, em timeout, tentar novamente antes do fallback.
- **Dedup persistente:** o dedup atual é em memória (sobrevive a reentregas em segundos, mas não a restart). Para robustez, persistir `message_id` (tabela `processed_messages`).
```
