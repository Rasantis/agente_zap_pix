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
