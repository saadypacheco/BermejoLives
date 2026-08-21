-- Export CSV: qué rubros infiere el diccionario de cada descripción cargada.
-- SÓLO LECTURA. Requiere la migración 0045.
--
--   cd /docker/uruku
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U postgres -d postgres -f - < supabase/export_rubros_csv.sql > rubros.csv
--
-- Después bajás rubros.csv del VPS y lo abrís con Excel (separador coma, UTF-8).
--
-- Columnas:
--   estado            SIN MATCH / 1 rubro / N rubros — por dónde empezar a revisar
--   rubros_sugeridos  todos los que matchean, separados por " | " (multi-rubro)
--   palabras_clave    qué palabras de la descripción los dispararon
--   falta             pista de qué agregar a la descripción cuando no matchea

\pset format csv
\pset tuples_only off

select
  c.slug,
  c.nombre,
  coalesce(l.nombre, '') as lugar,
  coalesce(c.puesto, '') as puesto,
  coalesce(c.descripcion, '') as descripcion,
  case
    when array_length(rubros_sugeridos(coalesce(c.nombre,'') || ' ' || coalesce(c.prod_obs_human,'') || ' ' || coalesce(c.prod_det_ia,'') || ' ' || coalesce(c.descripcion,'')), 1) is null
      then 'SIN MATCH'
    when array_length(rubros_sugeridos(coalesce(c.nombre,'') || ' ' || coalesce(c.prod_obs_human,'') || ' ' || coalesce(c.prod_det_ia,'') || ' ' || coalesce(c.descripcion,'')), 1) = 1
      then '1 rubro'
    else array_length(rubros_sugeridos(coalesce(c.nombre,'') || ' ' || coalesce(c.prod_obs_human,'') || ' ' || coalesce(c.prod_det_ia,'') || ' ' || coalesce(c.descripcion,'')), 1) || ' rubros'
  end as estado,
  (select string_agg(r.nombre, ' | ' order by r.orden)
     from unnest(rubros_sugeridos(coalesce(c.nombre,'') || ' ' || coalesce(c.prod_obs_human,'') || ' ' || coalesce(c.prod_det_ia,'') || ' ' || coalesce(c.descripcion,''))) s
     join rubros r on r.slug = s) as rubros_sugeridos,
  -- Qué palabra concreta disparó cada rubro: sirve para auditar el diccionario y
  -- para entender qué conviene escribir en la próxima descripción.
  (select string_agg(distinct m.palabra, ', ')
     from rubro_palabras rp
     cross join lateral (
       select (regexp_matches(unaccent(lower(coalesce(c.nombre,'') || ' ' || coalesce(c.prod_obs_human,'') || ' ' || coalesce(c.prod_det_ia,'') || ' ' || coalesce(c.descripcion,''))),
                              rp.patron))[1] as palabra
     ) m
    where unaccent(lower(coalesce(c.nombre,'') || ' ' || coalesce(c.prod_obs_human,'') || ' ' || coalesce(c.prod_det_ia,'') || ' ' || coalesce(c.descripcion,''))) ~ rp.patron
  ) as palabras_clave,
  case
    when coalesce(c.descripcion,'') = ''
      then 'Sin descripción: no hay de dónde inferir. Anotar qué vende.'
    when array_length(rubros_sugeridos(coalesce(c.nombre,'') || ' ' || coalesce(c.prod_obs_human,'') || ' ' || coalesce(c.prod_det_ia,'') || ' ' || coalesce(c.descripcion,'')), 1) is null
      then 'La descripción no nombra productos concretos. Agregar 3-5 productos que se ven en el local.'
    else ''
  end as falta,
  case when coalesce(c.whatsapp,'') = '' then 'FALTA' else c.whatsapp end as whatsapp,
  'URUKU-' || c.codigo as codigo
from comercios c
left join lugares l on l.id = c.lugar_id
where c.activo
order by
  case when array_length(rubros_sugeridos(coalesce(c.nombre,'') || ' ' || coalesce(c.prod_obs_human,'') || ' ' || coalesce(c.prod_det_ia,'') || ' ' || coalesce(c.descripcion,'')), 1) is null
       then 0 else 1 end,   -- primero los que no matchean: son los que hay que tocar
  c.nombre;
