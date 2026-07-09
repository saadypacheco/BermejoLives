-- ============================================================
-- Bermejo Live Market · 0005_rubros_modalidad
-- Dos ejes nuevos para el comercio:
--   modalidad: mayorista | minorista | ambos   (la mayoría en Bermejo es mayorista)
--   rubro:     qué hace el negocio (importadora, restaurante, gomería, servicios…)
--              distinto de la ZONA (dónde está).
-- ============================================================

-- Modalidad de venta
alter table comercios add column if not exists modalidad text not null default 'mayorista'
  check (modalidad in ('mayorista', 'minorista', 'ambos'));

-- Rubros (categoría de negocio, extensible)
create table if not exists rubros (
  id         uuid primary key default gen_random_uuid(),
  slug       text not null unique,
  nombre     text not null,
  icono      text,
  orden      int  not null default 0,
  activo     boolean not null default true,
  created_at timestamptz not null default now()
);

alter table comercios add column if not exists rubro_id uuid references rubros(id) on delete set null;
create index if not exists idx_comercios_rubro     on comercios (rubro_id)   where activo;
create index if not exists idx_comercios_modalidad on comercios (modalidad)  where activo;

-- GRANTs + RLS (lectura pública, escritura solo backend)
grant select on rubros to anon, authenticated;
grant all on rubros to service_role;
alter table rubros enable row level security;
drop policy if exists rubros_public_read on rubros;
create policy rubros_public_read on rubros
  for select to anon, authenticated using (activo);

-- Seed de rubros (incluye restaurantes, servicios, gomería, etc.)
insert into rubros (slug, nombre, icono, orden) values
  ('importadora', 'Importadora',            'box',      1),
  ('moda',        'Moda y calzado',         'shirt',    2),
  ('tecnologia',  'Tecnología',             'cpu',      3),
  ('gastronomia', 'Restaurante / Comida',   'utensils', 4),
  ('servicios',   'Servicios',              'wrench',   5),
  ('gomeria',     'Gomería / Repuestos',    'car',      6),
  ('farmacia',    'Farmacia / Salud',       'plus',     7),
  ('hogar',       'Hogar y electrodom.',    'home',     8),
  ('belleza',     'Belleza y estética',     'sparkles', 9),
  ('mercado',     'Mercado / Abarrotes',    'basket',  10),
  ('otros',       'Otros',                  'dots',    11)
on conflict (slug) do nothing;

-- Marcar los comercios demo con modalidad + rubro
update comercios set modalidad = 'mayorista', rubro_id = (select id from rubros where slug = 'importadora') where slug = 'importadora-abc';
update comercios set modalidad = 'ambos',     rubro_id = (select id from rubros where slug = 'moda')        where slug = 'moda-bermejo';
update comercios set modalidad = 'minorista', rubro_id = (select id from rubros where slug = 'tecnologia')  where slug = 'tecno-store';
update comercios set modalidad = 'minorista', rubro_id = (select id from rubros where slug = 'belleza')     where slug = 'perfumeria-vip';
update comercios set modalidad = 'ambos',     rubro_id = (select id from rubros where slug = 'moda')        where slug = 'calzados-top';

-- Ampliar el feed público con modalidad + rubro (columnas nuevas al final)
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
    z.nombre as zona_nombre,
    c.modalidad as comercio_modalidad,
    r.nombre as rubro_nombre,
    r.slug as rubro_slug
  from publicaciones p
  join comercios c on c.id = p.comercio_id and c.activo
  left join zonas z on z.id = c.zona_id
  left join rubros r on r.id = c.rubro_id
  where p.estado = 'aprobado' and p.activo
  order by p.approved_at desc nulls last;
