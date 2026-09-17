-- Los servicios de la ciudad son rubros, y el rubro principal va primero.
--
-- Revisando cada acceso del home contra la base (16/9/2026):
--
--  · "Baños" mostraba cero. La 0110 había abierto una segunda forma de cargar
--    baños, cajeros y estacionamientos —la tabla `lugares` con un tipo— y el
--    buscador miraba sólo ésa, que estaba vacía. Los nueve baños públicos
--    reales estaban cargados como comercios del rubro `banos` desde campo,
--    que es como se carga todo lo demás. Dos formas de cargar lo mismo es
--    una que se mira y otra que se llena. Queda UNA: rubros. Se crean los
--    que faltaban, no comerciales como `banos`.
--  · "Casas de cambio" empezaba con COMERCIAL FIDEL, ropa de jean, y
--    "Farmacias" con una heladería: el filtro por rubro toma cualquiera de
--    los rubros del comercio, y con el orden por nombre un secundario mal
--    asignado sube a primero. Ahora, filtrando por rubro, los que lo tienen
--    como PRINCIPAL van antes. Los secundarios siguen entrando (FARMACIA
--    AMANECER tiene `bebes` de principal y es una farmacia), pero al final.

insert into rubros (slug, nombre, icono, orden, comercial) values
  ('estacionamiento', '🅿️ Estacionamientos',  '🅿️', 56, false),
  ('cajeros',         '🏧 Cajeros y bancos',   '🏧', 57, false),
  ('wifi',            '📶 Wifi gratis',        '📶', 58, false)
on conflict (slug) do update set
  nombre = excluded.nombre, icono = excluded.icono,
  orden = excluded.orden, comercial = excluded.comercial, activo = true;

-- Las palabras del servicio, no las de la mercadería: "banco" a secas es un
-- banco de carpintero, y "estacionar" aparece en cualquier hotel.
insert into rubro_palabras (rubro_slug, patron) values
  ('estacionamiento', '\m(estacionamiento|cochera|parking|playa de estacionamiento|guarderia de vehiculos)'),
  ('cajeros',         '\m(cajeros? automaticos?|atm\M|agencia bancaria|sucursal bancaria|banco (union|nacional|mercantil|bisa|fie|sol|ganadero|economico|prodem|bcp|bnb))'),
  ('wifi',            '\m(zona wifi|wifi gratis|wi-fi gratis|internet gratis)')
on conflict (rubro_slug, patron) do nothing;

-- Lo que ya estaba cargado bajo "otros" con el servicio en la subcategoría
-- o el nombre pasa a su rubro: la Cochera y la Zona wifi.
with destino as (
  select c.id as comercio_id, r.id as rubro_id
  from comercios c
  join rubros ro on ro.id = c.rubro_id and ro.slug = 'otros'
  join rubros r on r.slug = case
      when lower(unaccent(coalesce(c.subcategoria, ''))) ~ '\m(estacionamiento|cochera)' then 'estacionamiento'
      when lower(unaccent(c.nombre)) ~ '\m(zona wifi|wifi gratis)' then 'wifi'
      when lower(unaccent(coalesce(c.subcategoria, '') || ' ' || c.nombre)) ~ '\m(cajero|cajeros)' then 'cajeros'
    end
),
mov as (
  update comercios c set rubro_id = d.rubro_id from destino d where c.id = d.comercio_id
  returning c.id, c.rubro_id
)
insert into comercio_rubros (comercio_id, rubro_id)
select id, rubro_id from mov
on conflict do nothing;

-- El "otros" que les quedó de secundario ya no dice nada.
delete from comercio_rubros cr
using comercios c, rubros r
where cr.comercio_id = c.id and cr.rubro_id = r.id and r.slug = 'otros'
  and c.rubro_id <> r.id
  and exists (select 1 from rubros r2 where r2.id = c.rubro_id and r2.slug in ('estacionamiento', 'wifi', 'cajeros'));

-- ------------------------------------------------- buscar_comercios
-- Mismo cuerpo que la 0105 más `principal`: filtrando por rubro, primero los
-- que lo tienen de principal. Misma firma, así que `create or replace`.
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
              + case when exists (
                  select 1 from comercio_rubros cr3 join rubros r4 on r4.id = cr3.rubro_id
                  where cr3.comercio_id = c.id
                    and (to_tsvector('spanish_unaccent', r4.nombre) @@ e.tsq_todas
                         or lower(unaccent(r4.nombre)) ~ e.inicio_palabra)
                ) then 0.35 else 0 end
              + similarity(lower(unaccent(c.nombre)), e.texto) * 0.3
              + similarity(lower(unaccent(coalesce(c.subcategoria, ''))), e.texto) * 0.25
            end)::real as rank,
      -- Filtrando por rubro: ¿es SU rubro, o uno más de los que tiene?
      (p_rubro is not null and r.slug = p_rubro) as principal,
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
    order by c.id, fuerte desc, rank desc
  ),
  medidos as (
    select b.*, sum(case when b.fuerte then 1 else 0 end) over () as n_fuertes from base b
  ),
  filtrados as (
    select * from medidos where coalesce(n_fuertes, 0) < 5 or fuerte
  )
  select id, slug, nombre, descripcion, logo_url, portada_url, whatsapp, direccion,
         lat, lng, modalidad, rubro_slug, rubro_nombre, subcategoria, zona_nombre, rating, verificado,
         ofertas, rank, monedas_aceptadas, envios_internacionales, tiene_factura,
         horario, tiene_stock, ciudad_nombre, ciudad_pais,
         prod_obs_human, prod_det_ia,
         destacado, plan, portada_thumb_url, portada_pos,
         count(*) over () as total
    from filtrados order by rank desc, principal desc, nombre, id
   limit case when p_limit <= 0 then null else greatest(1, least(p_limit, 500)) end
  offset greatest(0, p_offset);
$$;

grant execute on function buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text)
  to anon, authenticated, service_role;
