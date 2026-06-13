-- ============================================================
-- Bermejo Live Market · 0006_busqueda (Fase 1 del buscador)
-- Full-text en español sobre comercios + publicaciones, y una función RPC
-- buscar_comercios(...) que el frontend llama directo (anon + RLS).
-- La relevancia sale TAMBIÉN de lo que el comercio publica, así el que
-- "vende de todo" aparece por su contenido real, no solo por su rubro.
-- ============================================================

-- Columnas tsvector generadas + índices GIN
alter table comercios add column if not exists busqueda tsvector
  generated always as (
    to_tsvector('spanish',
      coalesce(nombre, '') || ' ' || coalesce(descripcion, '') || ' ' || coalesce(direccion, ''))
  ) stored;
create index if not exists idx_comercios_busqueda on comercios using gin (busqueda);

alter table publicaciones add column if not exists busqueda tsvector
  generated always as (
    to_tsvector('spanish', coalesce(titulo, '') || ' ' || coalesce(descripcion, ''))
  ) stored;
create index if not exists idx_pub_busqueda on publicaciones using gin (busqueda);

-- Función de búsqueda. SECURITY INVOKER (default) => respeta RLS:
-- anon solo ve comercios activos y publicaciones aprobadas.
create or replace function buscar_comercios(
  q            text    default null,
  p_rubro      text    default null,
  p_modalidad  text    default null,
  p_zona       text    default null,
  p_precio_min numeric default null,
  p_precio_max numeric default null
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
    left join publicaciones p
      on p.comercio_id = c.id and p.estado = 'aprobado' and p.activo
    where c.activo
      and (p_rubro     is null or r.slug = p_rubro)
      and (p_modalidad is null or c.modalidad = p_modalidad)
      and (p_zona      is null or z.slug = p_zona)
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

grant execute on function buscar_comercios(text, text, text, text, numeric, numeric) to anon, authenticated;
