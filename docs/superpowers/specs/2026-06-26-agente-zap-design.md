# Agente de WhatsApp — Qualificador + Agendador com RAG

**Data:** 2026-06-26
**Status:** Aprovado (design) — pronto para virar plano de implementação

## 1. Objetivo

Construir um agente de WhatsApp para dar suporte ao cliente da empresa que:

1. **Responde dúvidas** sobre a empresa/produto usando uma base de conhecimento própria (RAG).
2. **Qualifica o lead** com coleta leve (nome, necessidade, empresa) durante a conversa.
3. **Classifica** o lead (etiqueta quente/morno/frio + tema) para o time interno.
4. **Sempre encaminha para agendamento** ao final, enviando uma mensagem pronta com o link do Calendly.

O cliente agenda direto pelo link do Calendly. O bot não confirma o agendamento de volta (fora do MVP).

## 2. Decisões travadas

| Tema | Decisão |
|------|---------|
| Escopo da conversa | Responder dúvidas (RAG) **e** qualificar |
| Lógica de qualificação | Coleta leve, **sempre** manda o Calendly; classificador só etiqueta |
| Canal | WhatsApp **Cloud API oficial da Meta** |
| Linguagem/framework | **Python / FastAPI** |
| Armazenamento | **Supabase** (Postgres + pgvector) — leads, estado das conversas e vetores |
| LLM | **Gemini** `gemini-2.5-flash` (chat) via SDK `google-genai` |
| Embeddings | **`gemini-embedding-001`**, 768 dims, normalizado L2 |
| Base de conhecimento | Arquivos (PDF/Word/texto) **+** FAQ escrito à mão (`faq.md`) |
| Handoff do lead | Tabela `leads` no Supabase (time consulta) |
| Calendly | Só envia o link (sem webhook de confirmação) |
| Orquestração | **Saída estruturada**: 1 chamada ao Gemini por turno devolve JSON |

## 3. Fatos técnicos verificados (pesquisa em 2026-06-26)

### Gemini
- SDK Python: **`google-genai`** (o `google-generativeai` está descontinuado desde 31/08/2025).
- Chat: **`gemini-2.5-flash`** (melhor custo/qualidade). `gemini-2.5-flash-lite` se precisar cortar custo.
- Embeddings: **`gemini-embedding-001`**, dimensão padrão 3072, **configurável via `output_dimensionality`** (usaremos **768**). Para dims < 3072 é preciso **normalizar L2 manualmente**. `task_type=RETRIEVAL_DOCUMENT` na ingestão e `RETRIEVAL_QUERY` na consulta.
- Por que 768: o tipo `vector` indexável do pgvector (HNSW/IVFFlat) limita em **2000 dims**; 768 é prático e dentro do limite.
- Free tier `gemini-2.5-flash`: ~10 RPM / 250k TPM / ~250 RPD (muda sem aviso; confirmar no AI Studio). Limite é por projeto Google Cloud, não por API key.

### Meta WhatsApp Cloud API
- Versão da Graph API nos exemplos atuais: **v23.0** (usar a mais recente do painel).
- **Verificação do webhook (GET):** Meta envia `hub.mode=subscribe`, `hub.verify_token`, `hub.challenge`. Validar mode + token e responder **200 com o `hub.challenge` em texto puro**; senão **403**.
- **Recebimento (POST):** texto em `entry[0].changes[0].value.messages[0].text.body`; remetente em `...messages[0].from`; `phone_number_id` em `...value.metadata.phone_number_id`; nome em `...value.contacts[0].profile.name`. Responder **200 rápido** (a Meta reentrega/desativa webhooks que não retornam 200). Tratar `messages` e `statuses` separadamente; ignorar eventos sem `messages`.
- **Envio:** `POST https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/messages`, headers `Authorization: Bearer {TOKEN}` + `Content-Type: application/json`, body `{messaging_product, to, type:"text", text:{body}}`.
- **Janela de 24h:** quando o cliente envia mensagem abre uma janela de 24h (reiniciada a cada nova mensagem dele). Dentro: texto livre. Fora / para iniciar conversa: **obrigatório template aprovado**. Como o bot só responde a mensagens recebidas, estamos sempre dentro da janela.
- **Produção:** app na Meta com produto WhatsApp + Meta Business **verificado**; número **dedicado** (não registrado no app de consumidor); **token permanente via System User** (escopos `whatsapp_business_messaging` + `whatsapp_business_management`) — o token do painel expira em 24h; webhook **HTTPS público** inscrito no campo `messages`; validar `X-Hub-Signature-256` (HMAC-SHA256 com o App Secret).

