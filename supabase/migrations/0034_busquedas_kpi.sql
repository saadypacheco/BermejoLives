-- 0034: log de búsquedas para KPIs del admin (qué busca la gente y qué NO encuentra).
create table if not exists busquedas (
  id         uuid primary key default gen_random_uuid(),
  query      text not null,
  resultados smallint not null default 0,   -- cuántos resultados dio (0 = sin resultado)
  created_at timestamptz not null default now()
);
create index if not exists idx_busquedas_created on busquedas (created_at);

alter table busquedas enable row level security;
grant all on public.busquedas to service_role;  -- el backend loguea y lee (KPIs)

-- 'vista' como tipo de lead: para "locales más visitados" (se loguea al abrir la ficha).
-- La columna leads.tipo no tiene CHECK, así que no hace falta alterar nada.
