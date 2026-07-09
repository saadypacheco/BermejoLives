-- Monitoreo propio de errores y performance (sin depender de terceros).
-- error_logs: excepciones de backend/frontend, agrupadas por fingerprint para
--   no llenar la tabla con la misma falla repetida.
-- perf_events: mediciones crudas de demora (Web Vitals del frontend, duración
--   de requests del backend); se limpian solas con el tiempo (ver observabilidad.py).

create table if not exists error_logs (
  id uuid primary key default gen_random_uuid(),
  fingerprint text not null,
  origen text not null check (origen in ('frontend', 'backend')),
  nivel text not null default 'error' check (nivel in ('error', 'lento')),
  mensaje text not null,
  stack text,
  ruta text,
  status_code int,
  contexto jsonb,
  ocurrencias int not null default 1,
  primera_vez timestamptz not null default now(),
  ultima_vez timestamptz not null default now(),
  resuelto boolean not null default false
);

create unique index if not exists error_logs_fingerprint_idx on error_logs (fingerprint);
create index if not exists error_logs_ultima_vez_idx on error_logs (ultima_vez desc);

alter table error_logs enable row level security;
grant all on error_logs to service_role;

create table if not exists perf_events (
  id uuid primary key default gen_random_uuid(),
  origen text not null check (origen in ('frontend', 'backend')),
  ruta text not null,
  metrica text not null,
  valor_ms numeric not null,
  repetida boolean,
  created_at timestamptz not null default now()
);

create index if not exists perf_events_created_at_idx on perf_events (created_at desc);
create index if not exists perf_events_ruta_idx on perf_events (ruta);

alter table perf_events enable row level security;
grant all on perf_events to service_role;
