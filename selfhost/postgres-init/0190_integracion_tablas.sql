-- API de integración para el sistema de marketing (docs/integracion-marketing.md).
--
-- Cuatro tablas nuevas. TODAS son operación interna: ninguna se lee ni se escribe desde el
-- sitio, así que anon y authenticated NO tienen ningún permiso (RLS activo y sin policies;
-- además `revoke all`, por si un default privilege del entorno les diera algo). Sólo
-- service_role (el backend) las toca, y sin DELETE salvo en la tabla de idempotencia (una
-- caché con vencimiento a los 7 días, no un dato de negocio). Baja lógica con `activo`.
--
--   integracion_clientes     Una fila por API KEY. Guarda sólo sha256(secreto): el secreto se
--                            muestra una vez al emitirla. `grupo_id` agrupa las claves de un
--                            mismo cliente (la rotación deja dos activas a la vez) y es el id de
--                            la PRIMERA clave: a él se ata el alcance.
--   integracion_comercios    El ALCANCE de un cliente: qué comercios puede ver y tocar. Estar acá
--                            (activo) es lo que vuelve "gestionado" a un comercio: toda
--                            publicación suya queda pendiente hasta que la apruebe la integración.
--                            Lo administra el admin de Uruku.
--   integracion_idempotencia Respuestas guardadas por (cliente, Idempotency-Key) durante 7 días.
--   integracion_eventos      Auditoría append-only: emisión/rotación/revocación de claves, cambios
--                            de alcance y overrides de admin sobre un comercio gestionado.
--
-- Idempotente: se puede correr dos veces. Una transacción, con comprobación al final.

begin;

-- ============================================================ integracion_clientes
create table if not exists public.integracion_clientes (
  id           uuid primary key default gen_random_uuid(),
  grupo_id     uuid not null,
  key_id       text not null,
  nombre       text not null,
  key_hash     text not null,
  scopes       text[] not null,
  activo       boolean not null default true,
  created_at   timestamptz not null default now(),
  last_used_at timestamptz,
  rotada_de    uuid references public.integracion_clientes(id),
  revocada_at  timestamptz,
  creado_por   text,
  constraint integracion_clientes_key_id_formato check (key_id ~ '^[A-Za-z0-9]{6,32}$'),
  constraint integracion_clientes_hash_formato  check (key_hash ~ '^[0-9a-f]{64}$'),
  constraint integracion_clientes_scopes_validos
    check (scopes <@ array['publications:read','publications:write','media:write','broadcast:send']::text[]),
  constraint integracion_clientes_nombre_largo  check (char_length(nombre) between 1 and 80),
  -- la primera clave de un cliente es su propio grupo; las rotadas heredan el del original
  constraint integracion_clientes_grupo check (grupo_id = id or rotada_de is not null)
);

create unique index if not exists integracion_clientes_key_id_uq on public.integracion_clientes (key_id);
create index if not exists idx_integracion_clientes_grupo on public.integracion_clientes (grupo_id);

comment on table public.integracion_clientes is
  'API keys de integración (una fila por clave). Guarda sólo sha256 del secreto. Sin acceso para anon/authenticated.';
comment on column public.integracion_clientes.key_hash is 'sha256 (hex) del secreto. El secreto se ve una sola vez, al emitir la clave.';
comment on column public.integracion_clientes.grupo_id is 'Id de la primera clave del cliente: a él se ata integracion_comercios (la rotación no copia alcance).';
comment on column public.integracion_clientes.rotada_de is 'Clave a la que reemplaza esta (rotación con dos activas a la vez).';

-- ============================================================ integracion_comercios
create table if not exists public.integracion_comercios (
  cliente_id   uuid not null references public.integracion_clientes(id),
  comercio_id  uuid not null references public.comercios(id),
  desde        timestamptz not null default now(),
  activo       boolean not null default true,
  agregado_por text,
  updated_at   timestamptz not null default now(),
  primary key (cliente_id, comercio_id)
);

create index if not exists idx_integracion_comercios_comercio
  on public.integracion_comercios (comercio_id) where activo;

comment on table public.integracion_comercios is
  'Alcance de cada cliente de integración (cliente_id = grupo_id). Un comercio con una fila activa acá es "gestionado": sus publicaciones quedan pendientes hasta que las apruebe la integración. Lo administra el admin de Uruku.';

