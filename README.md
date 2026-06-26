# Agente de WhatsApp — Qualificador + Agendador (RAG)

Bot de WhatsApp (Meta Cloud API oficial) que responde dúvidas usando a base de
conhecimento da empresa (RAG com Gemini + Supabase/pgvector), qualifica o lead com
coleta leve, classifica (quente/morno/frio + tema) e encaminha para agendamento
enviando o link do Calendly.

## Stack
- **Python 3.11+ / FastAPI** (webhook)
- **Gemini** `gemini-2.5-flash` (chat) + `gemini-embedding-001` (embeddings, 768 dims, normalizados L2)
- **Supabase** (Postgres + pgvector) — leads, estado das conversas e vetores do RAG
- **WhatsApp Cloud API** (Graph API v23.0)

## Como o bot se comporta
- Responde dúvidas **apenas com base no contexto** recuperado (não inventa).
- Coleta de forma natural: **nome** e **necessidade** (empresa é opcional).
- Só envia o Calendly **depois** de ter nome + necessidade, e **uma única vez** por conversa.
- Classifica o lead (`etiqueta`: quente/morno/frio, `tema`) e grava em `leads`.

## Arquitetura (módulos)
```
app/
  main.py          # FastAPI: GET/POST /webhook (verificação, assinatura, 200 rápido, background, dedup, fallback)
  config.py        # settings via env/.env (pydantic-settings)
  models.py        # ParsedMessage + TurnResult/DadosLead/Classificacao
  whatsapp.py      # parse_incoming · verify_signature · send_text
  prompts.py       # SYSTEM_INSTRUCTION · build_user_turn
  gemini_client.py # embed_text (L2) · generate_turn (saída estruturada)
  rag.py           # retrieve (embed + match_documents)
  store.py         # Supabase: conversations, leads, documents
  scheduling.py    # build_calendly_message
  orchestrator.py  # handle_message (o "cérebro" do turno)
ingest/
  chunker.py       # chunk_text
  ingest.py        # CLI: lê .md/.txt/.pdf/.docx → chunk → embed → grava em documents
db/schema.sql      # extensão vector, tabelas, índice HNSW, função match_documents
```

## Setup
```bash
python -m venv .venv
# Windows: . .venv/Scripts/activate      |  Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preencha os valores
```
> No Windows, rode os comandos Python com `.venv/Scripts/python -m ...`.

### Variáveis de ambiente (`.env`)
Veja `.env.example`. As que dependem de terceiros: `GEMINI_API_KEY` (Google AI Studio),
`SUPABASE_URL` + `SUPABASE_SERVICE_KEY` (Supabase), `META_ACCESS_TOKEN` +
`META_PHONE_NUMBER_ID` + `META_APP_SECRET` (Meta), `CALENDLY_URL` (seu link).
O `META_VERIFY_TOKEN` é uma string secreta que **você** define.
**Segredos só no `.env`** (gitignored) — nunca no `.env.example`.

## Banco (Supabase)
Aplique `db/schema.sql` no **SQL Editor** do Supabase (cria a extensão `vector`,
as tabelas, o índice HNSW e a função `match_documents`). RLS fica habilitado; o app
usa a **service key** (server-side), que ignora RLS.

## Indexar a base de conhecimento
Coloque arquivos `.md`, `.txt`, `.pdf` ou `.docx` numa pasta (ex.: `./conhecimento/`) e rode:
```bash
python -m ingest.ingest ./conhecimento --reset
```
`--reset` limpa os vetores antigos antes de reindexar.

## Rodar local
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Exponha via HTTPS (ngrok em dev) e configure o webhook na Meta apontando para
`https://SEU_DOMINIO/webhook` (mesmo `META_VERIFY_TOKEN`, inscrito no campo `messages`).

## Deploy (produção)
Veja **[DEPLOY.md](DEPLOY.md)** — `Dockerfile` pronto + guia passo a passo para Render/Railway.

## Testes
```bash
pytest -v          # Windows: .venv/Scripts/python -m pytest -v
```

## Checklist de E2E manual
1. Subir o servidor + expor com HTTPS (`ngrok http 8000` ou deploy).
2. Na Meta, configurar o webhook com a URL + verify token; confirmar a verificação (GET) → retorna o `hub.challenge`.
3. Indexar uma base (`python -m ingest.ingest ./conhecimento --reset`).
4. Enviar uma mensagem do WhatsApp para o número.
5. Conferir: o bot responde fundamentado no conteúdo; `conversations` tem a linha do número; ao completar nome + necessidade, chega o link do Calendly **uma vez** e `leads` recebe a linha com `etiqueta`/`tema` e `status=link_enviado`.

## Notas de produção
- **Gemini free tier ≈ 10 req/min** — para volume real, habilite billing no Google AI Studio.
- Dedup do webhook é em memória (single-process); para múltiplos workers, persista os `message_id`.
- A janela de 24h da Meta permite texto livre enquanto o cliente interage; fora dela, exige template aprovado (fora do MVP).
