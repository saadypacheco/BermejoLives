-- Cuenta liviana para compradores/visitantes (NO comercios): solo celular +
-- código de verificación por WhatsApp. Objetivo único: tener el número con
-- consentimiento para avisos/ofertas, y permitir guardar comercios favoritos
-- desde cualquier dispositivo.
create table usuarios (
  id uuid primary key default gen_random_uuid(),
  whatsapp text not null unique,
  reset_code text,
  reset_code_expira timestamptz,
  consentimiento_ofertas boolean not null default true,
  activo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table favoritos (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios(id) on delete cascade,
  comercio_id uuid not null references comercios(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (usuario_id, comercio_id)
);

create index idx_favoritos_usuario on favoritos(usuario_id);

alter table usuarios enable row level security;
alter table favoritos enable row level security;

grant all on public.usuarios to service_role;
grant all on public.favoritos to service_role;