### Supabase / pgvector
- Extensão chamada **`vector`** (instalar no schema `extensions`).
- Coluna `embedding extensions.vector(768)`; **mesma dimensão** na ingestão e na consulta.
- Similaridade via RPC (PostgREST não expõe operadores do pgvector): função `match_documents` com distância de cosseno `<=>`, ordenando **pela distância** (não por coluna calculada, senão ignora o índice).
- Índice **HNSW** (`vector_cosine_ops`) — pode ser criado logo após a tabela.
- Chunking: ~400–512 tokens, overlap ~15%, respeitando fronteiras de parágrafo/seção.

## 4. Arquitetura

```
Cliente (WhatsApp)
      │  mensagem
      ▼
Meta Cloud API ──POST──▶ FastAPI /webhook ──(responde 200 na hora)──┐
                                  │                                  │
                                  └─▶ tarefa em background:          │
                                       1. valida X-Hub-Signature-256 │
                                       2. dedup por message_id       │
                                       3. carrega conversa (Supabase)│
                                       4. RAG: embed + match_documents
                                       5. Gemini (1 chamada/turno) → JSON
                                       6. salva conversa + lead       │
                                       7. envia resposta ◀───────────┘
                                          (+ Calendly quando ação=mandar_calendly)
```

Serviço único FastAPI. Responde **200 imediatamente** e processa em background (a chamada ao Gemini leva alguns segundos). Como o bot sempre responde a uma mensagem recebida, opera dentro da janela de 24h (texto livre, sem template).

## 5. Estrutura de módulos

```
agente_zap/
├─ app/
│  ├─ main.py          # FastAPI: GET /webhook (verifica) · POST /webhook (recebe→background→200)
│  ├─ config.py        # settings via .env (chaves, IDs, URL do Calendly, versão Graph API)
│  ├─ whatsapp.py      # parse_incoming() · verify_signature() · send_text()
│  ├─ gemini_client.py # embed_text() · generate_turn() (saída estruturada)
│  ├─ rag.py           # retrieve(pergunta) → chunks (embed query + RPC match_documents)
│  ├─ orchestrator.py  # handle_message(phone, nome, texto) → resposta  (cérebro do turno)
│  ├─ store.py         # CRUD de conversations e leads (cliente Supabase)
│  ├─ prompts.py       # system instruction + schema do JSON do turno
│  └─ scheduling.py    # monta a mensagem com o link do Calendly
├─ ingest/
│  ├─ ingest.py        # CLI offline: arquivos + faq.md → chunk → embed → grava documents
│  └─ chunker.py       # divide texto em chunks ~500 tokens, ~15% overlap
├─ db/
│  └─ schema.sql       # extensão vector, tabelas, match_documents, índices
├─ tests/
├─ .env.example
├─ requirements.txt
└─ README.md
```

Fronteiras: `whatsapp.py` não conhece Gemini; `rag.py` não conhece WhatsApp; `orchestrator.py` costura tudo. Cada módulo é testável isoladamente.

## 6. Modelo de dados (Supabase)

