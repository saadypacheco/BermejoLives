-- "ropa y moda" traía muebles, tecnología y alojamientos.
--
-- QUÉ PASABA
-- ==========
-- El buscador tiene dos consultas. `tsq_todas` pide TODAS las palabras y es la
-- buena; `tsq_alguna` pide CUALQUIERA y es la que decide quién entra. Lo
-- segundo está puesto a propósito y por una buena razón: sin eso, agregar una
-- palabra de más vacía la pantalla.
--
-- El problema es que no había ningún piso. Escribiendo "moda y ropa" —el nombre
-- exacto del rubro— funcionaba de casualidad: hay una vía que compara la frase
-- ENTERA contra el nombre del rubro (`lower(unaccent(r.nombre)) ~ '\mmoda y
-- ropa'`), los 282 comercios de Moda y ropa entraban con rank alto y la basura
-- quedaba sepultada abajo.
--
-- Al escribirlo al revés esa vía se cae —"ropa y moda" no es prefijo de "Moda y
-- ropa"— y lo único que queda es el OR: "ropa" pega en un hotel cuya foto
-- describe "ropa de cama", "moda" pega en cualquier descripción suelta. La
-- pantalla se llena de cosas que no son, y nada avisa.
--
-- DOS ARREGLOS
-- ============
-- 1) El nombre del rubro se compara POR PALABRAS y no como prefijo de la frase.
--    `to_tsvector('Moda y ropa') @@ (ropa & moda)` es verdadero escriba como
--    escriba, y "y" es palabra vacía en castellano así que ni cuenta. El orden
--    en que alguien teclea dos palabras no es información.
--
-- 2) El OR pasa a ser RED DE CONTENCIÓN y no la puerta principal. Si hay al
--    menos 5 resultados que tienen todas las palabras, sólo se muestran ésos.
--    Si hay menos —una búsqueda rara, un error de tipeo— se agregan los flojos,
--    que es exactamente el caso para el que se puso el OR.
--
--    El corte se mide sobre los resultados YA filtrados por ciudad, rubro y
--    todo lo demás, así que no hay forma de que la red de contención tape una
--    búsqueda que sí tenía respuesta.
--
-- Lo que NO se toca: con una sola palabra las dos consultas son la misma, así
-- que "comida" sigue trayendo lo mismo que hoy.

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
  destacado boolean, plan text, portada_thumb_url text,
  total bigint
)
language sql stable
as $$
  with entrada as (
    select
      lower(unaccent(coalesce(q, ''))) as texto,
      '\m' || regexp_replace(lower(unaccent(coalesce(q, ''))),
                             '([.^$*+?()\[\]{}|\\-])', '\\\1', 'g') as inicio_palabra,
      websearch_to_tsquery('spanish_unaccent', coalesce(q, '')) as tsq_todas,
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
      -- ¿Este resultado tiene TODAS las palabras, de alguna forma? De esto
      -- depende si es un resultado de verdad o relleno del OR.
      -- `coalesce` porque `p` viene de un LEFT JOIN: sin publicación,
      -- `p.busqueda @@ ...` es NULL, y `false or NULL` es NULL. Un NULL acá
      -- descartaría la fila más abajo sin que nada lo diga.
      coalesce(
      q is null or q = ''
       or c.busqueda @@ e.tsq_todas
       or p.busqueda @@ e.tsq_todas
       or lower(unaccent(c.nombre)) ~ e.inicio_palabra
       or exists (
            select 1 from comercio_rubros cr4 join rubros r5 on r5.id = cr4.rubro_id
             where cr4.comercio_id = c.id
               and (to_tsvector('spanish_unaccent', r5.nombre) @@ e.tsq_todas
                    or lower(unaccent(r5.nombre)) ~ e.inicio_palabra))
       or similarity(lower(unaccent(c.nombre)), e.texto) > 0.35
       or similarity(lower(unaccent(coalesce(c.subcategoria, ''))), e.texto) > 0.35
      , false) as fuerte,
      (case when q is null or q = '' then 1.0
            else
              least(ts_rank(c.busqueda, e.tsq_todas) * 4, 1.0)
              + least(ts_rank(c.busqueda, e.tsq_alguna) * 1.5, 0.4)
              + case when lower(unaccent(c.nombre)) ~ e.inicio_palabra then 0.5 else 0 end
              -- El rubro que se llama como lo que se buscó pesa fuerte: si
              -- alguien escribe el nombre de un rubro, quiere ese rubro.
              + case when exists (
                  select 1 from comercio_rubros cr3 join rubros r4 on r4.id = cr3.rubro_id
                  where cr3.comercio_id = c.id
                    and (to_tsvector('spanish_unaccent', r4.nombre) @@ e.tsq_todas
                         or lower(unaccent(r4.nombre)) ~ e.inicio_palabra)
                ) then 0.35 else 0 end
              + similarity(lower(unaccent(c.nombre)), e.texto) * 0.3
              + similarity(lower(unaccent(coalesce(c.subcategoria, ''))), e.texto) * 0.25
            end)::real as rank,
      coalesce(c.monedas_aceptadas, '{}') as monedas_aceptadas,
      coalesce(c.envios_internacionales, false) as envios_internacionales,
      coalesce(c.tiene_factura, false) as tiene_factura,
      c.horario, coalesce(c.tiene_stock, true) as tiene_stock,
      ci.nombre as ciudad_nombre, ci.pais as ciudad_pais,
      c.prod_obs_human, c.prod_det_ia,
      coalesce(c.destacado, false) as destacado, coalesce(c.plan, 'gratis') as plan,
      c.portada_thumb_url
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
          where cr2.comercio_id = c.id
            and (to_tsvector('spanish_unaccent', r3.nombre) @@ e.tsq_todas
                 or lower(unaccent(r3.nombre)) ~ e.inicio_palabra))
        or similarity(lower(unaccent(c.nombre)), e.texto) > 0.35
        or similarity(lower(unaccent(coalesce(c.subcategoria, ''))), e.texto) > 0.35
      )
    -- `distinct on` se queda con la PRIMERA fila de cada comercio, y un comercio
    -- con varias publicaciones aparece varias veces. Sin el `fuerte desc`, la
    -- que sobrevive es cualquiera: un comercio cuya oferta sí tenía todas las
    -- palabras podía quedar marcado como flojo por la fila de otra oferta.
    order by c.id, fuerte desc, rank desc
  ),
  -- Cuántos de los que pasaron tienen TODAS las palabras. Se cuenta acá, sobre
  -- los resultados ya filtrados por ciudad y rubro, para que el corte no pueda
  -- tapar una búsqueda que sí tenía respuesta.
  medidos as (
    select b.*, sum(case when b.fuerte then 1 else 0 end) over () as n_fuertes from base b
  ),
  filtrados as (
    -- Con 5 buenos alcanza para llenar pantalla: los flojos sobran y sólo
    -- ensucian. Con menos, entran — es el caso para el que existe el OR.
    select * from medidos where coalesce(n_fuertes, 0) < 5 or fuerte
  )
  select id, slug, nombre, descripcion, logo_url, portada_url, whatsapp, direccion,
         lat, lng, modalidad, rubro_slug, rubro_nombre, subcategoria, zona_nombre, rating, verificado,
         ofertas, rank, monedas_aceptadas, envios_internacionales, tiene_factura,
         horario, tiene_stock, ciudad_nombre, ciudad_pais,
         prod_obs_human, prod_det_ia,
         destacado, plan, portada_thumb_url,
         count(*) over () as total
    from filtrados order by rank desc, nombre
   limit case when p_limit <= 0 then null else greatest(1, least(p_limit, 500)) end
  offset greatest(0, p_offset);
$$;

grant execute on function buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text)
  to anon, authenticated, service_role;
