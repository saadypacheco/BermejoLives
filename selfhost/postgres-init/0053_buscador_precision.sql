-- Dos correcciones del buscador salidas de medir contra los 203 comercios.
--
-- 1) "olla" TRAÍA "Comercial molla"
--
--    No era el parecido por trigramas —el diagnóstico descartó eso, cero falsos
--    positivos— sino el match por subcadena: unaccent(lower(nombre)) LIKE
--    '%olla%' y "comercial molla" contiene "olla" adentro de "molla". Un local
--    de ropa deportiva apareciendo entre las ollas.
--
--    Ahora el nombre matchea por PRINCIPIO DE PALABRA. "olla" sigue encontrando
--    "Ollas del Sur" y "ollas", pero no "molla". Es la diferencia entre buscar
--    una palabra y buscar una tira de letras.
--
-- 2) EL FILTRO DE PRECIO VACIABA LA PANTALLA
--
--    La condición era `p.precio <= p_precio_max` sobre un LEFT JOIN a
--    publicaciones. Cuando un comercio no tiene ninguna publicación, p.precio es
--    NULL, y `NULL <= 5000` no es falso: es NULL, que el WHERE descarta igual.
--
--    Hoy hay 1 publicación en toda la base y 0 aprobadas, así que mover el
--    precio dejaba la lista en cero SIEMPRE — sin decir por qué, que es lo peor
--    de este tipo de fallas. Ahora un comercio sin publicaciones no queda
--    excluido por un precio que no tiene.

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
  with entrada as (
    -- El texto buscado, listo para usar de tres formas distintas sin repetir
    -- las conversiones en cada condición.
    select
      lower(unaccent(coalesce(q, ''))) as texto,
      -- Para el regex de principio de palabra hay que neutralizar los
      -- caracteres que el usuario puede tipear y que significan algo en una
      -- expresión regular: buscar "3+1" no puede romper la consulta.
      '\m' || regexp_replace(lower(unaccent(coalesce(q, ''))),
                             '([.^$*+?()\[\]{}|\\-])', '\\\1', 'g') as inicio_palabra
  ),
  base as (
    select distinct on (c.id)
      c.id, c.slug, c.nombre, c.descripcion, c.logo_url, c.portada_url,
      c.whatsapp, c.direccion, c.lat, c.lng, c.modalidad,
      r.slug as rubro_slug, r.nombre as rubro_nombre, z.nombre as zona_nombre,
      c.rating, c.verificado,
      (select count(*) from publicaciones pp
         where pp.comercio_id = c.id and pp.estado = 'aprobado' and pp.activo) as ofertas,
      (case when q is null or q = '' then 1.0
            else
              least(ts_rank(c.busqueda, websearch_to_tsquery('spanish_unaccent', q)) * 4, 1.0)
              + case when lower(unaccent(c.nombre)) ~ e.inicio_palabra then 0.5 else 0 end
              -- Pertenecer al rubro es una señal GRUESA: desempata, no decide.
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
      ci.nombre as ciudad_nombre, ci.pais as ciudad_pais
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
      and (p_zona is null or z.slug = p_zona)
      and (p_ciudad is null or ci.slug = p_ciudad)
      -- Un comercio SIN publicaciones no puede quedar excluido por un precio que
      -- no tiene. Antes `NULL <= p_precio_max` daba NULL y el WHERE lo
      -- descartaba, así que tocar el precio vaciaba la lista entera.
      and (p_precio_min is null or p.precio is null or p.precio >= p_precio_min)
      and (p_precio_max is null or p.precio is null or p.precio <= p_precio_max)
      and (
        q is null or q = ''
        or c.busqueda @@ websearch_to_tsquery('spanish_unaccent', q)
        or p.busqueda @@ websearch_to_tsquery('spanish_unaccent', q)
        -- PRINCIPIO DE PALABRA, no subcadena: "olla" encuentra "Ollas del Sur"
        -- pero ya no "Comercial molla", que es ropa deportiva.
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
         lat, lng, modalidad, rubro_slug, rubro_nombre, zona_nombre, rating, verificado,
         ofertas, rank, monedas_aceptadas, envios_internacionales, tiene_factura,
         horario, tiene_stock, ciudad_nombre, ciudad_pais
    from base order by rank desc, nombre
   limit greatest(1, least(p_limit, 60)) offset greatest(0, p_offset);
$$;
grant execute on function buscar_comercios(text, text, text, text, numeric, numeric, text, int, int) to anon, authenticated;
