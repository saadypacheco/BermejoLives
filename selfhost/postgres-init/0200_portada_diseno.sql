-- 0200 · Portada de diseño para la ficha pública (docs/portada-diseno.md).
--
--  1. `comercios.portada_diseno_url`: la portada con diseño de publicidad que muestra la ficha en lugar de la foto.
--     Es PÚBLICA (la ficha la usa): regla 11 de AGENTS.md, una columna nueva de `comercios` nace privada para anon
--     y se da a mano por columna.
--  2. `comercios.portada_diseno_propuesta_url`: la propuesta que el panel todavía no aprobó. PRIVADA: no se da a
--     anon ni a authenticated (sólo la lee el backend con service_role).
--  3. Comprobación: si algo quedó mal, no se aplica.
--
-- Sin borrado físico. Idempotente: se puede correr dos veces. Copia idéntica en supabase/migrations/ y
-- selfhost/postgres-init/.

begin;

-- ───────────────────────────────────────────── 1. la portada de diseño, pública por columna
alter table public.comercios add column if not exists portada_diseno_url text;
comment on column public.comercios.portada_diseno_url is
  'Portada con diseño (foto del local + nombre, rubro y ciudad) que la ficha muestra en lugar de la foto. La aprueba una persona en el panel.';
grant select (portada_diseno_url) on public.comercios to anon, authenticated;

-- ───────────────────────────────────────────── 2. la propuesta, privada
alter table public.comercios add column if not exists portada_diseno_propuesta_url text;
comment on column public.comercios.portada_diseno_propuesta_url is
  'Portada de diseño propuesta, todavía sin aprobar. Privada: sólo la ve el panel.';

-- ───────────────────────────────────────────── 3. comprobación
do $chk$
declare
  v_rol text;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    if not has_column_privilege(v_rol, 'public.comercios', 'portada_diseno_url', 'select') then
      raise exception '0200: % no puede leer comercios.portada_diseno_url', v_rol;
    end if;
    if has_column_privilege(v_rol, 'public.comercios', 'portada_diseno_propuesta_url', 'select') then
      raise exception '0200: % puede leer comercios.portada_diseno_propuesta_url y tiene que ser privada', v_rol;
    end if;
  end loop;
end
$chk$;

commit;

notify pgrst, 'reload schema';
