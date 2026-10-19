-- publicaciones: `updated_at` (con trigger) y `remitente_rol`, para la API de integración.
--
--   updated_at     El cursor de sincronización de la integración es (updated_at, id): hasta hoy
--                  `publicaciones` no sabía cuándo se tocó por última vez. Backfill = created_at.
--                  El trigger usa clock_timestamp() (no now()): now() es la hora de INICIO de la
--                  transacción, y una transacción larga que confirma tarde dejaría una fila con
--                  fecha anterior al cursor que el cliente ya pasó (la perdería).
--                  Se actualiza en todo UPDATE (no se puede filtrar con WHEN old.* <> new.*: la tabla
--                  tiene una columna generada, `busqueda`). Cambiar updated_at no cambia el ETag de la
--                  API (que sólo mira contenido, estado y activo): un UPDATE sin cambios de contenido
--                  mueve el cursor pero el cliente lo ve como "sin cambios".
--   remitente_rol  Quién mandó el mensaje, resuelto por la ingesta: 'merchant' (el comercio),
--                  'third_party' (otro participante del grupo, o alguien que sólo sabe el código)
--                  o 'uruku_explorer' (el explorador de URUKU). NULL = publicación anterior a esto.
--                  Es lo que le permite a la integración procesar sólo material del propio comercio
--                  SIN que la API devuelva teléfonos.
--
-- Las dos columnas nacen PRIVADAS para anon (regla 11 de AGENTS.md / 0149): `publicaciones` se da
-- por columnas y estas no se agregan al grant. Quedan en PRIVADAS de
-- test_publicaciones_columnas_publicas.py.
--
-- Idempotente. Una transacción, con comprobación al final.

begin;

alter table public.publicaciones add column if not exists updated_at timestamptz;
alter table public.publicaciones add column if not exists remitente_rol text;

update public.publicaciones set updated_at = created_at where updated_at is null;

alter table public.publicaciones alter column updated_at set default clock_timestamp();
alter table public.publicaciones alter column updated_at set not null;

alter table public.publicaciones drop constraint if exists publicaciones_remitente_rol_check;
alter table public.publicaciones add constraint publicaciones_remitente_rol_check
  check (remitente_rol is null or remitente_rol in ('merchant', 'third_party', 'uruku_explorer'));

comment on column public.publicaciones.updated_at is
  'Última modificación (trigger). Cursor de la API de integración. PRIVADA (regla 11).';
comment on column public.publicaciones.remitente_rol is
  'merchant | third_party | uruku_explorer, resuelto por la ingesta. NULL = anterior a la 0157. PRIVADA (regla 11).';

create or replace function public.publicaciones_set_updated_at() returns trigger
language plpgsql as $fn$
begin
  new.updated_at := clock_timestamp();
  return new;
end
$fn$;

revoke all on function public.publicaciones_set_updated_at() from public, anon, authenticated;

drop trigger if exists publicaciones_updated_at on public.publicaciones;
create trigger publicaciones_updated_at
  before update on public.publicaciones
  for each row
  execute function public.publicaciones_set_updated_at();

create index if not exists idx_publicaciones_updated_at_id on public.publicaciones (updated_at, id);

-- ============================================================ comprobación
do $chk$
declare
  v_rol text;
  v_col text;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    foreach v_col in array array['updated_at', 'remitente_rol'] loop
      if has_column_privilege(v_rol, 'public.publicaciones', v_col, 'select') then
        raise exception '0157: % puede leer publicaciones.% (es privada)', v_rol, v_col;
      end if;
    end loop;
  end loop;
  if not exists (select 1 from pg_trigger where tgrelid = 'public.publicaciones'::regclass
                 and tgname = 'publicaciones_updated_at' and not tgisinternal) then
    raise exception '0157: falta el trigger publicaciones_updated_at';
  end if;
  if exists (select 1 from public.publicaciones where updated_at is null) then
    raise exception '0157: quedaron publicaciones sin updated_at';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
