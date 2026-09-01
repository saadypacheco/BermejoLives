-- El buscador necesita saber quién es destacado y quién paga.
--
-- Se unifican las dos pantallas: /mapa y /buscar pasan a ser una sola, y el
-- mapa de /buscar hereda el modo descubrimiento de /mapa — sin filtro puesto se
-- ven los adornos y NADA MÁS, salvo los comercios destacados o con plan.
--
-- Esa regla ya existía en HomeMap, donde el dato venía de `getComerciosMapa`.
-- `buscar_comercios` nunca devolvió `destacado` ni `plan`, así que en la
-- pantalla unificada la primera vista no habría podido mostrar a los que pagan
-- — que es justamente lo que se les cobra.
--
-- Se BORRA y se recrea: cambia el tipo de retorno.

drop function if exists buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text);

create or replace function buscar_comercios(
  q text default null, p_rubro text default null, p_modalidad text default null,
  p_zona text default null, p_precio_min numeric default null, p_precio_max numeric default null,
  p_ciudad text default null, p_limit int default 24, p_offset int default 0,
  p_subcategoria text default null
)
returns table (
  id uuid, slug text, nombre text, descripcion text, logo_url text, portada_url text,
  whatsapp text, direccion text, lat double precision, lng double precision, modalidad text,
  rubro_slug text, rubro_nombre text, subcategoria text, zona_nombre text, rating numeric, verificado boolean,
  ofertas bigint, rank real, monedas_aceptadas text[], envios_internacionales boolean,
  tiene_factura boolean, horario text, tiene_stock boolean, ciudad_nombre text, ciudad_pais text,
  prod_obs_human text, prod_det_ia text,
  destacado boolean, plan text,
  total bigint
)
language sql stable
as $$
  with entrada as (
    select
      lower(unaccent(coalesce(q, ''))) as texto,
      '\m' || regexp_replace(lower(unaccent(coalesce(q, ''))),
                             '([.^$*+?()\[\]{}|\\-])', '\\\1', 'g') as inicio_palabra,
      -- TODAS las palabras: es el match bueno, el que manda arriba en el orden.
      websearch_to_tsquery('spanish_unaccent', coalesce(q, '')) as tsq_todas,
      -- ALGUNA palabra: es el que decide quién entra. Sin esto, agregar una
      -- palabra de más vacía la pantalla.
      websearch_to_tsquery('spanish_unaccent',
        regexp_replace(btrim(coalesce(q, '')), '\s+', ' or ', 'g')) as tsq_alguna
  ),
  base as (
    select distinct on (c.id)
      c.id, c.slug, c.nombre, c.descripcion, c.logo_url, c.portada_url,
      c.whatsapp, c.direccion, c.lat, c.lng, c.modalidad,
      r.slug as rubro_slug, r.nombre as rubro_nombre, c.subcategoria, z.nombre as zona_nombre,
      c.rating, c.verificado,
      (select count(*) from publicaciones pp
         where pp.comercio_id = c.id and pp.estado = 'aprobado' and pp.activo) as ofertas,
      (case when q is null or q = '' then 1.0
            else
              -- Tener TODAS las palabras pesa mucho más que tener alguna: así
              -- "perfumeria belleza" trae también las perfumerías sueltas, pero
              -- la que es las dos cosas encabeza la lista.
              least(ts_rank(c.busqueda, e.tsq_todas) * 4, 1.0)
              + least(ts_rank(c.busqueda, e.tsq_alguna) * 1.5, 0.4)
              + case when lower(unaccent(c.nombre)) ~ e.inicio_palabra then 0.5 else 0 end
              + case when exists (
                  select 1 from comercio_rubros cr3 join rubros r4 on r4.id = cr3.rubro_id
                  where cr3.comercio_id = c.id and lower(unaccent(r4.nombre)) ~ e.inicio_palabra
                ) then 0.15 else 0 end
              + similarity(lower(unaccent(c.nombre)), e.texto) * 0.3
              + similarity(lower(unaccent(coalesce(c.subcategoria, ''))), e.texto) * 0.25
            end)::real as rank,
      coalesce(c.monedas_aceptadas, '{}') as monedas_aceptadas,
      coalesce(c.envios_internacionales, false) as envios_internacionales,
      coalesce(c.tiene_factura, false) as tiene_factura,
      c.horario, coalesce(c.tiene_stock, true) as tiene_stock,
      ci.nombre as ciudad_nombre, ci.pais as ciudad_pais,
      c.prod_obs_human, c.prod_det_ia,
      coalesce(c.destacado, false) as destacado, coalesce(c.plan, 'gratis') as plan
    from comercios c
    cross join entrada e
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
      -- El refinamiento por subcategoría: se compara sin tildes y en
      -- minúsculas porque el chip lleva el texto tal como lo escribió la IA.
      -- Se compara por la RAÍZ de las palabras, no por el texto: el chip dice
      -- "zapatilla" y hay comercios cargados como "zapatillas". Comparando
      -- texto contra texto, el chip mostraba 35 y al tocarlo aparecían 23.
      -- `strip` saca las posiciones, así "calzado femenino" y "femenino
      -- calzado" también caen en la misma bolsa.
      and (p_subcategoria is null
           or strip(to_tsvector('spanish_unaccent', coalesce(c.subcategoria, '')))
              = strip(to_tsvector('spanish_unaccent', p_subcategoria)))
      and (p_zona is null or z.slug = p_zona)
      and (p_ciudad is null or ci.slug = p_ciudad)
      and (p_precio_min is null or p.precio is null or p.precio >= p_precio_min)
      and (p_precio_max is null or p.precio is null or p.precio <= p_precio_max)
      and (
        q is null or q = ''
        or c.busqueda @@ e.tsq_alguna
        or p.busqueda @@ e.tsq_alguna
        or lower(unaccent(c.nombre)) ~ e.inicio_palabra
        or exists (
          select 1 from comercio_rubros cr2 join rubros r3 on r3.id = cr2.rubro_id
          where cr2.comercio_id = c.id and lower(unaccent(r3.nombre)) ~ e.inicio_palabra)
        or similarity(lower(unaccent(c.nombre)), e.texto) > 0.35
        or similarity(lower(unaccent(coalesce(c.subcategoria, ''))), e.texto) > 0.35
      )
    order by c.id
  )
  select id, slug, nombre, descripcion, logo_url, portada_url, whatsapp, direccion,
         lat, lng, modalidad, rubro_slug, rubro_nombre, subcategoria, zona_nombre, rating, verificado,
         ofertas, rank, monedas_aceptadas, envios_internacionales, tiene_factura,
         horario, tiene_stock, ciudad_nombre, ciudad_pais,
         prod_obs_human, prod_det_ia,
         destacado, plan,
         -- Cuántos hay EN TOTAL, no cuántos entran en esta página. Se calcula
         -- sobre `base`, que ya tiene aplicados todos los filtros y todavía no
         -- el limit, así que es el número real de coincidencias.
         count(*) over () as total
    from base order by rank desc, nombre
   -- p_limit <= 0 significa SIN TOPE. Lo usa `refinamientos_busqueda`, que
   -- necesita contar sobre todas las coincidencias y no sobre una porción.
   -- Un tope alto habría sido lo mismo de siempre: mover el techo y esperar a
   -- que alguien lo vuelva a chocar sin enterarse.
   limit case when p_limit <= 0 then null else greatest(1, least(p_limit, 500)) end
  offset greatest(0, p_offset);
$$;

grant execute on function buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text)
  to anon, authenticated, service_role;
