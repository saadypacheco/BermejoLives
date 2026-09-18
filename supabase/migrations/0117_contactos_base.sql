-- La base de compradores: números y el grupo del que vienen.
--
-- Viene de un Excel con miles de compradores y los grupos de WhatsApp a
-- los que pertenecen (tours de compras, grupos por ciudad). Decidido el
-- 13/9 y ratificado el 17/9: NO se le escribe a nadie desde los números de
-- URUKU. Sirve para tres cosas que no mandan un solo mensaje:
--
--   1. Saber de dónde vienen los compradores (por grupo, por ciudad).
--   2. Cruzar con `usuarios` (los que entran con su WhatsApp) y saber qué
--      parte de la base ya usa URUKU, y de qué grupos.
--   3. Darle a cada grupo un enlace propio (`?ref=grupo-<slug>`) para que
--      lo publique SU administrador; las llegadas se cuentan en leads.origen.
--
-- Sólo el backend la lee (service_role). Son datos personales: no salen a
-- anon ni a authenticated, y el panel muestra conteos, no listas de números.

create table if not exists contactos_base (
  id          uuid primary key default gen_random_uuid(),
  telefono    text not null,             -- dígitos con país: 549…, 591…
  grupo       text not null default '',  -- como está en el Excel
  grupo_slug  text not null default '',  -- para el ?ref=grupo-<slug>
  ciudad      text,
  nombre      text,
  origen      text,                      -- el archivo del que vino
  valido      boolean not null default true,
  creado_en   timestamptz not null default now(),
  unique (telefono, grupo_slug)
);
create index if not exists idx_contactos_base_grupo on contactos_base (grupo_slug);
create index if not exists idx_contactos_base_telefono on contactos_base (telefono);

grant all on contactos_base to service_role;
alter table contactos_base enable row level security;
-- Sin políticas para anon/authenticated: sólo service_role, que saltea RLS.
