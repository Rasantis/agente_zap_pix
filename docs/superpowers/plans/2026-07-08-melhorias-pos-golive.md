# Melhorias pós-go-live — Agente Zap

Este plano cobre os próximos incrementos do bot de WhatsApp (qualificador + agendador)
depois que ele estiver rodando com tráfego real. O bot hoje já responde com RAG, qualifica
lead (nome + necessidade), classifica em quente/morno/frio, envia o link do Calendly uma
única vez (reenviando só sob pedido explícito) e tem fallback educado para áudio/mídia. As
seções abaixo detalham cinco features e um checklist operacional, cada uma com objetivo,
design proposto, arquivos afetados, riscos e esforço estimado (P/M/G).

## Prioridade sugerida

| Ordem | Item | Impacto | Esforço | Por quê |
|---|---|---|---|---|
| 1 | 6. Checklist operacional pré-tráfego | Alto (evita queda total) | P | Sem isso o bot cai (Supabase pausa, Render hiberna, rate limit do Gemini). Bloqueante. |
| 2 | 1. Transcrição de voice notes | Alto (naturalidade BR) | M | Brasileiro manda muito áudio; hoje isso vira um fallback manual, perdendo qualificação. |
| 3 | 2. Debounce de rajada | Médio-Alto (qualidade da conversa) | M | Evita respostas fragmentadas/fora de ordem quando o lead manda várias mensagens seguidas. |
| 4 | 4. Notificação ativa de lead quente | Médio (velocidade de follow-up comercial) | P | Barato de implementar, ganho direto em SLA de resposta do time. |
| 5 | 5. Webhook do Calendly | Médio (métrica de conversão real) | M | Depende de expor endpoint público e validar assinatura; não bloqueia o core. |
| 6 | 3. Follow-up de abandono | Médio (recupera lead morno) | M/G | Precisa de scheduler externo (cron/pg_cron); mais infra nova, maior risco de gerar ruído se mal calibrado. |

---

## 1. Transcrição de voice notes com Gemini — ✅ IMPLEMENTADO (2026-07-09)

> Entregue no commit `34a6eae` conforme o design abaixo (`whatsapp.download_media` +
> `gemini_client.transcribe_audio` + fluxo no `main.process_event`). OGG/Opus do WhatsApp
> funcionou direto no Gemini (sem transcodificação); validado em produção com áudio real.

**Objetivo:** substituir o fallback educado atual de áudio por uma transcrição real, para
que voice notes entrem no fluxo normal de qualificação como se fossem texto.

**Design proposto:**
1. No webhook, quando `type == "audio"`, capturar `audio.id` e `audio.mime_type`.
2. Passo 1 do download: `GET https://graph.facebook.com/<ver>/<MEDIA_ID>` com Bearer token
   → retorna a URL real da mídia (expira em 5 min).
3. Passo 2: baixar essa URL com o **mesmo** Bearer token (não é uma URL pública), em até
   5 min. Mídia fica disponível por 7 dias no servidor da Meta, mas o link do passo 1 é
   sempre gerado na hora.
4. Chamar `gemini-2.5-flash` com `types.Part.from_bytes(data=<bytes>, mime_type="audio/ogg")`
   pedindo só a transcrição (chamada separada da chamada estruturada do turno, para não
   misturar responsabilidades).
5. Prefixar o texto transcrito (ex.: `"[áudio transcrito] " + texto`) e injetá-lo no fluxo
   normal do `orchestrator.handle_message`, como se fosse a mensagem de texto do usuário.
6. Se a transcrição falhar (erro de API, mídia expirada, timeout) manter o fallback educado
   atual como rede de segurança.

**Arquivos afetados:** `app/main.py` (detecção do tipo `audio` no payload do webhook),
novo módulo `app/audio.py` (ou função em `app/whatsapp.py`) para o download em 2 passos,
`app/gemini_client.py` (nova função `transcribe_audio`), `app/orchestrator.py` (chamar a
transcrição antes do RAG/turno quando a mensagem for áudio).

**Riscos/observações:**
- A doc oficial do Gemini lista suporte a "OGG Vorbis"; o WhatsApp manda Opus dentro do
  contêiner OGG (`audio/ogg; codecs=opus`). Não há confirmação explícita de suporte a Opus
  — tratar como "suportado com ressalva": testar direto primeiro, e ter um fallback de
  transcodificação via `ffmpeg` (ogg/opus → mp3 ou wav) caso a API rejeite ou transcreva mal.
- Custo: áudio custa ~32 tokens/segundo de entrada (~1.920 tokens/min). Um voice note de
  30s ≈ 960 tokens de entrada — marginal, mas monitorar se volume de áudio for alto.
- Latência extra (download + chamada Gemini) antes de responder — considerar manter o
  typing indicator ativo durante esse tempo.

**Esforço estimado:** M.

---

## 2. Debounce de rajada

