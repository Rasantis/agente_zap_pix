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
- Calendly: só envia depois de ter **nome + necessidade** e **uma vez** por conversa (guard `already_scheduled` via `conv.lead_id`); **reenvio** só quando o cliente pede explicitamente (ação `reenviar_link` do LLM + o flag `link_ja_enviado` vai no prompt via `build_user_turn`).
- `ParsedMessage.msg_type`: `"text"` segue o fluxo normal; mídia (áudio/imagem/etc.) recebe fallback educado no `main.process_event`; **reações são ignoradas** (`parse_incoming` → None).
- `whatsapp.mark_read_and_typing(message_id)`: ticks azuis + "digitando..." (1 POST; best-effort no `process_event`, falha não bloqueia o turno).
- Prompt de naturalidade: persona Pix Safety, 1 pergunta por vez, anti-repetição, nome do perfil do WhatsApp (`contact_name`) usado pra confirmar identidade; `temperature=0.6` no `generate_turn`.
- A função do store é `insert_document` (foi renomeada de `upsert_document`).
- Config via env/.env com pydantic-settings; use `get_settings()` (cacheado), não instancie `Settings()` solto fora de testes.
- Segredos só no `.env` (gitignored) — nunca no `.env.example`.
- TDD: cada feature tem teste; mantenha a suíte verde antes de commitar.

## Estado atual
Código completo, **58 testes passando**, em `main`. Supabase aplicado e validado ao vivo;
base de conhecimento REAL do Pix Safety indexada (26 chunks) e RAG validado ponta a ponta;
deploy no Render no ar (webhook validado). Pacote de naturalidade aplicado e validado com
simulação real. Falta, para ir 100% ao vivo: token/Calendly nas envs do Render e o time
configurar o webhook na Meta. Melhorias futuras: `docs/superpowers/plans/2026-07-08-melhorias-pos-golive.md`.
Contexto operacional na memória do projeto.
