-- 0159 · Fotos que no se pierden, eventos de grupo de WAHA y mapa LID <-> número.
--
-- E1 de docs/grupos-por-comercio.md.
--
--  1. wa_inbox guarda dónde quedó la foto de un número desconocido (disco PRIVADO
--     del backend, nunca bajo /fotos) y quién dijo «es de…».
--  2. wa_group_events: los eventos de grupo de WAHA, crudos (como wa_inbox para
--     los mensajes). Idempotente por dedupe_key.
--  3. wa_lid_map: LID <-> número aprendido de los mensajes (participantAlt /
--     remoteJidAlt) o de WAHA.
--
-- Las tablas nuevas son SÓLO del backend (service_role): anon y authenticated no
-- tienen ningún permiso. Sin borrado físico: el mapa LID baja con `activo`.

begin;

alter table public.wa_inbox add column if not exists media_path      text;          -- dentro de WA_RECEIVED_DIR (disco PRIVADO)
alter table public.wa_inbox add column if not exists media_purged_at timestamptz;   -- se borró el archivo; la fila queda
alter table public.wa_inbox add column if not exists assigned_by     text;          -- quién dijo «es de…»
alter table public.wa_inbox add column if not exists assigned_at     timestamptz;

comment on column public.wa_inbox.media_path is
  'Ruta RELATIVA de la foto guardada en el disco privado del backend (WA_RECEIVED_DIR). Nunca bajo /fotos.';
comment on column public.wa_inbox.media_purged_at is
  'Cuándo se borró el archivo por la retención. La fila queda.';
comment on column public.wa_inbox.assigned_by is
  'Correo de quien dijo de qué comercio era el número («Es de…»).';

create index if not exists idx_wa_inbox_phone_sin_comercio
  on public.wa_inbox (phone, created_at desc) where resultado = 'sin_comercio';
create index if not exists idx_wa_inbox_jid_sin_comercio
  on public.wa_inbox (wa_jid, created_at desc) where resultado = 'sin_comercio';
create index if not exists idx_wa_inbox_media_vigente
  on public.wa_inbox (created_at) where media_path is not null and media_purged_at is null;

-- Eventos de grupo de WAHA, crudos.
create table if not exists public.wa_group_events (
  id           uuid primary key default gen_random_uuid(),
  dedupe_key   text not null unique,   -- sha256(evento|grupo|tipo|participantes ordenados|timestamp)
  event        text not null,          -- group.v2.join | group.v2.leave | group.v2.participants | group.v2.update
  group_jid    text,
  change_type  text,                   -- join | leave | promote | demote
  participants jsonb,
  raw          jsonb not null,
  result       text,                   -- captured | community_member | merchant_matched | group_bound | task_waiting | unbound | ignored | error
  reason       text,
  created_at   timestamptz not null default now()
);
create index if not exists idx_wa_group_events_group
  on public.wa_group_events (group_jid, created_at desc);

comment on table public.wa_group_events is
  'Eventos de grupo de WAHA tal como llegaron. Sólo el backend.';

-- LID <-> número, aprendido de los mensajes o de WAHA.
create table if not exists public.wa_lid_map (
  lid           text primary key check (lid like '%@lid'),
  phone         text not null,                       -- E.164 sin '+'
  source        text not null check (source in ('message', 'event', 'waha_api', 'admin')),
  first_seen_at timestamptz not null default now(),
  last_seen_at  timestamptz not null default now(),
  activo        boolean not null default true
);
create index if not exists idx_wa_lid_map_phone
  on public.wa_lid_map (phone) where activo;

comment on table public.wa_lid_map is
  'Identificador oculto de WhatsApp (LID) y el número que hay detrás. Sólo el backend.';

alter table public.wa_group_events enable row level security;
alter table public.wa_lid_map      enable row level security;

revoke all on public.wa_group_events, public.wa_lid_map from public, anon, authenticated;
grant all on public.wa_group_events, public.wa_lid_map to service_role;

-- ============================================================ comprobación
-- Si algo no quedó como debe, se revierte todo.
do $chk$
declare
  v_rol text;
  v_tabla text;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    foreach v_tabla in array array['public.wa_inbox', 'public.wa_group_events', 'public.wa_lid_map'] loop
      if has_table_privilege(v_rol, v_tabla, 'select')
         or has_table_privilege(v_rol, v_tabla, 'insert')
         or has_table_privilege(v_rol, v_tabla, 'update')
         or has_table_privilege(v_rol, v_tabla, 'delete') then
        raise exception '0159: % tiene permisos sobre %', v_rol, v_tabla;
      end if;
    end loop;
    if has_column_privilege(v_rol, 'public.wa_inbox', 'media_path', 'select') then
      raise exception '0159: % puede leer wa_inbox.media_path', v_rol;
    end if;
  end loop;
  foreach v_tabla in array array['public.wa_group_events', 'public.wa_lid_map'] loop
    if not (select relrowsecurity from pg_class where oid = v_tabla::regclass) then
      raise exception '0159: % sin RLS', v_tabla;
    end if;
    if not has_table_privilege('service_role', v_tabla, 'insert')
       or not has_table_privilege('service_role', v_tabla, 'update') then
      raise exception '0159: service_role perdió un permiso sobre %', v_tabla;
    end if;
  end loop;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
