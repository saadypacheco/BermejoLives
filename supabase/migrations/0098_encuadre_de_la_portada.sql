-- Dónde se recorta la portada, decidido por una persona.
--
-- Las tarjetas muestran la portada en una franja apaisada (150px de alto) y la
-- foto original casi siempre es vertical: la sacó alguien parado en la vereda,
-- con el celular. `object-fit: cover` recorta por el centro, y el centro de una
-- foto de vidriera suele ser la mitad inferior del toldo y la mitad superior de
-- la puerta — o sea, nada.
--
-- No hay forma de acertarle automáticamente. Un modelo puede proponer el
-- recorte y a veces acierta, pero acá el que sacó la foto está mirando la
-- pantalla y sabe qué parte importa: el cartel, la vidriera, la mercadería.
-- Mover una barra es más rápido y más barato que cualquier análisis.
--
-- `portada_pos` es el porcentaje vertical que va al centro del recorte, igual
-- que `object-position: center <n>%`:
--
--     0   arriba de todo   (el cartel)
--     50  el centro        (lo que hace hoy)
--     100 abajo de todo    (la mercadería en la vereda)
--
-- Vertical y no las dos coordenadas: en una foto vertical recortada a apaisada,
-- lo horizontal no se mueve — sobra alto, no ancho. Un control con dos ejes
-- pide dos decisiones donde hay una.

alter table comercios add column if not exists portada_pos smallint;

-- NULL, no 50: "nadie lo tocó" y "una persona eligió el centro" son cosas
-- distintas. La primera se puede revisar en tanda; la segunda ya está resuelta.
comment on column comercios.portada_pos is
  'Porcentaje vertical del recorte de la portada (0 arriba, 100 abajo). NULL = nunca se ajustó.';

-- `buscar_comercios` tiene que devolver `portada_pos`, o el encuadre elegido no
-- llega a la tarjeta de resultados —que es justo donde el recorte molesta—.
--
-- Va con DROP y no con CREATE OR REPLACE: agregar una columna a la salida
-- cambia la firma, y `create or replace` no puede con eso. El cuerpo es el
-- mismo de la 0096, con la columna sumada en los tres lugares donde va.

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
  destacado boolean, plan text, portada_thumb_url text, portada_pos smallint,
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
      c.portada_thumb_url, c.portada_pos
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
         destacado, plan, portada_thumb_url, portada_pos,
         count(*) over () as total
    from filtrados order by rank desc, nombre
   limit case when p_limit <= 0 then null else greatest(1, least(p_limit, 500)) end
  offset greatest(0, p_offset);
$$;

grant execute on function buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text)
  to anon, authenticated, service_role;
