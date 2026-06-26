# CLAUDE.md — guia do projeto

Agente de WhatsApp (qualificador + agendador) — FastAPI + Gemini + Supabase/pgvector.
Visão geral em `README.md`; spec e plano em `docs/superpowers/`.

## Comandos (Windows)
- Testes: `.venv/Scripts/python -m pytest -v`  (NÃO use `pytest` puro)
- Rodar servidor: `uvicorn app.main:app --port 8000`
- Ingestão: `.venv/Scripts/python -m ingest.ingest ./conhecimento --reset`
- Scripts soltos que importam `app` precisam de cwd = raiz do repo (o `.env` é lido do cwd).

## Arquitetura
- `app/main.py` (webhook) → responde 200 rápido → background `process_event` → `app/orchestrator.py`.
- `orchestrator.handle_message` (o cérebro): por turno faz RAG (`rag.retrieve`) + **uma** chamada estruturada ao Gemini (`gemini_client.generate_turn` → `TurnResult`), mescla o lead, classifica, persiste (`store.py`) e envia (`whatsapp.send_text`).
- RAG: `gemini-embedding-001` (768 dims, L2) → `store.search_documents` (RPC `match_documents`, distância de cosseno).
- Saída estruturada do Gemini = modelo pydantic `TurnResult` (em `app/models.py`).

## Convenções / cuidados
- `Classificacao.etiqueta` é `Literal["quente","morno","frio"]` (casa com o `CHECK` de `leads.etiqueta`).
- Calendly: só envia depois de ter **nome + necessidade** e **uma única vez** por conversa (guard `already_scheduled` via `conv.lead_id`).
- A função do store é `insert_document` (foi renomeada de `upsert_document`).
- Config via env/.env com pydantic-settings; use `get_settings()` (cacheado), não instancie `Settings()` solto fora de testes.
- Segredos só no `.env` (gitignored) — nunca no `.env.example`.
- TDD: cada feature tem teste; mantenha a suíte verde antes de commitar.

## Estado atual
Código completo, **46 testes passando**, em `main`. Supabase aplicado e validado ao vivo;
RAG validado multi-formato (md/txt/pdf/docx). Falta, para ir ao vivo: credenciais Meta
(com o time), link do Calendly e o deploy. Detalhes/contexto operacional na memória do projeto.