**Objetivo:** evitar que o bot responda a cada mensagem individual quando o lead manda
várias mensagens curtas em sequência (comportamento comum no WhatsApp brasileiro), o que
hoje gera respostas fragmentadas e fora de contexto.

**Design proposto:**
1. Ao receber uma mensagem, em vez de chamar `process_event` imediatamente, agendar/():
   - Se já existe uma `asyncio.Task` de debounce pendente para aquele `phone`, cancelá-la.
   - Criar uma nova task que dorme ~8s e, se não for cancelada, dispara o processamento
     acumulando todas as mensagens chegadas nesse intervalo (concatenadas ou processadas
     como lista, dependendo de como o `orchestrator` consome).
2. Manter um dicionário em memória `phone -> (task, buffer_de_mensagens)` no processo do
   `app/main.py` (ou um módulo novo `app/debounce.py`).
3. Ao processar, juntar as mensagens do buffer num único turno (ex.: concatenar com quebra
   de linha) e seguir o fluxo normal (RAG + 1 chamada Gemini).

**Arquivos afetados:** `app/main.py` (ponto de entrada do webhook), novo módulo
`app/debounce.py`, possivelmente `app/orchestrator.py` (para aceitar múltiplas mensagens
de um turno).

**Riscos/observações:**
- Essa solução assume **um único processo/worker** (estado em memória). Se o deploy no
  Render escalar para múltiplos workers/instâncias, o debounce por `asyncio.Task` local
  deixa de funcionar corretamente (cada worker teria seu próprio buffer) — nesse caso será
  necessário migrar para uma fila externa (Redis, ou tabela no Supabase com lock).
  Documentar essa limitação explicitamente no código.
  - Precisa cuidado com o `mark-as-read`/typing indicator para não "piscar" a cada mensagem
    do buffer.
- Cancelamento de task mal feito pode perder mensagem (testar concorrência).

**Esforço estimado:** M.

---

## 3. Follow-up de abandono

**Objetivo:** recuperar leads que somem no meio da qualificação (deram "oi" ou começaram a
conversa mas pararam de responder), com um nudge gentil, ainda dentro da janela de 24h da
Meta (fora dela não é possível mandar mensagem de sessão sem template aprovado).

**Design proposto:**
1. Critério de disparo: `conversations` sem `lead_id` (ou lead sem `etiqueta` final) e
   `updated_at` mais antigo que ~2h, e ainda dentro de 24h da última mensagem do usuário.
2. Scheduler externo rodando periodicamente (a cada 15-30 min): opção A — cron job no
   próprio Render (Render Cron Job, plano pago) chamando um endpoint interno tipo
   `/internal/run-nudges`; opção B — `pg_cron` no Supabase disparando uma função que só
   marca os leads elegíveis, e um worker do próprio app consome essa fila.
