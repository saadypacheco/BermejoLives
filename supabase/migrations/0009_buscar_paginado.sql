-- ============================================================
-- Bermejo Live Market · 0009_buscar_paginado
-- Paginación en el buscador (limit/offset). Re-crea buscar_comercios.
-- ============================================================
drop function if exists buscar_comercios(text, text, text, text, numeric, numeric, text);
create or replace function buscar_comercios(
  q            text    default null,
  p_rubro      text    default null,
  p_modalidad  text    default null,
  p_zona       text    default null,
  p_precio_min numeric default null,
  p_precio_max numeric default null,
  p_ciudad     text    default null,
  p_limit      int     default 24,
  p_offset     int     default 0
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
  select * from base order by rank desc, nombre
  limit greatest(1, least(p_limit, 60)) offset greatest(0, p_offset);
$$;

grant execute on function buscar_comercios(text, text, text, text, numeric, numeric, text, int, int) to anon, authenticated;
