-- ============================================================
-- Bermejo Live Market · 0008_ciudades
-- Dimensión geográfica: ciudades/departamentos de Bolivia.
-- Bermejo arranca "encendida" (activa); el resto queda "próximamente".
-- Visión: fronteras → ciudades importantes → mayoristas top de Bolivia.
-- ============================================================

create table if not exists ciudades (
  id           uuid primary key default gen_random_uuid(),
  slug         text not null unique,
  nombre       text not null,
  departamento text not null,
  lat          double precision,
  lng          double precision,
  es_frontera  boolean not null default false,
  activa       boolean not null default false,   -- "encendida" en el mapa
  orden        int     not null default 0,
  created_at   timestamptz not null default now()
);

alter table comercios add column if not exists ciudad_id uuid references ciudades(id) on delete set null;
create index if not exists idx_comercios_ciudad on comercios (ciudad_id) where activo;

-- GRANTs + RLS (lectura pública)
grant select on ciudades to anon, authenticated;
grant all on ciudades to service_role;
alter table ciudades enable row level security;
drop policy if exists ciudades_public_read on ciudades;
create policy ciudades_public_read on ciudades
  for select to anon, authenticated using (true);

-- Seed: fronteras + ciudades importantes de Bolivia. Solo Bermejo activa.
insert into ciudades (slug, nombre, departamento, lat, lng, es_frontera, activa, orden) values
  -- Frontera (la apuesta del producto)
  ('bermejo',          'Bermejo',          'Tarija',      -22.7361, -64.3433, true,  true,  1),
  ('yacuiba',          'Yacuiba',          'Tarija',      -22.0146, -63.6775, true,  false, 2),
  ('villazon',         'Villazón',         'Potosí',      -22.0866, -65.5942, true,  false, 3),
  ('desaguadero',      'Desaguadero',      'La Paz',      -16.5667, -69.0417, true,  false, 4),
  ('puerto-quijarro',  'Puerto Quijarro',  'Santa Cruz',  -17.7833, -57.7667, true,  false, 5),
  ('cobija',           'Cobija',           'Pando',       -11.0267, -68.7692, true,  false, 6),
  -- Ciudades importantes
  ('santa-cruz',       'Santa Cruz',       'Santa Cruz',  -17.7833, -63.1821, false, false, 10),
  ('la-paz',           'La Paz',           'La Paz',      -16.5000, -68.1500, false, false, 11),
  ('cochabamba',       'Cochabamba',       'Cochabamba',  -17.3895, -66.1568, false, false, 12),
  ('tarija',           'Tarija',           'Tarija',      -21.5355, -64.7296, false, false, 13),
  ('sucre',            'Sucre',            'Chuquisaca',  -19.0333, -65.2627, false, false, 14),
  ('oruro',            'Oruro',            'Oruro',       -17.9833, -67.1500, false, false, 15),
  ('potosi',           'Potosí',           'Potosí',      -19.5836, -65.7531, false, false, 16),
  ('trinidad',         'Trinidad',         'Beni',        -14.8333, -64.9000, false, false, 17)
on conflict (slug) do nothing;

-- Los comercios actuales son todos de Bermejo
update comercios set ciudad_id = (select id from ciudades where slug = 'bermejo')
where ciudad_id is null;

-- buscar_comercios: sumar filtro por ciudad (re-crear con el nuevo parámetro)
drop function if exists buscar_comercios(text, text, text, text, numeric, numeric);
create or replace function buscar_comercios(
  q            text    default null,
  p_rubro      text    default null,
  p_modalidad  text    default null,
  p_zona       text    default null,
  p_precio_min numeric default null,
  p_precio_max numeric default null,
  p_ciudad     text    default null
)
returns table (
  id uuid, slug text, nombre text, descripcion text, logo_url text, portada_url text,
  whatsapp text, direccion text, lat double precision, lng double precision,
  modalidad text, rubro_slug text, rubro_nombre text, zona_nombre text,
  rating numeric, verificado boolean, ofertas bigint, rank real
)
language sql stable
as $$
  with base as (
    select distinct on (c.id)
      c.id, c.slug, c.nombre, c.descripcion, c.logo_url, c.portada_url,
      c.whatsapp, c.direccion, c.lat, c.lng, c.modalidad,
      r.slug as rubro_slug, r.nombre as rubro_nombre, z.nombre as zona_nombre,
      c.rating, c.verificado,
      (select count(*) from publicaciones pp
         where pp.comercio_id = c.id and pp.estado = 'aprobado' and pp.activo) as ofertas,
      (case when q is null or q = '' then 1.0
            else ts_rank(c.busqueda, websearch_to_tsquery('spanish', q)) end)::real as rank
    from comercios c
    left join rubros r on r.id = c.rubro_id
    left join zonas  z on z.id = c.zona_id
    left join ciudades ci on ci.id = c.ciudad_id
    left join publicaciones p
      on p.comercio_id = c.id and p.estado = 'aprobado' and p.activo
    where c.activo
      and (p_rubro     is null or r.slug = p_rubro)
      and (p_modalidad is null or c.modalidad = p_modalidad)
      and (p_zona      is null or z.slug = p_zona)
      and (p_ciudad    is null or ci.slug = p_ciudad)
      and (p_precio_min is null or p.precio >= p_precio_min)
      and (p_precio_max is null or p.precio <= p_precio_max)
      and (
        q is null or q = ''
        or c.busqueda @@ websearch_to_tsquery('spanish', q)
        or p.busqueda @@ websearch_to_tsquery('spanish', q)
      )
    order by c.id
  )
  select * from base order by rank desc, nombre;
$$;

grant execute on function buscar_comercios(text, text, text, text, numeric, numeric, text) to anon, authenticated;
