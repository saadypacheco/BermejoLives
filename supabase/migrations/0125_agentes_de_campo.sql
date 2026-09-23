-- Los agentes de campo: varios, cada uno con su ciudad.
--
-- Había UNO solo, con el usuario y la clave en el `.env` (AGENTE_EMAIL /
-- AGENTE_PASSWORD). Con dos ciudades más para cargar hacen falta varios, y
-- sumar uno no puede ser editar el `.env` y reiniciar el backend.
--
-- Cada agente tiene su ciudad: lo que carga nace en ESA ciudad, sin que
-- tenga que elegirla en el formulario (y sin que se equivoque). Y se ve
-- quién cargó qué, que hoy se pierde con una cuenta compartida.
--
-- La cuenta del `.env` sigue andando mientras exista: es la que está en los
-- teléfonos hoy y no se le corta el trabajo a nadie por un deploy.

create table if not exists agentes (
  id            uuid primary key default gen_random_uuid(),
  email         text not null unique,
  password_hash text not null,                -- pbkdf2_sha256$… (app/core/seguridad)
  nombre        text,
  ciudad_id     uuid references ciudades(id) on delete set null,
  activo        boolean not null default true,
  creado_por    text,
  created_at    timestamptz not null default now(),
  ultimo_acceso timestamptz
);
create index if not exists idx_agentes_activo on agentes (activo);

-- Sólo el backend: acá hay hashes de contraseña.
grant all on agentes to service_role;
alter table agentes enable row level security;