```sql
create extension if not exists vector with schema extensions;

-- Base de conhecimento (RAG)
create table documents (
  id        bigint primary key generated always as identity,
  content   text not null,                 -- o chunk
  metadata  jsonb default '{}',            -- {fonte, titulo, pagina}
  embedding extensions.vector(768)
);
create index on documents using hnsw (embedding extensions.vector_cosine_ops);

-- Leads etiquetados (time consulta aqui) — criado antes de conversations por causa da FK
create table leads (
  id          bigint primary key generated always as identity,
  nome        text,
  telefone    text,
  empresa     text,
  necessidade text,
  etiqueta    text check (etiqueta in ('quente','morno','frio')),
  tema        text,
  status      text default 'novo',         -- novo | link_enviado
  created_at  timestamptz not null default now()
);

-- Estado da conversa por número
create table conversations (
  id         bigint primary key generated always as identity,
  phone      text unique not null,         -- E.164
  messages   jsonb not null default '[]',  -- [{role, content, ts}] (últimas N)
  lead_data  jsonb not null default '{}',  -- {nome, empresa, necessidade...} coletado até agora
  lead_id    bigint references leads(id),
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);
-- (a constraint UNIQUE em phone já cria o índice de lookup)

-- RPC de similaridade (cosseno)
create function match_documents(query_embedding extensions.vector(768),
                                match_threshold float, match_count int)
returns setof documents language sql as $$
  select * from documents
  where embedding <=> query_embedding < 1 - match_threshold
  order by embedding <=> query_embedding asc
  limit least(match_count, 50);
$$;
```

RLS habilitado nas tabelas; a aplicação usa a service key apenas no servidor. Schema configurado no Supabase via a integração disponível (extensão, tabelas, RPC, índice).

## 7. Fluxo do turno (abordagem A — saída estruturada)

1. Meta envia POST → valida `X-Hub-Signature-256` → retorna **200** e agenda tarefa em background.
2. Background: dedup por `message_id`; extrai `phone`, `nome`, `texto`. Ignora eventos `statuses`/sem `messages`.
3. Carrega `conversations` por `phone` (histórico + `lead_data`).
4. **RAG:** embeda o texto (`RETRIEVAL_QUERY`, normalizado L2) → `match_documents` top-k com threshold → chunks.
5. **Orquestrador:** monta prompt (system instruction + estado do `lead_data` + contexto do RAG + últimas N mensagens + mensagem nova) → **1 chamada** ao `gemini-2.5-flash` com `response_schema` → `TurnResult`.
6. Merge de `dados_lead` no `lead_data`; anexa mensagem do usuário + resposta ao histórico (mantém últimas N); upsert da conversa.
7. Se `acao == "mandar_calendly"` (ou guard determinístico: campos mínimos presentes), anexa a mensagem do Calendly (`scheduling.py`), grava/atualiza o lead em `leads` com a classificação e marca `status=link_enviado`.
8. Envia a resposta via `send_text`.

### Schema do `TurnResult` (saída estruturada do Gemini)

```json
{
  "resposta": "texto que vai pro cliente no WhatsApp",
  "dados_lead": { "nome": "...", "empresa": "...", "necessidade": "..." },
  "classificacao": { "etiqueta": "quente|morno|frio", "tema": "..." },
  "acao": "continuar | mandar_calendly"
}
```

- **Gatilho do Calendly:** decidido pelo modelo via `acao`, guiado por checklist no prompt (já tem nome + necessidade? cliente demonstrou interesse / pediu falar com alguém?). **Guard determinístico** garante o envio quando os campos mínimos já estão preenchidos — nunca "esquece" de agendar.
- **Campos mínimos para agendar:** `nome` + `necessidade` (empresa é desejável, não bloqueante).
- **Anti-alucinação:** se o RAG não trouxer nada acima do threshold, o prompt instrui a não inventar — oferece falar com humano ou puxa para o agendamento.

## 8. Ingestão da base de conhecimento (offline)

