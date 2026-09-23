-- Los usuarios del sistema y sus roles, en la base.
--
-- Hasta hoy: admin, publicador y agente eran tres pares correo/clave en el
-- `.env`, en texto plano, compartidos. Sumar a alguien era editar un archivo
-- del servidor y reiniciar; y como la cuenta era una sola, no se sabía quién
-- hizo cada cosa. Los permisos, además, estaban escritos endpoint por
-- endpoint: `require_admin` en 68 lugares, `require_moderador` en 28. Un rol
-- nuevo era tocar cien archivos.
--
-- Ahora:
--   usuarios_panel   quién es (correo, clave cifrada, nombre, ciudad)
--   roles            qué puede hacer un rol (lista de permisos)
--   usuario_roles    quién tiene qué rol (uno puede tener varios)
--
-- El CATÁLOGO de permisos vive en el código (app/core/permisos.py): un
-- permiso es algo que el código sabe hacer, y un tilde que no corresponde a
-- ningún endpoint es peor que no tener el tilde. Lo que se arma desde el
-- panel es qué permisos lleva cada rol, y los roles nuevos.
--
-- El `.env` sigue funcionando mientras tenga valores: es la llave de
-- emergencia si alguien se queda afuera. Lo que hay en la base gana.

create table if not exists roles (
  slug        text primary key,
  nombre      text not null,
  descripcion text,
  permisos    text[] not null default '{}',
  -- Los del sistema no se borran: si alguien borra "admin" no entra nadie.
  del_sistema boolean not null default false,
  created_at  timestamptz not null default now()
);

insert into roles (slug, nombre, descripcion, permisos, del_sistema) values
  ('admin',      'Administrador',   'Todo. Es el rol de quien maneja URUKU.', array['*'], true),
  ('moderador',  'Moderador',       'Aprueba lo que llega, corrige fichas y contesta la Ayuda.',
   array['moderar','comercios.editar','ayuda','lugares','whatsapp'], true),
  ('publicador', 'Publicador',      'Carga la cotización, el estado del paso y los videos.',
   array['contenido','moderar'], true),
  ('agente',     'Agente de campo', 'Carga comercios desde la calle, en su ciudad.',
   array['comercios.cargar'], true)
on conflict (slug) do update set
  nombre = excluded.nombre, descripcion = excluded.descripcion, del_sistema = true;
-- Los permisos NO se pisan al re-aplicar: si alguien ajustó un rol desde el
-- panel, una migración no tiene por qué deshacerlo.

create table if not exists usuarios_panel (
  id            uuid primary key default gen_random_uuid(),
  email         text not null unique,
  password_hash text not null,
  nombre        text,
  -- Para los agentes: dónde carga. Para el resto, informativo.
  ciudad_id     uuid references ciudades(id) on delete set null,
  activo        boolean not null default true,
  creado_por    text,
  created_at    timestamptz not null default now(),
  ultimo_acceso timestamptz
);
create index if not exists idx_usuarios_panel_activo on usuarios_panel (activo);

create table if not exists usuario_roles (
  usuario_id uuid not null references usuarios_panel(id) on delete cascade,
  rol_slug   text not null references roles(slug) on delete cascade,
  primary key (usuario_id, rol_slug)
);

-- Los agentes de la 0125 pasan acá con su rol. La tabla vieja queda un
-- tiempo por si hay que mirar algo; el login ya no la usa.
insert into usuarios_panel (id, email, password_hash, nombre, ciudad_id, activo, creado_por, created_at, ultimo_acceso)
select a.id, a.email, a.password_hash, a.nombre, a.ciudad_id, a.activo, a.creado_por, a.created_at, a.ultimo_acceso
  from agentes a
 where not exists (select 1 from usuarios_panel u where u.email = a.email)
on conflict (id) do nothing;
insert into usuario_roles (usuario_id, rol_slug)
select u.id, 'agente' from usuarios_panel u
 where exists (select 1 from agentes a where a.email = u.email)
on conflict do nothing;

grant all on roles, usuarios_panel, usuario_roles to service_role;
alter table roles enable row level security;
alter table usuarios_panel enable row level security;
alter table usuario_roles enable row level security;
