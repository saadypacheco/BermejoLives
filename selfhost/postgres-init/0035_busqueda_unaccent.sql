-- 0035: búsqueda inteligente — acento-insensible + por nombre de categoría + substring.
--   Bug: "vidrieria" (sin tilde) no encontraba "Vidriería" porque to_tsvector('spanish')
--   distingue acentos. Fix: config de texto con unaccent (ignora acentos).
--   Además: el texto libre ahora matchea por NOMBRE DE RUBRO (todas las categorías del
--   comercio) y por substring del nombre (encuentra "vidri" → Vidriería).

create extension if not exists unaccent;

-- Config de texto que ignora acentos (es inmutable → usable en columnas generadas).
do $$ begin
  if not exists (select 1 from pg_ts_config where cfgname = 'spanish_unaccent') then
    create text search configuration spanish_unaccent (copy = spanish);
    alter text search configuration spanish_unaccent
      alter mapping for hword, hword_part, word with unaccent, spanish_stem;
  end if;
end $$;

-- Recrear los vectores de búsqueda con la config acento-insensible.
-- (Se dropean las funciones que los referencian, se recrean las columnas, se recrea la RPC.)
drop function if exists buscar_comercios(text, text, text, text, numeric, numeric);
drop function if exists buscar_comercios(text, text, text, text, numeric, numeric, text, int, int);

alter table comercios drop column if exists busqueda;
alter table comercios add column busqueda tsvector generated always as (
  to_tsvector('spanish_unaccent',
    coalesce(nombre, '') || ' ' || coalesce(descripcion, '') || ' ' || coalesce(direccion, ''))
) stored;
create index if not exists idx_comercios_busqueda on comercios using gin (busqueda);

alter table publicaciones drop column if exists busqueda;
alter table publicaciones add column busqueda tsvector generated always as (
  to_tsvector('spanish_unaccent', coalesce(titulo, '') || ' ' || coalesce(descripcion, ''))
) stored;
create index if not exists idx_pub_busqueda on publicaciones using gin (busqueda);

create or replace function buscar_comercios(
  q text default null, p_rubro text default null, p_modalidad text default null,
  p_zona text default null, p_precio_min numeric default null, p_precio_max numeric default null,
  p_ciudad text default null, p_limit int default 24, p_offset int default 0
)
returns table (
  id uuid, slug text, nombre text, descripcion text, logo_url text, portada_url text,
  whatsapp text, direccion text, lat double precision, lng double precision, modalidad text,
  rubro_slug text, rubro_nombre text, zona_nombre text, rating numeric, verificado boolean,
  ofertas bigint, rank real, monedas_aceptadas text[], envios_internacionales boolean,
  tiene_factura boolean, horario text, tiene_stock boolean, ciudad_nombre text, ciudad_pais text
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
            else greatest(
              ts_rank(c.busqueda, websearch_to_tsquery('spanish_unaccent', q)),
              case when unaccent(lower(c.nombre)) like '%' || unaccent(lower(q)) || '%' then 0.4 else 0 end
            ) end)::real as rank,
      coalesce(c.monedas_aceptadas, '{}') as monedas_aceptadas,
      coalesce(c.envios_internacionales, false) as envios_internacionales,
      coalesce(c.tiene_factura, false) as tiene_factura,
      c.horario, coalesce(c.tiene_stock, true) as tiene_stock,
      ci.nombre as ciudad_nombre, ci.pais as ciudad_pais
    from comercios c
    left join rubros r on r.id = c.rubro_id
    left join zonas z on z.id = c.zona_id
    left join ciudades ci on ci.id = c.ciudad_id
    left join publicaciones p on p.comercio_id = c.id and p.estado = 'aprobado' and p.activo
    where c.activo
      and not coalesce(c.suspendido, false)
      and (p_rubro is null or exists (
        select 1 from comercio_rubros cr join rubros r2 on r2.id = cr.rubro_id
        where cr.comercio_id = c.id and r2.slug = p_rubro))
      and (p_modalidad is null or c.modalidad = p_modalidad)
      and (p_zona is null or z.slug = p_zona)
      and (p_ciudad is null or ci.slug = p_ciudad)
      and (p_precio_min is null or p.precio >= p_precio_min)
      and (p_precio_max is null or p.precio <= p_precio_max)
      and (
        q is null or q = ''
        or c.busqueda @@ websearch_to_tsquery('spanish_unaccent', q)
        or p.busqueda @@ websearch_to_tsquery('spanish_unaccent', q)
        or unaccent(lower(c.nombre)) like '%' || unaccent(lower(q)) || '%'
        or exists (                                    -- matchea por NOMBRE DE CATEGORÍA (todas)
          select 1 from comercio_rubros cr2 join rubros r3 on r3.id = cr2.rubro_id
          where cr2.comercio_id = c.id
            and unaccent(lower(r3.nombre)) like '%' || unaccent(lower(q)) || '%')
      )
    order by c.id
  )
  select * from base order by rank desc, nombre
  limit greatest(1, least(p_limit, 60)) offset greatest(0, p_offset);
$$;
grant execute on function buscar_comercios(text, text, text, text, numeric, numeric, text, int, int) to anon, authenticated;
