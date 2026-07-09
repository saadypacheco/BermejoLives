-- ============================================================
-- Bermejo Live Market · 0011_plataforma_frontera
-- Expansión estratégica: plataforma de inteligencia comercial
-- de frontera Bolivia-Argentina.
-- Agrega: rubros nuevos, campos fronterizos en comercios,
-- ciudades argentinas, columna pais en ciudades, tabla leads.
-- ============================================================

-- 1. Nuevos rubros para el mercado fronterizo
insert into rubros (slug, nombre, icono, orden) values
  ('casa-de-cambio', 'Casa de cambio',       'banknotes', 12),
  ('transporte',     'Transporte / Logística','truck',     13),
  ('hotel',          'Hotel / Hospedaje',     'building',  14)
on conflict (slug) do nothing;

-- 2. Nuevos campos en comercios para el diferencial fronterizo
alter table comercios add column if not exists monedas_aceptadas    text[]  default '{}';
alter table comercios add column if not exists envios_internacionales boolean default false;
alter table comercios add column if not exists origen_importacion   text[]  default '{}';
alter table comercios add column if not exists pedido_minimo        text;
alter table comercios add column if not exists tiene_factura        boolean default false;
alter table comercios add column if not exists horario              text;
alter table comercios add column if not exists tiene_stock          boolean default true;

-- 3. Columna pais en ciudades (Bolivia por defecto para las existentes)
alter table ciudades add column if not exists pais text not null default 'Bolivia';

-- 4. Ciudades argentinas: frontera y destinos clave
insert into ciudades (slug, nombre, departamento, lat, lng, es_frontera, activa, orden, pais) values
  ('la-quiaca',    'La Quiaca',    'Jujuy',         -22.1027, -65.5983, true,  false, 20, 'Argentina'),
  ('oran',         'Orán',         'Salta',         -23.1333, -64.3167, false, false, 21, 'Argentina'),
  ('jujuy',        'Jujuy',        'Jujuy',         -24.1858, -65.2995, false, false, 22, 'Argentina'),
  ('salta',        'Salta',        'Salta',         -24.7821, -65.4232, false, false, 23, 'Argentina'),
  ('perico',       'Perico',       'Jujuy',         -24.3833, -65.1167, false, false, 24, 'Argentina'),
  ('tucuman',      'Tucumán',      'Tucumán',       -26.8083, -65.2176, false, false, 25, 'Argentina'),
  ('cordoba',      'Córdoba',      'Córdoba',       -31.4135, -64.1811, false, false, 26, 'Argentina'),
  ('buenos-aires', 'Buenos Aires', 'Buenos Aires',  -34.6037, -58.3816, false, false, 27, 'Argentina')
on conflict (slug) do nothing;

-- 5. Tabla de leads: registra cada vez que alguien contacta un comercio
create table if not exists leads (
  id          uuid        primary key default gen_random_uuid(),
  comercio_id uuid        not null references comercios(id) on delete cascade,
  tipo        text        not null default 'whatsapp',  -- 'whatsapp' | 'telefono' | 'email' | 'web'
  created_at  timestamptz not null default now()
);

create index if not exists idx_leads_comercio on leads (comercio_id);
create index if not exists idx_leads_created  on leads (created_at);

-- RLS: cualquiera puede insertar un lead; solo service_role puede leer
grant select, insert on leads to anon, authenticated;
grant all             on leads to service_role;
alter table leads enable row level security;

drop policy if exists leads_insert_public on leads;
create policy leads_insert_public on leads
  for insert to anon, authenticated with check (true);

drop policy if exists leads_select_service on leads;
create policy leads_select_service on leads
  for select to service_role using (true);

-- 6. Actualizar buscar_comercios: incluir nuevos campos en el resultado
drop function if exists buscar_comercios(text, text, text, text, numeric, numeric, text, int, int);
create or replace function buscar_comercios(
  q                     text    default null,
  p_rubro               text    default null,
  p_modalidad           text    default null,
  p_zona                text    default null,
  p_precio_min          numeric default null,
  p_precio_max          numeric default null,
  p_ciudad              text    default null,
  p_limit               int     default 24,
  p_offset              int     default 0
)
returns table (
  id                    uuid,
  slug                  text,
  nombre                text,
  descripcion           text,
  logo_url              text,
  portada_url           text,
  whatsapp              text,
  direccion             text,
  lat                   double precision,
  lng                   double precision,
  modalidad             text,
  rubro_slug            text,
  rubro_nombre          text,
  zona_nombre           text,
  rating                numeric,
  verificado            boolean,
  ofertas               bigint,
  rank                  real,
  monedas_aceptadas     text[],
  envios_internacionales boolean,
  tiene_factura         boolean,
  horario               text,
  tiene_stock           boolean,
  ciudad_nombre         text,
  ciudad_pais           text
)
language sql stable
as $$
  with base as (
    select distinct on (c.id)
      c.id, c.slug, c.nombre, c.descripcion, c.logo_url, c.portada_url,
      c.whatsapp, c.direccion, c.lat, c.lng, c.modalidad,
      r.slug   as rubro_slug,   r.nombre as rubro_nombre,
      z.nombre as zona_nombre,
      c.rating, c.verificado,
      (select count(*) from publicaciones pp
         where pp.comercio_id = c.id and pp.estado = 'aprobado' and pp.activo) as ofertas,
      (case when q is null or q = '' then 1.0
            else ts_rank(c.busqueda, websearch_to_tsquery('spanish', q)) end)::real as rank,
      coalesce(c.monedas_aceptadas,     '{}') as monedas_aceptadas,
      coalesce(c.envios_internacionales, false) as envios_internacionales,
      coalesce(c.tiene_factura,          false) as tiene_factura,
      c.horario,
      coalesce(c.tiene_stock, true) as tiene_stock,
      ci.nombre as ciudad_nombre,
      ci.pais   as ciudad_pais
    from comercios c
    left join rubros   r  on r.id  = c.rubro_id
    left join zonas    z  on z.id  = c.zona_id
    left join ciudades ci on ci.id = c.ciudad_id
    left join publicaciones p
      on p.comercio_id = c.id and p.estado = 'aprobado' and p.activo
    where c.activo
      and (p_rubro is null or exists (
        select 1 from comercio_rubros cr join rubros r2 on r2.id = cr.rubro_id
        where cr.comercio_id = c.id and r2.slug = p_rubro))
      and (p_modalidad  is null or c.modalidad  = p_modalidad)
      and (p_zona       is null or z.slug       = p_zona)
      and (p_ciudad     is null or ci.slug      = p_ciudad)
      and (p_precio_min is null or p.precio    >= p_precio_min)
      and (p_precio_max is null or p.precio    <= p_precio_max)
      and (
        q is null or q = ''
        or c.busqueda @@ websearch_to_tsquery('spanish', q)
        or p.busqueda @@ websearch_to_tsquery('spanish', q)
      )
    order by c.id
  )
  select * from base order by rank desc, nombre
  limit greatest(1, least(p_limit, 60)) offset greatest(0, p_offset);
$$;

grant execute on function buscar_comercios(text, text, text, text, numeric, numeric, text, int, int)
  to anon, authenticated;
