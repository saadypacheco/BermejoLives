-- 0184 · Teléfonos en las fotos de los comercios.
--
-- Spec: docs/telefonos-en-fotos.md.
--
--  1. cost_switches: el check de la clave suma 'gemini_phone_scan' (leer los teléfonos de las
--     portadas con Gemini en vez del lector gratis). El check de la 0183 es el de columna, que
--     Postgres llama `cost_switches_key_check`.
--  2. fotos_escaneadas: qué foto ya se leyó y con qué motor. Una portada que cambia de URL es otra
--     fila, así que se vuelve a leer sola.
--  3. telefonos_detectados: cada número leído es una PROPUESTA. Nada se escribe solo en la ficha del
--     comercio: una persona lo aplica o lo descarta desde el panel.
--  4. portadas_sin_escanear y telefonos_resumen: lo que el worker y el panel necesitan y PostgREST no
--     sabe pedir (un «no existe» entre dos tablas). Sólo para service_role.
--
-- Todo es SÓLO del backend (service_role): anon y authenticated no tienen ningún permiso. `comercios`
-- no se toca: las funciones la leen por columnas.
-- Sin borrado físico: lo descartado queda con estado 'descartado' y lo dado de baja con `activo`.
-- Idempotente: se puede correr dos veces.

begin;

-- ───────────────────────────────────────────── 1. interruptor de costo
alter table public.cost_switches drop constraint if exists cost_switches_key_check;
alter table public.cost_switches
  add constraint cost_switches_key_check check (key in ('gemini_content', 'gemini_phone_scan'));

-- ───────────────────────────────────────────── 2. fotos ya leídas
create table if not exists public.fotos_escaneadas (
  foto_url     text not null,
  motor        text not null check (motor in ('tesseract', 'gemini', 'gemini-relevamiento')),
  comercio_id  uuid not null references public.comercios(id),
  numeros      int not null default 0,
  error        text,
  escaneada_at timestamptz not null default now(),
  primary key (foto_url, motor)
);
create index if not exists idx_fotos_escaneadas_comercio on public.fotos_escaneadas (comercio_id);

comment on table public.fotos_escaneadas is
  'Qué foto ya se leyó en busca de teléfonos y con qué motor. Un error se reintenta a los 7 días. Sólo el backend.';

-- ───────────────────────────────────────────── 3. teléfonos propuestos
create table if not exists public.telefonos_detectados (
  id            uuid primary key default gen_random_uuid(),
  comercio_id   uuid not null references public.comercios(id),
  numero        text not null,                 -- E.164 (+591…, +54…)
  tipo          text not null check (tipo in ('celular', 'fijo')),
  texto_leido   text not null check (length(texto_leido) <= 60),
  foto_url      text not null,
  motor         text not null,
  estado        text not null default 'pendiente' check (estado in
                ('pendiente', 'coincide', 'aplicado_whatsapp', 'aplicado_telefono', 'descartado')),
  compartido    boolean not null default false,
  revisado_por  text,
  revisado_at   timestamptz,
  activo        boolean not null default true,
  created_at    timestamptz not null default now(),
  unique (comercio_id, numero)
);
create index if not exists idx_telefonos_detectados_numero on public.telefonos_detectados (numero) where activo;
create index if not exists idx_telefonos_detectados_estado on public.telefonos_detectados (estado, created_at desc) where activo;

comment on table public.telefonos_detectados is
  'Teléfonos leídos en las fotos de los comercios: propuestas que una persona aplica o descarta. Sólo el backend.';
comment on column public.telefonos_detectados.compartido is
  'El número aparece en 4 o más comercios (galería, administración, agente): no se ofrece en el lote.';

alter table public.fotos_escaneadas enable row level security;
alter table public.telefonos_detectados enable row level security;
revoke all on public.fotos_escaneadas from public, anon, authenticated;
revoke all on public.telefonos_detectados from public, anon, authenticated;
grant all on public.fotos_escaneadas to service_role;
grant all on public.telefonos_detectados to service_role;

-- ───────────────────────────────────────────── 4. funciones para el worker y el panel
-- Las portadas de los comercios activos que todavía no se leyeron con este motor (o que ya las leyó el
-- relevamiento por fotos, que no cuesta nada más). Primero los comercios SIN WhatsApp. Un error
-- anterior se reintenta a los 7 días.
create or replace function public.portadas_sin_escanear(
  p_motor text, p_limit integer default 20, p_ciudad_id uuid default null)
