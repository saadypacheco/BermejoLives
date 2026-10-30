-- 0163 · Credencial de los agentes de campo.
--
-- Etapa E5 de docs/grupos-por-comercio.md, con los cambios de
-- docs/credencial-agentes.md (gana esta última).
--
-- Cada agente lleva una credencial impresa con su foto, nombre y apellido y un QR.
-- Quien escanea el QR ve en uruku.bo si esa persona es agente de URUKU o ya no lo es.
--
--  1. usuarios_panel: `apellido` y `photo_url` (la foto de la credencial).
--  2. agent_credentials: una fila por credencial emitida. Revocar = activo=false
--     más revoked_*; nunca se borra. El índice único parcial garantiza que un
--     agente no tenga dos credenciales vivas.
--
-- La tabla es SÓLO del backend (service_role): anon y authenticated no tienen
-- ningún permiso. Nada se lee por PostgREST; la página pública pasa por la API.

begin;

alter table public.usuarios_panel add column if not exists apellido  text;
alter table public.usuarios_panel add column if not exists photo_url text;

comment on column public.usuarios_panel.apellido  is 'Apellido de la persona (va en la credencial).';
comment on column public.usuarios_panel.photo_url is 'URL pública de la foto de la credencial (/fotos/agentes/<aleatorio>.jpg).';

create table if not exists public.agent_credentials (
  id            uuid primary key default gen_random_uuid(),
  usuario_id    uuid not null references public.usuarios_panel(id),
  -- secrets.token_urlsafe(16): 128 bits, 22 caracteres. Es lo que lleva el QR.
  token         text not null unique check (length(token) >= 22),
  activo        boolean not null default true,        -- true = vigente
  issued_by     text,
  issued_at     timestamptz not null default now(),
  revoked_by    text,
  revoked_at    timestamptz,
  revoke_reason text,
  last_scan_at  timestamptz,
  scan_count    int not null default 0
);

-- Nunca dos credenciales vivas para el mismo agente.
create unique index if not exists uq_agent_credentials_vigente
  on public.agent_credentials (usuario_id) where activo;
create index if not exists idx_agent_credentials_usuario
  on public.agent_credentials (usuario_id, issued_at desc);

comment on table public.agent_credentials is
  'Credenciales de agente (QR). Revocar = activo=false; no se borra. Sólo el backend.';
comment on column public.agent_credentials.activo is 'true = vigente. Hay a lo sumo una vigente por agente.';

alter table public.agent_credentials enable row level security;

revoke all on public.agent_credentials from public, anon, authenticated;
grant all on public.agent_credentials to service_role;

-- ============================================================ comprobación
do $chk$
declare
  v_rol text;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    if has_table_privilege(v_rol, 'public.agent_credentials', 'select')
       or has_table_privilege(v_rol, 'public.agent_credentials', 'insert')
       or has_table_privilege(v_rol, 'public.agent_credentials', 'update')
       or has_table_privilege(v_rol, 'public.agent_credentials', 'delete') then
      raise exception '0163: % tiene permisos sobre agent_credentials', v_rol;
    end if;
  end loop;
  if not (select relrowsecurity from pg_class where oid = 'public.agent_credentials'::regclass) then
    raise exception '0163: agent_credentials sin RLS';
  end if;
  if not has_table_privilege('service_role', 'public.agent_credentials', 'update') then
    raise exception '0163: service_role sin permiso de update sobre agent_credentials';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
