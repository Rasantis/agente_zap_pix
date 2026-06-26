# Deploy — Agente de WhatsApp

O serviço é um app FastAPI (`app.main:app`). Toda a configuração vem de **variáveis de ambiente** (as mesmas chaves do `.env`). Em produção, defina essas variáveis no painel da hospedagem — **não** suba o `.env`.

## Pré-requisitos
- Schema aplicado no Supabase ✅ (já feito).
- Base de conhecimento indexada: `python -m ingest.ingest ./conhecimento --reset` (rode localmente ou dentro do container).
- Variáveis de ambiente definidas (lista abaixo).

## Variáveis de ambiente a definir na hospedagem
```
GEMINI_API_KEY
META_ACCESS_TOKEN
META_PHONE_NUMBER_ID
META_VERIFY_TOKEN
META_APP_SECRET
META_GRAPH_VERSION=v23.0
SUPABASE_URL
SUPABASE_SERVICE_KEY
CALENDLY_URL
```
(As demais — `CHAT_MODEL`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`, `RAG_TOP_K`, `RAG_MATCH_THRESHOLD`, `HISTORY_MAX_MESSAGES` — têm default no código; só defina se quiser sobrescrever.)

## Opção 1 — Render (Docker)
1. Suba o repositório no GitHub.
2. Render → **New → Web Service** → conecte o repo.
3. Runtime: **Docker** (usa o `Dockerfile`).
4. Em **Environment**, adicione as variáveis acima.
5. Deploy. A URL fica tipo `https://seu-app.onrender.com`.

## Opção 2 — Railway
1. Railway → **New Project → Deploy from GitHub repo**.
2. Ele detecta o `Dockerfile` (ou usa o `Procfile`).
3. **Variables** → adicione as variáveis.
4. Deploy → **Settings → Networking → Generate Domain** pra pegar a URL pública.

## Rodar o container localmente (teste)
```
docker build -t agente-zap .
docker run -p 8000:8000 --env-file .env agente-zap
```

## Depois do deploy
- **Webhook URL** = `https://SEU_DOMINIO/webhook`
- Passe essa URL ao time pra configurar o webhook na Meta (o **verify token** já está definido; assinar o campo **`messages`**).
- Teste rápido da verificação: a Meta faz um `GET` no `/webhook`; o app responde o `hub.challenge`. Dá pra simular com:
  `curl "https://SEU_DOMINIO/webhook?hub.mode=subscribe&hub.verify_token=SEU_VERIFY_TOKEN&hub.challenge=123"` → deve retornar `123`.
