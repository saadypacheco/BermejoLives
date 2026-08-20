-- analisis_buscador.sql — ¿Encuentran los compradores lo que cargamos?
-- SÓLO LECTURA.
--
--   cd /docker/uruku
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U postgres -d postgres -f - < supabase/analisis_buscador.sql
--
-- Qué indexa buscar_comercios (0006 + 0035), que es lo único que decide si un
-- local aparece o no:
--   · comercios.busqueda = nombre + descripcion + direccion
--   · nombre por LIKE (coincidencia parcial)
--   · nombre de los rubros en comercio_rubros (la tabla N-a-N, no rubro_id)
--   · publicaciones APROBADAS y activas (titulo + descripcion)
-- Un comercio sin descripción, sin dirección, con nombre genérico y sin rubros
-- es, para el comprador, invisible.

\pset border 2

\echo ''
\echo '################ 1. ¿ES ENCONTRABLE CADA COMERCIO? ################'
\echo 'nombre_util = el nombre sirve para buscar (no es "Comercio" ni el rubro pelado)'
\echo 'Un comercio con todo en ✗ sólo se encuentra si el comprador lo ve en el mapa.'
select
  left(c.nombre, 24)                                          as comercio,
  case when c.nombre is null or c.nombre = ''
            or lower(c.nombre) = 'comercio' then '✗' else '✓' end as nombre_util,
  case when coalesce(c.descripcion,'') <> '' then '✓' else '✗' end as descrip,
  case when coalesce(c.direccion,'')   <> '' then '✓' else '✗' end as direccion,
  (select count(*) from comercio_rubros cr where cr.comercio_id = c.id) as rubros,
  (select count(*) from publicaciones p
     where p.comercio_id = c.id and p.estado='aprobado' and p.activo) as ofertas,
  -- Cuántas "vías de entrada" tiene: cada una es una forma distinta de llegar a él.
  ( (case when coalesce(c.descripcion,'') <> '' then 1 else 0 end)
  + (case when coalesce(c.direccion,'')   <> '' then 1 else 0 end)
  + (case when c.nombre is not null and lower(c.nombre) <> 'comercio' then 1 else 0 end)
  + (case when exists (select 1 from comercio_rubros cr where cr.comercio_id=c.id) then 1 else 0 end)
  + (case when exists (select 1 from publicaciones p where p.comercio_id=c.id
                         and p.estado='aprobado' and p.activo) then 1 else 0 end)
  )                                                            as vias
from comercios c
where c.activo
order by vias, c.nombre;

\echo ''
\echo '################ 2. INVISIBLES AL BUSCADOR ################'
\echo 'Están en el mapa pero NO salen en ninguna búsqueda por texto.'
select left(c.nombre,24) as comercio, c.slug, 'URUKU-' || c.codigo as codigo
from comercios c
where c.activo
  and coalesce(c.descripcion,'') = ''
  and coalesce(c.direccion,'')   = ''
  and (c.nombre is null or lower(c.nombre) = 'comercio')
  and not exists (select 1 from comercio_rubros cr where cr.comercio_id = c.id)
order by c.nombre;

\echo ''
\echo '################ 3. RUBROS: LA VÍA MÁS BARATA ################'
\echo 'El buscador matchea por el NOMBRE del rubro vía comercio_rubros. Un comercio'
\echo 'sin filas ahí no aparece cuando alguien busca "ferretería" o "farmacia",'
\echo 'aunque tenga rubro_id cargado.'
select
  left(c.nombre,24) as comercio,
  coalesce(r.nombre,'(sin rubro_id)') as rubro_principal,
  (select count(*) from comercio_rubros cr where cr.comercio_id=c.id) as en_comercio_rubros,
  case when c.rubro_id is not null
        and not exists (select 1 from comercio_rubros cr where cr.comercio_id=c.id)
       then '⚠ tiene rubro_id pero NO está en comercio_rubros' end as alerta
from comercios c
left join rubros r on r.id = c.rubro_id
where c.activo
order by en_comercio_rubros, c.nombre;

\echo ''
\echo '################ 4. QUÉ BUSCAN LOS COMPRADORES ################'
select query, count(*) as veces, max(created_at)::date as ultima
from busquedas
where coalesce(query,'') <> ''
group by query order by veces desc, ultima desc limit 25;

\echo ''
\echo '################ 5. BÚSQUEDAS SIN NINGÚN RESULTADO ################'
\echo 'Demanda real que hoy no tiene oferta cargada. Es la mejor lista de'
\echo 'prioridades para el próximo recorrido.'
select query, count(*) as veces, max(created_at)::date as ultima
from busquedas
where coalesce(query,'') <> '' and resultados = 0
group by query order by veces desc, ultima desc limit 25;

\echo ''
\echo '################ 6. SIMULACIÓN: QUÉ DEVUELVE EL BUSCADOR HOY ################'
\echo 'Se corre buscar_comercios() con términos típicos, igual que el comprador.'

\echo ''
\echo '--- "empanadas" ---'
select nombre, verificado, ofertas, round(rank::numeric, 3) as rank
from buscar_comercios('empanadas', null, null, null, null, null, null, 10, 0);

\echo ''
\echo '--- "ferreteria" ---'
select nombre, verificado, ofertas, round(rank::numeric, 3) as rank
from buscar_comercios('ferreteria', null, null, null, null, null, null, 10, 0);

\echo ''
\echo '--- "farmacia" ---'
select nombre, verificado, ofertas, round(rank::numeric, 3) as rank
from buscar_comercios('farmacia', null, null, null, null, null, null, 10, 0);

\echo ''
\echo '--- "ropa" ---'
select nombre, verificado, ofertas, round(rank::numeric, 3) as rank
from buscar_comercios('ropa', null, null, null, null, null, null, 10, 0);

\echo ''
\echo '--- "mercado central" ---'
select nombre, verificado, ofertas, round(rank::numeric, 3) as rank
from buscar_comercios('mercado central', null, null, null, null, null, null, 10, 0);

\echo ''
\echo '################ 7. SINCRONIZACIÓN: ¿ENTRÓ TODO? ################'
\echo 'Altas por día y por quién las cargó. Un hueco acá es trabajo que se perdió.'
select created_at::date as dia, cargado_por, count(*) as altas,
       count(*) filter (where whatsapp is not null and whatsapp <> '') as con_whatsapp,
       count(*) filter (where portada_url is not null)                 as con_foto,
       count(*) filter (where lugar_id is not null)                    as en_mercado
from comercios
where activo
group by 1, 2 order by 1 desc;

\echo ''
\echo '################ 8. RESUMEN DE ENCONTRABILIDAD ################'
select
  count(*)                                                             as activos,
  count(*) filter (where coalesce(descripcion,'') <> '')               as con_descripcion,
  count(*) filter (where coalesce(direccion,'')   <> '')               as con_direccion,
  count(*) filter (where exists (select 1 from comercio_rubros cr where cr.comercio_id = comercios.id)) as con_rubros,
  count(*) filter (where lower(coalesce(nombre,'')) = 'comercio')      as sin_nombre_real
from comercios where activo;
