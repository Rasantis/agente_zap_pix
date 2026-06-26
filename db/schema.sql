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