CLI rodado pelo time quando o conteúdo muda: `python -m ingest.ingest ./conhecimento/`.
- Lê PDFs / Word / `.txt` **+** um `faq.md` escrito à mão.
- Divide em chunks (~500 tokens, ~15% overlap, respeitando parágrafos).
- Gera embeddings (`gemini-embedding-001`, 768, L2, `RETRIEVAL_DOCUMENT`).
- Faz upsert em `documents` com `metadata` (fonte/título/página).

Desacoplado do webhook: atualizar conhecimento não afeta o bot em execução.

## 9. Tratamento de erros

| Situação | Comportamento |
|---|---|
| Assinatura `X-Hub-Signature-256` inválida | 403, ignora |
| `message_id` repetido (reentrega) | ignora (idempotência) |
| Gemini falha/timeout | resposta de fallback educada, loga, não perde a conversa |
| RAG sem resultado relevante | não inventa; oferece humano ou puxa pro agendamento |
| Envio ao WhatsApp falha | retry com backoff (3x) + log |
| Rate limit do Gemini (free ~10 RPM) | backoff/retry; habilitar billing para volume |
| App reinicia no meio do background | MVP: `BackgroundTasks` do FastAPI. Caminho de escala: fila (Supabase Queue/Redis) + worker |

## 10. Segurança

- Validação de `X-Hub-Signature-256` (HMAC-SHA256 com App Secret) em todo POST.
- Segredos em `.env` (nunca versionado); `.env.example` no repositório.
- Supabase service key apenas no servidor; RLS nas tabelas.
- Token permanente via System User da Meta.

## 11. Testes

- **Unit (TDD primeiro, lógica pura):** parsing do payload da Meta (com payload real de exemplo), verificação de assinatura, chunker, normalização L2, merge do `lead_data`, decisão de "mandar Calendly", montagem do prompt.
- **Integração:** `rag.retrieve` contra `documents` semeada; `orchestrator` com Gemini **stub** devolvendo JSON canônico (assere transições de estado + ação); CRUD do `store`.
- **E2E manual:** ngrok + número de teste da Meta → envia mensagem → confere resposta + linha em `leads` + etiqueta.

## 12. Fora do MVP (YAGNI)

- Confirmação de agendamento via webhook do Calendly.
- Function-calling / multi-agente.
- Mensagens de áudio/imagem (texto primeiro).
- Sync com CRM / Google Sheets.
- Painel admin (consulta o Supabase direto por enquanto).
- Campanhas ativas (bot iniciando conversa — exigiriam template).

## 13. Pré-requisitos a providenciar (responsabilidade do usuário)

- Conta **Meta Business verificada** + número dedicado + token permanente (System User) + App Secret + verify token.
- **Chave da API do Gemini** (Google AI Studio).
- Projeto **Supabase** (URL + service key) — schema configurado pela implementação.
- **Link do Calendly**.
- Hospedagem com **HTTPS público** (Render/Railway/Fly/VPS); ngrok para desenvolvimento local.

## 14. Variáveis de ambiente (`.env`)