3. Enviar 1 mensagem curta e humana (ex.: "Oi, ainda tá por aí? Fico à disposição pra
   ajudar 🙂" — sem emoji se o tom do bot não usa) via `whatsapp.send_text`.
4. Marcar `nudged=true` (nova coluna em `conversations` ou `leads`) para nunca repetir o
   nudge na mesma conversa.

**Arquivos afetados:** migração no Supabase (nova coluna `nudged` / `last_user_message_at`),
novo módulo `app/nudge.py` (ou job), endpoint interno em `app/main.py` se for cron via HTTP,
`app/store.py` (query de conversas elegíveis).

**Riscos/observações:**
- Maior peça de infraestrutura nova (scheduler externo) comparado às outras features —
  maior risco de configuração errada gerar nudge duplicado ou fora da janela de 24h.
- Precisa registrar `last_user_message_at` de forma confiável para calcular corretamente
  as 2h e a janela de 24h.
- Cuidado para não mandar nudge para lead que já terminou a conversa "naturalmente" (ex.:
  já recebeu o Calendly e não precisa de mais nada) — condicionar ao estado do lead.

**Esforço estimado:** M/G.

---

## 4. Notificação ativa de lead quente

**Objetivo:** avisar o time comercial imediatamente quando um lead é classificado como
`etiqueta=quente`, para reduzir o tempo de resposta humano.

**Design proposto:**
1. No ponto do `orchestrator.py` onde o lead é persistido com `etiqueta="quente"` (em
   `store.py`), disparar uma notificação assíncrona (não bloquear a resposta ao usuário).
2. Recomendação: começar com **Slack webhook** ou **e-mail** — não consome conversa da
   janela de 24h da Meta e é mais simples de implementar que WhatsApp para número interno.
   Slack incoming webhook: `POST` de um payload simples (nome, necessidade, telefone,
   resumo da conversa) para uma URL configurada via env (`SLACK_WEBHOOK_URL`).
3. Alternativa (fase 2, se o time preferir): mensagem via o próprio bot para um número
   interno do time, usando `whatsapp.send_text` — mais simples de operar (não precisa de
   conta Slack) mas consome janela/template e acopla notificação interna ao canal do cliente.

**Arquivos afetados:** `app/orchestrator.py` (chamada ao notificar após classificar),
novo módulo `app/notify.py`, `app/config.py`/`.env.example` (nova env `SLACK_WEBHOOK_URL`).

**Riscos/observações:**
- Falha na notificação (Slack fora do ar, webhook errado) não pode quebrar o fluxo do
  usuário — envolver em try/except e logar, nunca propagar exceção para o `orchestrator`.
- Evitar notificar mais de uma vez pro mesmo lead se ele for reclassificado como quente
  de novo depois (idempotência simples: só notificar na primeira vez que vira quente).

**Esforço estimado:** P.

---

## 5. Webhook do Calendly

**Objetivo:** saber de verdade quando um lead marcou reunião (métrica de conversão real),
e usar isso para parar de mandar follow-ups/nudges para quem já agendou.

**Design proposto:**
1. Criar endpoint novo `POST /calendly-webhook` em `app/main.py` (ou router dedicado).
2. Configurar no painel do Calendly um webhook de organização/usuário assinando o evento
   `invitee.created`, apontando pra esse endpoint.
3. Validar a assinatura do payload (Calendly manda um HMAC-SHA256 no header
   `Calendly-Webhook-Signature`, com um signing key gerado na criação do webhook) antes de
   processar — rejeitar payloads não assinados corretamente.
4. Extrair o e-mail/telefone do invitee do payload e casar com o lead correspondente
   (provavelmente por telefone, se coletado no formulário do Calendly, ou por e-mail se for
   isso que se usa para casar com `leads`).
5. Atualizar `leads.status='reuniao_agendada'` no Supabase. Esse status também serve de
   guarda para não mandar follow-up de abandono (item 3) depois que a reunião é marcada.

**Arquivos afetados:** `app/main.py` (novo endpoint), novo módulo `app/calendly.py`
(validação de assinatura + parsing do payload), migração no Supabase (nova coluna
`status` ou reaproveitar campo existente em `leads`), `app/store.py` (update do lead).

**Riscos/observações:**
- Casar o invitee do Calendly com o lead certo pode ser ambíguo se o link do Calendly não
  carrega nenhum identificador do lead (ideal: usar prefill de UTM/parâmetro customizado no
  link com o `lead_id` ou telefone, para casar 1:1 sem heurística por nome/e-mail).
- Precisa expor o endpoint publicamente (já é o caso do webhook da Meta) e documentar a
  signing key como segredo (`.env`, nunca versionado).
- Baixo acoplamento com o resto do fluxo — pode ser feito em paralelo às outras features.

**Esforço estimado:** M.

---

## 6. Checklist operacional pré-tráfego real

**Objetivo:** garantir que a infraestrutura aguenta tráfego real antes de divulgar o número
para leads de verdade — hoje tudo está em planos free, que têm limitações que já
derrubaram o ambiente antes.

**Itens:**
- **Render (plano pago):** o free tier hiberna após ~15 min de inatividade e o cold start
  leva ~50s — inaceitável para um webhook que precisa responder rápido (Meta espera 200 em
  poucos segundos). Migrar para plano pago antes de divulgar o número.
- **Supabase (plano pago):** o free tier **pausa o projeto após ~7 dias de inatividade**,
  derrubando o banco inteiro (já aconteceu neste projeto). Migrar para plano pago ou, no
  mínimo, monitorar/reativar proativamente antes que pause.
- **Billing do Gemini:** o tier free tem limite de **10 RPM** — insuficiente para qualquer
  volume real de conversas simultâneas (cada turno faz pelo menos 1 chamada estruturada +
  embeddings do RAG). Ativar billing/tier pago antes do go-live.
- **Rotacionar segredos que passaram por chat/conversas:** App Secret da Meta, Supabase
  service role key, access token da Meta — qualquer credencial que tenha sido colada em
  chat (Claude, Slack, etc.) deve ser considerada potencialmente exposta e rotacionada
  antes de ir ao ar com tráfego real.
- **Logs/observabilidade das conversas:** hoje não há um jeito fácil de ver como o bot está
  respondendo em produção para iterar o prompt/RAG. Definir um lugar mínimo de observação
  (dashboard simples nas tabelas do Supabase, ou exportar logs estruturados) para conseguir
  revisar conversas reais e ajustar o comportamento do bot rapidamente após o go-live.

**Arquivos afetados:** nenhum código novo obrigatório (é operacional/infra), mas pode gerar
ajustes em `render.yaml`, `.env.example` (documentar quais envs precisam de rotação) e,
para logs, possivelmente um script/view no Supabase.

**Riscos/observações:** este item é bloqueante — sem ele, qualquer uma das features acima
é irrelevante porque o bot pode simplesmente estar fora do ar ou sem capacidade de
responder quando o tráfego real chegar.

**Esforço estimado:** P.
