-- ============================================================
-- Bermejo Live Market · 0004_comercio_login_confiable
-- Cuentas de comercio (login propio, patrón JWT del backend) + flag 'confiable'.
--
-- 'confiable' = comercio de confianza: sus publicaciones se publican DIRECTO
-- (estado='aprobado'), sin pasar por moderación. Aplica tanto al chatbot
-- in-site como a la ingesta por WhatsApp.
-- ============================================================

-- Flag de confianza en el comercio
alter table comercios add column if not exists confiable boolean not null default false;

-- Usuarios de comercio (login del panel del vendedor).
-- No usamos Supabase Auth acá para mantener el mismo patrón JWT que el admin;
-- el backend (service_role) es el único que lee esta tabla.
create table if not exists comercio_usuarios (
  id            uuid primary key default gen_random_uuid(),
  comercio_id   uuid not null references comercios(id) on delete cascade,
  email         text not null unique,
  password_hash text not null,                  -- pbkdf2_sha256$...
  nombre        text,
  activo        boolean not null default true,
  created_at    timestamptz not null default now()
);
create index if not exists idx_comercio_usuarios_comercio on comercio_usuarios (comercio_id);

-- GRANTs: solo service_role (el backend). anon/authenticated NO acceden.
grant all on comercio_usuarios to service_role;

-- RLS activo sin policies para anon/authenticated => sin acceso (lo lee el backend).
alter table comercio_usuarios enable row level security;

-- ------------------------------------------------------------
-- Seed de cuentas demo (password: comercio1234)
--   - Importadora ABC -> confiable (publica directo)
--   - Moda Bermejo     -> NO confiable (pasa por moderación)
-- ------------------------------------------------------------
update comercios set confiable = true  where slug = 'importadora-abc';
update comercios set confiable = false where slug = 'moda-bermejo';

insert into comercio_usuarios (comercio_id, email, password_hash, nombre)
select c.id, v.email, v.ph, v.nombre
from comercios c
join (values
  ('importadora-abc', 'abc@bermejolive.com',  'pbkdf2_sha256$100000$8fd868428c77aa2f4e3a10675c237329$254cab062b086e21281f26a364b8dfb157b49451d656a5bca689d6632994facf', 'Importadora ABC'),
  ('moda-bermejo',    'moda@bermejolive.com', 'pbkdf2_sha256$100000$8fd868428c77aa2f4e3a10675c237329$254cab062b086e21281f26a364b8dfb157b49451d656a5bca689d6632994facf', 'Moda Bermejo')
) as v(slug, email, ph, nombre)
  on c.slug = v.slug
on conflict (email) do nothing;
