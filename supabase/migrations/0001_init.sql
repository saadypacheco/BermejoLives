-- ============================================================
-- Bermejo Live Market · 0001_init
-- Esquema base: zonas, comercios, productos, publicaciones (feed),
-- e ingesta de WhatsApp. Comentarios en español.
-- ============================================================

create extension if not exists "pgcrypto";   -- gen_random_uuid()

-- ------------------------------------------------------------
-- ZONAS comerciales (conceptuales, NO calles reales)
-- ------------------------------------------------------------
create table if not exists zonas (
  id          uuid primary key default gen_random_uuid(),
  slug        text not null unique,             -- 'zona-moda', 'importadoras'...
  nombre      text not null,                    -- 'Zona Moda'
  descripcion text,
  color       text,                             -- acento UI (#hex)
  icono       text,                             -- nombre de icono UI
  orden       int  not null default 0,
  activo      boolean not null default true,
  created_at  timestamptz not null default now()
);

-- ------------------------------------------------------------
-- COMERCIOS (vendedores) — entidad central del producto
-- Incluye TODOS los datos de contacto/redes/ubicación que pediste.
-- ------------------------------------------------------------
create table if not exists comercios (
  id            uuid primary key default gen_random_uuid(),
  slug          text not null unique,           -- url pública: /comercios/<slug>
  nombre        text not null,
  descripcion   text,

  -- Identidad / branding
  logo_url      text,
  portada_url   text,

  -- Contacto (whatsapp es obligatorio: es el canal del producto)
  whatsapp      text not null,                  -- E.164 sin '+': '5917xxxxxxx'
  telefono      text,
  email         text,

  -- Redes y web (todas opcionales — "si tiene")
  tiktok_url    text,
  facebook_url  text,
  instagram_url text,
  sitio_web     text,

  -- Ubicación
  zona_id       uuid references zonas(id) on delete set null,
  direccion     text,                           -- 'Galería Central, Local 14'
  lat           double precision,
  lng           double precision,
  como_llegar   text,                           -- link Google Maps opcional

  -- Estado de plataforma
  plan          text not null default 'gratis'  check (plan in ('gratis','pro','premium')),
  verificado    boolean not null default false,
  rating        numeric(2,1) not null default 0, -- 0.0 - 5.0
  destacado     boolean not null default false,

  -- Vínculo con WhatsApp (para asociar mensajes entrantes a su comercio)
  wa_jid        text unique,                    -- jid del remitente (ej '5917...@c.us')

  activo        boolean not null default true,  -- soft-delete
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index if not exists idx_comercios_zona      on comercios (zona_id) where activo;
create index if not exists idx_comercios_destacado on comercios (destacado) where activo;

-- ------------------------------------------------------------
-- PRODUCTOS del catálogo de un comercio
-- ------------------------------------------------------------
create table if not exists productos (
  id          uuid primary key default gen_random_uuid(),
  comercio_id uuid not null references comercios(id) on delete cascade,
  nombre      text not null,
  descripcion text,
  precio      numeric(12,2),
  moneda      text not null default 'BOB' check (moneda in ('BOB','USD','ARS')),
  foto_url    text,
  tiktok_url  text,                             -- video del producto (link, no hosting)
  destacado   boolean not null default false,
  activo      boolean not null default true,    -- soft-delete
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists idx_productos_comercio on productos (comercio_id) where activo;

-- ------------------------------------------------------------
-- PUBLICACIONES = el feed. Es lo que el vendedor manda por WhatsApp.
-- tipo: oferta | video | novedad
-- estado: pendiente -> aprobado | rechazado | cambios   (moderación)
-- Solo las 'aprobado' se muestran en el feed en vivo (Realtime).
-- ------------------------------------------------------------
create table if not exists publicaciones (
  id            uuid primary key default gen_random_uuid(),
  comercio_id   uuid references comercios(id) on delete cascade,
  tipo          text not null default 'oferta' check (tipo in ('oferta','video','novedad')),

  titulo        text,
  descripcion   text,
  precio        numeric(12,2),
  moneda        text not null default 'BOB' check (moneda in ('BOB','USD','ARS')),

  imagen_url    text,                           -- foto (Storage)
  tiktok_url    text,                           -- si es video: link TikTok publicado

  -- Moderación
  estado        text not null default 'pendiente'
                  check (estado in ('pendiente','aprobado','rechazado','cambios')),
  motivo_moderacion text,                       -- razón de rechazo / cambios pedidos
  moderado_por  text,
  moderado_at   timestamptz,

  -- Origen / trazabilidad
  origen        text not null default 'whatsapp' check (origen in ('whatsapp','panel')),
  wa_message_id text,                           -- idempotencia de ingesta
  raw           jsonb,                          -- payload crudo del bridge

  activo        boolean not null default true,  -- soft-delete
  created_at    timestamptz not null default now(),
  approved_at   timestamptz,
  unique (wa_message_id)
);
create index if not exists idx_pub_feed     on publicaciones (estado, approved_at desc) where activo;
create index if not exists idx_pub_comercio on publicaciones (comercio_id) where activo;
create index if not exists idx_pub_estado   on publicaciones (estado) where activo;

-- ------------------------------------------------------------
-- WA_INBOX: bitácora cruda de mensajes entrantes de WhatsApp.
-- Fuente de verdad inmutable; la moderación trabaja sobre publicaciones.
-- ------------------------------------------------------------
create table if not exists wa_inbox (
  id            uuid primary key default gen_random_uuid(),
  wa_message_id text not null unique,           -- idempotencia
  wa_jid        text not null,                  -- remitente
  phone         text,
  tipo          text,                           -- text/image/video/...
  body          text,
  media_url     text,
  raw           jsonb not null,
  procesado     boolean not null default false,
  created_at    timestamptz not null default now()
);
create index if not exists idx_wa_inbox_jid on wa_inbox (wa_jid);

-- ------------------------------------------------------------
-- updated_at automático
-- ------------------------------------------------------------
create or replace function set_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end$$;

drop trigger if exists trg_comercios_updated on comercios;
create trigger trg_comercios_updated before update on comercios
  for each row execute function set_updated_at();

drop trigger if exists trg_productos_updated on productos;
create trigger trg_productos_updated before update on productos
  for each row execute function set_updated_at();

-- ------------------------------------------------------------
-- VISTA del feed público (solo aprobado + activo, con datos del comercio)
-- ------------------------------------------------------------
create or replace view feed_publico as
  select
    p.id, p.tipo, p.titulo, p.descripcion, p.precio, p.moneda,
    p.imagen_url, p.tiktok_url, p.approved_at, p.created_at,
    c.id   as comercio_id,
    c.slug as comercio_slug,
    c.nombre as comercio_nombre,
    c.logo_url as comercio_logo,
    c.whatsapp as comercio_whatsapp,
    c.verificado as comercio_verificado,
    z.nombre as zona_nombre
  from publicaciones p
  join comercios c on c.id = p.comercio_id and c.activo
  left join zonas z on z.id = c.zona_id
  where p.estado = 'aprobado' and p.activo
  order by p.approved_at desc nulls last;
