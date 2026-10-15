-- Farmacias de turno (docs/farmacias-de-turno.md).
--
-- En Bolivia el turno farmacéutico dura 24 horas: de las 08:00 del día indicado a las 08:00
-- del día siguiente (DS 25235, art. 74). Cada fila de `turnos_farmacia` es "esta farmacia
-- está de turno ese día"; `inicio` y `fin` guardan el instante exacto (hora de La Paz, UTC-4),
-- así "de turno ahora" es `inicio <= now() < fin`, sin cuentas de zona horaria en el sitio.
--
-- Cómo está dado el acceso (regla de la 0145/0149/0150: una columna nueva nace PRIVADA):
--   * anon y authenticated leen SÓLO los turnos activos (policy) y SÓLO las columnas
--     id, comercio_id, fecha, inicio, fin. `fuente`, `activo` y `created_at` son internas:
--     para el sitio la policy ya filtra por `activo`, no hace falta pedirla ni filtrarla.
--     Nunca un grant de tabla entera: `select=*` por la API falla (42501).
--   * service_role (el backend) hace todo. Es la única vía de escritura (la importación).
--   * Baja LÓGICA (`activo = false`), nunca DELETE físico.
--
-- En `comercios` se suman dos columnas que nacen PRIVADAS (regla 11 de AGENTS.md; no se hace
-- `grant select (columna)` para anon, y quedan en PRIVADAS_EXTRA de test_comercios_columnas_publicas):
--   * ubicacion_aproximada: el punto se calculó cruzando calles desde la dirección y no se
--     tomó con el GPS en la puerta. La app del agente avisa; al re-tomar el GPS pasa a false.
--   * nota_interna: dudas o avisos para el equipo (p. ej. "la fuente trae dos celulares").
--
-- Idempotente: se puede correr dos veces. Una transacción, con comprobación al final.

begin;

-- ============================================================ comercios
alter table public.comercios
  add column if not exists ubicacion_aproximada boolean not null default false,
  add column if not exists nota_interna text;

comment on column public.comercios.ubicacion_aproximada is
  'true = lat/lng calculados desde la dirección (cruce de calles), no tomados con el GPS en la puerta. PRIVADA (regla 11): la ve el equipo, no el público.';
comment on column public.comercios.nota_interna is
  'Dudas o avisos internos del equipo sobre la ficha. PRIVADA (regla 11): nunca se publica.';

-- ============================================================ turnos_farmacia
create table if not exists public.turnos_farmacia (
  id          uuid primary key default gen_random_uuid(),
  comercio_id uuid not null references public.comercios(id),
  fecha       date not null,
  inicio      timestamptz not null,
  fin         timestamptz not null,
  fuente      text,
  activo      boolean not null default true,
  created_at  timestamptz not null default now(),
  constraint turnos_farmacia_fin_despues_de_inicio check (fin > inicio)
);

comment on table public.turnos_farmacia is
  'Turnos de las farmacias (24 h, de 08:00 a 08:00 del día siguiente, hora de La Paz). Lectura pública sólo de los activos y de id, comercio_id, fecha, inicio, fin. Baja lógica con activo = false.';
comment on column public.turnos_farmacia.fecha is 'Día en que empieza el turno (hora de La Paz).';
comment on column public.turnos_farmacia.inicio is 'Instante en que empieza el turno: la fecha a las 08:00 de La Paz (UTC-4).';
comment on column public.turnos_farmacia.fin is 'Instante en que termina: inicio + 24 h. "De turno ahora" = inicio <= now() < fin.';
comment on column public.turnos_farmacia.fuente is 'De dónde salió el rol (PRIVADA).';
comment on column public.turnos_farmacia.activo is 'Baja lógica: false = el turno no se ve en el sitio (PRIVADA; la policy ya filtra).';

-- Una farmacia, un turno por día: es la clave del upsert de la importación.
create unique index if not exists turnos_farmacia_comercio_fecha_uq
  on public.turnos_farmacia (comercio_id, fecha);

create index if not exists idx_turnos_farmacia_vigentes
  on public.turnos_farmacia (inicio, fin) where activo;

-- ============================================================ permisos + RLS
alter table public.turnos_farmacia enable row level security;

drop policy if exists turnos_farmacia_public_read on public.turnos_farmacia;
create policy turnos_farmacia_public_read on public.turnos_farmacia
  for select to anon, authenticated using (activo);

-- Se parte de cero (por si un default privilege le dio la tabla entera a anon) y se da por columnas.
revoke all on public.turnos_farmacia from public, anon, authenticated;

grant select (id, comercio_id, fecha, inicio, fin) on public.turnos_farmacia to anon, authenticated;

grant all on public.turnos_farmacia to service_role;

-- ============================================================ comprobación
do $chk$
declare
  v_rol text;
  v_col text;
begin
  if not exists (select 1 from information_schema.columns
                 where table_schema = 'public' and table_name = 'comercios'
                   and column_name = 'ubicacion_aproximada' and is_nullable = 'NO') then
    raise exception '0154: falta comercios.ubicacion_aproximada (not null)';
  end if;
  if not exists (select 1 from information_schema.columns
                 where table_schema = 'public' and table_name = 'comercios'
                   and column_name = 'nota_interna') then
    raise exception '0154: falta comercios.nota_interna';
  end if;
  if not exists (select 1 from pg_indexes
                 where schemaname = 'public' and indexname = 'turnos_farmacia_comercio_fecha_uq') then
    raise exception '0154: falta el único (comercio_id, fecha) de turnos_farmacia';
  end if;
  if not (select relrowsecurity from pg_class where oid = 'public.turnos_farmacia'::regclass) then
    raise exception '0154: turnos_farmacia sin RLS';
  end if;
  if not exists (select 1 from pg_policies
                 where schemaname = 'public' and tablename = 'turnos_farmacia'
                   and policyname = 'turnos_farmacia_public_read') then
    raise exception '0154: falta la policy de lectura pública de turnos_farmacia';
  end if;
  foreach v_rol in array array['anon', 'authenticated'] loop
    foreach v_col in array array['id', 'comercio_id', 'fecha', 'inicio', 'fin'] loop
      if not has_column_privilege(v_rol, 'public.turnos_farmacia', v_col, 'select') then
        raise exception '0154: % no puede leer turnos_farmacia.%', v_rol, v_col;
      end if;
    end loop;
    foreach v_col in array array['fuente', 'activo', 'created_at'] loop
      if has_column_privilege(v_rol, 'public.turnos_farmacia', v_col, 'select') then
        raise exception '0154: % puede leer turnos_farmacia.% (es privada)', v_rol, v_col;
      end if;
    end loop;
    if has_table_privilege(v_rol, 'public.turnos_farmacia', 'insert')
       or has_table_privilege(v_rol, 'public.turnos_farmacia', 'update')
       or has_table_privilege(v_rol, 'public.turnos_farmacia', 'delete') then
      raise exception '0154: % puede escribir turnos_farmacia', v_rol;
    end if;
    foreach v_col in array array['ubicacion_aproximada', 'nota_interna'] loop
      if has_column_privilege(v_rol, 'public.comercios', v_col, 'select') then
        raise exception '0154: % puede leer comercios.% (es privada)', v_rol, v_col;
      end if;
    end loop;
  end loop;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