```
GEMINI_API_KEY=
META_ACCESS_TOKEN=          # token permanente do System User
META_PHONE_NUMBER_ID=
META_VERIFY_TOKEN=          # string secreta definida por nós no painel
META_APP_SECRET=            # para validar X-Hub-Signature-256
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

## 15. Atualizações pós-design (implementação)

Mudanças e decisões surgidas durante a implementação/validação. O design acima
permanece a base; estas são as evoluções:

- **`Classificacao.etiqueta` virou `Literal["quente","morno","frio"]`** — propaga o enum
  para o schema de saída estruturada do Gemini e alinha com o `CHECK` de `leads.etiqueta`
  (evita que um valor fora do conjunto quebre o INSERT do lead).
- **`store.insert_document`** — renomeado de `upsert_document` (a função faz `insert`; o
  dedup é via `--reset`/`clear_documents` na reindexação).
- **Calendly enviado uma única vez** — o orquestrador só dispara o link após ter
  `nome` + `necessidade` **e** se a conversa ainda não tem `lead_id` (guard
  `already_scheduled`), evitando reenviar o link a cada mensagem seguinte.
- **Prompt ajustado** — o modelo só usa a ação `mandar_calendly` depois de coletar
  nome + necessidade (antes disso, `continuar`).
- **Hardening** — `set_updated_at` recriada com `search_path` fixo (advisor de segurança do Supabase).
- **Deploy** — adicionados `Dockerfile`, `Procfile`, `.dockerignore` e `DEPLOY.md` (Render/Railway).
- **Ingestão multi-formato validada** — `.md`, `.txt`, `.pdf` (pypdf) e `.docx` (python-docx).
- **Nota de produção** — o free tier do Gemini é ≈ 10 req/min; para volume real, habilitar billing no Google AI Studio.

### Pacote de naturalidade (2026-07-08)
- **Prompt**: persona Pix Safety explícita; mensagens curtas (1-3 frases); no máximo UMA
  pergunta por mensagem; anti-repetição de perguntas de coleta; uso do nome do perfil do
  WhatsApp (`contact_name` do webhook, agora passado ao LLM) para confirmar identidade;
  `temperature` 0.3 → 0.6.
- **Reenvio do Calendly**: nova ação `reenviar_link` (só sob pedido explícito do cliente);
  o prompt recebe o flag `link_ja_enviado` para o modelo saber que o link já foi; o guard
  `already_scheduled` continua impedindo reenvio automático.
- **Mídia**: `ParsedMessage.msg_type`; áudio/imagem/documento recebem fallback educado
  (não caem mais no vácuo); reações são ignoradas.
- **Presença**: `mark_read_and_typing` (ticks azuis + "digitando...", 1 POST na Graph API,
  best-effort antes de cada resposta).
- **Plano pós-go-live**: `docs/superpowers/plans/2026-07-08-melhorias-pos-golive.md`
  (transcrição de voice notes com Gemini, debounce de rajada, follow-up de abandono,
  notificação de lead quente, webhook do Calendly, checklist operacional).

### Go-live e evoluções (2026-07-09)
- **BOT EM PRODUÇÃO** no +55 51 2391-7020, validado com conversas reais (texto e áudio).
- **Schema wire sem defaults (`TurnResultWire`)** — correção definitiva do
  `ValueError: Default value is not supported in the response schema` (validação presente
  no SDK google-genai 1.0–1.11; a API oficial ignora `default`). O schema enviado ao
  Gemini não pode ter defaults; conversão wire→`TurnResult` no `generate_turn`.
- **Tabela `error_logs`** — `process_event` grava o traceback de qualquer falha de turno
  no Supabase (diagnóstico via MCP, sem depender de painel de host).
- **Humanização (rodada 2)** — sem repetir o nome do cliente/empresa, cumprimento único,
  sem eco da pergunta, respostas curtas, variação de ritmo; honestidade se perguntarem
  se é um robô.
- **Suporte a voice notes** — `whatsapp.download_media` (2 passos, Bearer) →
  `gemini_client.transcribe_audio` (áudio inline, ~32 tokens/s) → o texto segue o turno
  normal; falha → fallback educado. OGG/Opus do WhatsApp validado em produção.
- **Agendamento com consentimento** — o bot oferece o link no momento certo e só envia
  quando o cliente topa (`should_send_calendly` exige `acao=mandar_calendly` E
  nome+necessidade); reenvio segue apenas sob pedido explícito.
- **Registro do número via API** (`POST /{phone_id}/register`) quando o painel da Meta
  falhou; PIN de duas etapas definido.
- Auditoria de versões da stack (não aplicada — produção congelada):
  `notas/relatorio-auditoria-versoes.md`.

### Status (2026-07-09)
Em produção, 64 testes passando, `main` no GitHub com autodeploy no Render.
Pendências operacionais antes de escalar: planos pagos (Render/Supabase/Gemini) e
rotação de segredos — ver plano pós-go-live.
