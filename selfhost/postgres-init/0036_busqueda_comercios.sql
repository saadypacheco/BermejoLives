-- 0036: relación búsqueda → comercios que aparecieron en los resultados.
--   Objetivo: poder analizar, por comercio, CON QUÉ TÉRMINOS lo encuentra la gente
--   (y a los comercios sin resultados, qué se buscaba). Alimenta:
--     · "Mi negocio" → términos con los que te encuentran (valor agregado al comercio).
--     · KPIs del admin → demanda por comercio / oportunidades.
create table if not exists busqueda_comercios (
  busqueda_id uuid not null references busquedas(id) on delete cascade,
  comercio_id uuid not null references comercios(id) on delete cascade,
  posicion    smallint not null default 0,   -- 0 = apareció primero en los resultados
  primary key (busqueda_id, comercio_id)
);
create index if not exists idx_bc_comercio on busqueda_comercios (comercio_id);
create index if not exists idx_bc_busqueda on busqueda_comercios (busqueda_id);

alter table busqueda_comercios enable row level security;
grant all on public.busqueda_comercios to service_role;  -- solo el backend escribe/lee
