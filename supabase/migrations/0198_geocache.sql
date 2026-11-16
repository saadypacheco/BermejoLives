-- 0198 · Caché permanente de Nominatim (docs/vigia-fuentes.md, fase 1).
--
-- Cada corrida de `ubicar_direccion` le volvía a preguntar todo a Nominatim (~700 pedidos). El 16/11, después
-- de cuatro corridas, dejó de contestar: su política de uso pide no repetir consultas y guardar los resultados.
-- Acá queda la respuesta CRUDA (la primera fila que devolvió, o null si no encontró nada): los filtros del
-- ubicador (rango mínimo, largo máximo de la calle, caja de la ciudad) se aplican después, así que cambiarlos
-- no obliga a volver a preguntar.
--
--   clave          sha256 de «consulta | ciudad | radio» (la misma consulta con otra caja es otra respuesta)
--   consulta       el texto preguntado, para leerlo a mano
--   resultado      jsonb con lat, lon, display_name, place_rank, boundingbox; null = «no encontrado»
--   consultado_at  cuándo se preguntó: el backend la vuelve a pedir a los 90 días (30 si no encontró)
--
-- PERMISOS: sólo el backend (service_role). Nada para anon ni authenticated; RLS activo sin políticas.
-- No se borra: una consulta vencida se pisa con la respuesta nueva (upsert por clave). Es un caché de datos
-- públicos de OpenStreetMap, sin datos personales.
-- Idempotente. Copia idéntica en supabase/migrations/ y selfhost/postgres-init/.

begin;

create table if not exists public.geocache (
  id            uuid primary key default gen_random_uuid(),
  clave         text not null unique,
  consulta      text not null,
  ciudad_id     uuid references public.ciudades(id) on delete set null,
  resultado     jsonb,
  consultado_at timestamptz not null default now()
);

comment on table public.geocache is 'Respuestas de Nominatim guardadas: no repetir la misma consulta (docs/vigia-fuentes.md).';

alter table public.geocache enable row level security;

revoke all on public.geocache from anon, authenticated;
grant select, insert, update on public.geocache to service_role;

commit;
