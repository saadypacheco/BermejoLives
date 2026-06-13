-- ============================================================
-- Bermejo Live Market · 0002_rls_grants
-- GRANTs explícitos (Supabase Cloud, lesson KB) + RLS.
--
-- Modelo de acceso:
--   anon          → SELECT de catálogo público (comercios/productos activos)
--                   y del feed APROBADO. Nada de pendientes ni escritura.
--   service_role  → todo (lo usa SOLO el backend FastAPI). Bypassa RLS.
-- Toda escritura pasa por el backend; el frontend nunca escribe directo.
-- ============================================================

-- ------------------------------------------------------------
-- GRANTs (sin esto: ERROR 42501 permission denied — lesson KB)
-- ------------------------------------------------------------
grant usage on schema public to anon, authenticated;

-- Lectura pública del catálogo y zonas
grant select on zonas         to anon, authenticated;
grant select on comercios     to anon, authenticated;
grant select on productos     to anon, authenticated;
grant select on publicaciones to anon, authenticated;
grant select on feed_publico  to anon, authenticated;

-- service_role: control total (backend)
grant all on all tables in schema public to service_role;
grant all on all sequences in schema public to service_role;

-- ------------------------------------------------------------
-- RLS
-- ------------------------------------------------------------
alter table zonas         enable row level security;
alter table comercios     enable row level security;
alter table productos     enable row level security;
alter table publicaciones enable row level security;
alter table wa_inbox      enable row level security;

-- Zonas: públicas (activas)
drop policy if exists zonas_public_read on zonas;
create policy zonas_public_read on zonas
  for select to anon, authenticated
  using (activo);

-- Comercios: públicos (activos)
drop policy if exists comercios_public_read on comercios;
create policy comercios_public_read on comercios
  for select to anon, authenticated
  using (activo);

-- Productos: públicos (activos)
drop policy if exists productos_public_read on productos;
create policy productos_public_read on productos
  for select to anon, authenticated
  using (activo);

-- Publicaciones: el público SOLO ve aprobadas y activas.
-- (los pendientes/rechazados quedan invisibles al anon; el panel de
--  moderación los lee vía backend con service_role)
drop policy if exists publicaciones_public_read on publicaciones;
create policy publicaciones_public_read on publicaciones
  for select to anon, authenticated
  using (estado = 'aprobado' and activo);

-- wa_inbox: nada para anon/authenticated (solo service_role, que bypassa RLS).
-- Sin policies => sin acceso para roles no privilegiados.

-- ------------------------------------------------------------
-- Realtime: publicar cambios de 'publicaciones' para el feed en vivo.
-- El cliente se suscribe con anon + RLS (solo recibe filas aprobadas).
-- ------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    create publication supabase_realtime;
  end if;
end$$;
alter publication supabase_realtime add table publicaciones;