-- ============================================================ integracion_idempotencia
create table if not exists public.integracion_idempotencia (
  cliente_id   uuid not null references public.integracion_clientes(id),
  key          text not null,
  request_hash text not null,
  status       integer not null,
  response     jsonb,
  created_at   timestamptz not null default now(),
  primary key (cliente_id, key),
  constraint integracion_idempotencia_key_largo check (char_length(key) between 1 and 128)
);

create index if not exists idx_integracion_idempotencia_created on public.integracion_idempotencia (created_at);

comment on table public.integracion_idempotencia is
  'Respuestas guardadas por (grupo de cliente, Idempotency-Key) durante 7 días. status 0 = en curso (reclamada, sin respuesta todavía).';

-- ============================================================ integracion_eventos
create table if not exists public.integracion_eventos (
  id          uuid primary key default gen_random_uuid(),
  cliente_id  uuid references public.integracion_clientes(id),
  comercio_id uuid references public.comercios(id),
  tipo        text not null,
  actor       text,
  detalle     jsonb,
  created_at  timestamptz not null default now()
);

create index if not exists idx_integracion_eventos_created on public.integracion_eventos (created_at desc);

comment on table public.integracion_eventos is
  'Auditoría append-only de la integración: claves, alcance y overrides de admin.';

-- ============================================================ permisos + RLS
alter table public.integracion_clientes     enable row level security;
alter table public.integracion_comercios    enable row level security;
alter table public.integracion_idempotencia enable row level security;
alter table public.integracion_eventos      enable row level security;

revoke all on public.integracion_clientes     from public, anon, authenticated;
revoke all on public.integracion_comercios    from public, anon, authenticated;
revoke all on public.integracion_idempotencia from public, anon, authenticated;
revoke all on public.integracion_eventos      from public, anon, authenticated;

-- La 0090 deja `alter default privileges ... grant all on tables to service_role`: cada tabla nueva
-- nace con TODO para service_role. Se le quita y se le da sólo lo que necesita (sin DELETE en lo
-- que es dato de negocio, y la auditoría append-only).
revoke all on public.integracion_clientes     from service_role;
revoke all on public.integracion_comercios    from service_role;
revoke all on public.integracion_idempotencia from service_role;
revoke all on public.integracion_eventos      from service_role;

grant select, insert, update         on public.integracion_clientes     to service_role;
grant select, insert, update         on public.integracion_comercios    to service_role;
grant select, insert, update, delete on public.integracion_idempotencia to service_role;   -- caché con TTL
grant select, insert                 on public.integracion_eventos      to service_role;   -- append-only

-- ============================================================ comprobación
do $chk$
declare
  v_rol text;
  v_tabla text;
begin
  foreach v_tabla in array array['integracion_clientes', 'integracion_comercios',
                                 'integracion_idempotencia', 'integracion_eventos'] loop
    if not (select relrowsecurity from pg_class where oid = ('public.' || v_tabla)::regclass) then
      raise exception '0190: % sin RLS', v_tabla;
    end if;
    foreach v_rol in array array['anon', 'authenticated'] loop
      if has_table_privilege(v_rol, 'public.' || v_tabla, 'select')
         or has_table_privilege(v_rol, 'public.' || v_tabla, 'insert')
         or has_table_privilege(v_rol, 'public.' || v_tabla, 'update')
         or has_table_privilege(v_rol, 'public.' || v_tabla, 'delete') then
        raise exception '0190: % tiene permisos sobre %', v_rol, v_tabla;
      end if;
    end loop;
    if not has_table_privilege('service_role', 'public.' || v_tabla, 'select')
       or not has_table_privilege('service_role', 'public.' || v_tabla, 'insert') then
      raise exception '0190: service_role no puede leer/escribir %', v_tabla;
    end if;
  end loop;
  if has_table_privilege('service_role', 'public.integracion_eventos', 'update')
     or has_table_privilege('service_role', 'public.integracion_eventos', 'delete') then
    raise exception '0190: integracion_eventos tiene que ser append-only';
  end if;
  if has_table_privilege('service_role', 'public.integracion_clientes', 'delete')
     or has_table_privilege('service_role', 'public.integracion_comercios', 'delete') then
    raise exception '0190: sin borrado físico (baja lógica con activo)';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