returns table (comercio_id uuid, portada_url text, whatsapp text, telefono text, ciudad_id uuid)
language sql stable
set search_path = public
as $fn$
  select c.id, c.portada_url, c.whatsapp, c.telefono, c.ciudad_id
    from public.comercios c
   where c.activo
     and c.portada_url is not null and c.portada_url <> ''
     and (p_ciudad_id is null or c.ciudad_id = p_ciudad_id)
     and not exists (select 1 from public.fotos_escaneadas f
                      where f.foto_url = c.portada_url
                        and f.motor in (p_motor, 'gemini-relevamiento')
                        and (f.error is null or f.escaneada_at > now() - interval '7 days'))
   order by (coalesce(btrim(c.whatsapp), '') = '') desc, c.created_at, c.id
   limit greatest(1, least(coalesce(p_limit, 20), 200));
$fn$;

-- Los cuatro números de arriba del panel, en una sola vuelta.
create or replace function public.telefonos_resumen(p_motor text, p_ciudad_id uuid default null)
returns json
language sql stable
set search_path = public
as $fn$
  select json_build_object(
    'escaneadas', (select count(distinct f.foto_url)
                     from public.fotos_escaneadas f
                     join public.comercios c on c.id = f.comercio_id
                    where c.activo and (p_ciudad_id is null or c.ciudad_id = p_ciudad_id)),
    'pendientes_de_escanear', (select count(*)
                     from public.comercios c
                    where c.activo
                      and c.portada_url is not null and c.portada_url <> ''
                      and (p_ciudad_id is null or c.ciudad_id = p_ciudad_id)
                      and not exists (select 1 from public.fotos_escaneadas f
                                       where f.foto_url = c.portada_url
                                         and f.motor in (p_motor, 'gemini-relevamiento')
                                         and (f.error is null or f.escaneada_at > now() - interval '7 days'))),
    'numeros', (select count(*)
                  from public.telefonos_detectados t
                  join public.comercios c on c.id = t.comercio_id
                 where t.activo and c.activo and (p_ciudad_id is null or c.ciudad_id = p_ciudad_id)),
    'sin_whatsapp_con_numero', (select count(distinct t.comercio_id)
                  from public.telefonos_detectados t
                  join public.comercios c on c.id = t.comercio_id
                 where t.activo and c.activo
                   and t.estado = 'pendiente' and t.tipo = 'celular' and not t.compartido
                   and coalesce(btrim(c.whatsapp), '') = ''
                   and (p_ciudad_id is null or c.ciudad_id = p_ciudad_id))
  );
$fn$;

revoke all on function public.portadas_sin_escanear(text, integer, uuid) from public, anon, authenticated;
revoke all on function public.telefonos_resumen(text, uuid) from public, anon, authenticated;
grant execute on function public.portadas_sin_escanear(text, integer, uuid) to service_role;
grant execute on function public.telefonos_resumen(text, uuid) to service_role;

-- ───────────────────────────────────────────── comprobación (si algo falla, no queda nada)
do $chk$
declare
  v_rol text;
  v_tabla text;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    foreach v_tabla in array array['fotos_escaneadas', 'telefonos_detectados'] loop
      if has_table_privilege(v_rol, 'public.' || v_tabla, 'select')
         or has_table_privilege(v_rol, 'public.' || v_tabla, 'insert')
         or has_table_privilege(v_rol, 'public.' || v_tabla, 'update')
         or has_table_privilege(v_rol, 'public.' || v_tabla, 'delete') then
        raise exception '0184: % tiene permisos sobre %', v_rol, v_tabla;
      end if;
    end loop;
    if has_function_privilege(v_rol, 'public.portadas_sin_escanear(text, integer, uuid)', 'execute')
       or has_function_privilege(v_rol, 'public.telefonos_resumen(text, uuid)', 'execute') then
      raise exception '0184: % puede ejecutar las funciones de teléfonos', v_rol;
    end if;
  end loop;
  foreach v_tabla in array array['fotos_escaneadas', 'telefonos_detectados'] loop
    if not has_table_privilege('service_role', 'public.' || v_tabla, 'insert')
       or not has_table_privilege('service_role', 'public.' || v_tabla, 'update') then
      raise exception '0184: service_role no puede escribir %', v_tabla;
    end if;
  end loop;
  if not has_function_privilege('service_role', 'public.portadas_sin_escanear(text, integer, uuid)', 'execute')
     or not has_function_privilege('service_role', 'public.telefonos_resumen(text, uuid)', 'execute') then
    raise exception '0184: service_role no puede ejecutar las funciones de teléfonos';
  end if;
  if not exists (select 1 from pg_constraint
                  where conname = 'cost_switches_key_check'
                    and conrelid = 'public.cost_switches'::regclass
                    and pg_get_constraintdef(oid) like '%gemini_phone_scan%') then
    raise exception '0184: el check de cost_switches no admite gemini_phone_scan';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
