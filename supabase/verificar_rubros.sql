-- ¿Los rubros que puso la IA coinciden con lo que el local vende? SÓLO LECTURA.
--
--   cd /docker/uruku
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U postgres -d postgres -f - < supabase/verificar_rubros.sql
--
-- La clasificación se hizo mirando fotos. Ahora hay una segunda fuente para
-- contrastarla —los PRODUCTOS que la misma IA escribió— y el diccionario
-- `rubro_palabras`, que sabe qué palabra corresponde a qué rubro. Cruzar las dos
-- cosas encuentra los errores sin volver a llamar al modelo ni pagar un token.
--
-- Dos desacuerdos posibles, y NO son igual de graves:
--
--   SIN RESPALDO — el comercio tiene un rubro que ninguno de sus productos
--   sugiere. Es lo que se ve como "rubro mal asignado": la blanquería que
--   aparece buscando "celular". Ensucia las búsquedas por categoría.
--
--   FALTANTE — los productos sugieren un rubro que el comercio no tiene. No
--   ensucia nada, pero lo deja afuera de un filtro donde debería estar.
--
-- ADVERTENCIA sobre cómo leer esto: `rubro_palabras` es un diccionario escrito a
-- mano y está incompleto. Que un rubro figure "sin respaldo" NO prueba que esté
-- mal — puede ser que al diccionario le falte la palabra. Es una lista para
-- revisar a ojo, no una lista de errores confirmados. Si un rubro aparece entero
-- acá, sospechá del diccionario antes que de la IA.

\pset border 2

\echo ''
\echo '################ 1. ¿PONE MÁS DE UN RUBRO POR NEGOCIO? ################'
\echo 'Era el motivo de tener comercio_rubros: un local que vende neumáticos Y'
\echo 'zapatillas tiene que aparecer buscando cualquiera de las dos cosas.'
with n as (
  select cr.comercio_id, count(*) as rubros
    from comercio_rubros cr
    join rubros r    on r.id = cr.rubro_id and r.slug <> 'otros'
    join comercios c on c.id = cr.comercio_id and c.activo
   group by 1
)
select rubros as rubros_por_comercio, count(*) as comercios
  from n group by 1 order by 1;

\echo ''
\echo 'Promedio y total:'
select round(avg(rubros), 2) as promedio_rubros, count(*) as comercios_clasificados,
       (select count(*) from comercios where activo) as comercios_activos
  from (
    select cr.comercio_id, count(*) as rubros
      from comercio_rubros cr
      join rubros r    on r.id = cr.rubro_id and r.slug <> 'otros'
      join comercios c on c.id = cr.comercio_id and c.activo
     group by 1) t;

\echo ''
\echo '################ 2. RUBROS SIN RESPALDO EN LOS PRODUCTOS ################'
\echo 'El comercio tiene este rubro pero ninguno de sus productos lo sugiere.'
\echo 'Son los candidatos a "mal asignado". Ordenados por rubro para poder'
\echo 'revisarlos de a tandas.'
with texto as (
  select c.id, c.nombre, c.codigo,
         coalesce(c.prod_det_ia,'') || ' ' || coalesce(c.subcategoria,'') || ' ' ||
         coalesce(c.sinonimos,'')   || ' ' || coalesce(c.nombre,'')       as t
    from comercios c where c.activo
)
select r.nombre                              as rubro_asignado,
       'URUKU-' || tx.codigo                 as codigo,
       left(tx.nombre, 22)                   as comercio,
       left(coalesce(c.subcategoria,''), 16) as subcategoria,
       left(coalesce(c.prod_det_ia,''), 44)  as productos
  from comercio_rubros cr
  join rubros r     on r.id = cr.rubro_id and r.slug <> 'otros'
  join texto tx     on tx.id = cr.comercio_id
  join comercios c  on c.id = cr.comercio_id
 where not (r.slug = any (rubros_sugeridos(tx.t)))
 order by r.nombre, tx.nombre
 limit 80;

\echo ''
\echo '################ 3. QUÉ RUBROS ACUMULAN MÁS SOSPECHAS ################'
\echo 'Si un rubro concentra casi todos los desacuerdos, el problema es de ese'
\echo 'rubro —le faltan palabras en el diccionario, o la IA lo usa de cajón— y'
\echo 'no de los comercios sueltos. Se arregla en un lugar, no en cincuenta.'
with texto as (
  select c.id, coalesce(c.prod_det_ia,'') || ' ' || coalesce(c.subcategoria,'') || ' ' ||
                coalesce(c.sinonimos,'')   || ' ' || coalesce(c.nombre,'') as t
    from comercios c where c.activo
)
select r.nombre                                          as rubro,
       count(*)                                           as asignado_a,
       count(*) filter (where not (r.slug = any (rubros_sugeridos(tx.t)))) as sin_respaldo,
       round(100.0 * count(*) filter (where not (r.slug = any (rubros_sugeridos(tx.t))))
             / nullif(count(*), 0), 0)                    as pct
  from comercio_rubros cr
  join rubros r  on r.id = cr.rubro_id and r.slug <> 'otros'
  join texto tx  on tx.id = cr.comercio_id
 group by 1
 order by 4 desc nulls last, 3 desc;

\echo ''
\echo '################ 4. RUBROS QUE FALTAN ################'
\echo 'Los productos sugieren este rubro y el comercio no lo tiene. No ensucia'
\echo 'las búsquedas, pero lo deja afuera de un filtro donde debería estar.'
with texto as (
  select c.id, c.nombre, c.codigo,
         coalesce(c.prod_det_ia,'') || ' ' || coalesce(c.subcategoria,'') || ' ' ||
         coalesce(c.sinonimos,'')   || ' ' || coalesce(c.nombre,'') as t
    from comercios c where c.activo
)
select s.slug                        as rubro_que_falta,
       count(*)                      as comercios,
       string_agg(distinct left(tx.nombre, 18), ', ')  as ejemplos
  from texto tx
  cross join lateral unnest(rubros_sugeridos(tx.t)) as s(slug)
 where not exists (
   select 1 from comercio_rubros cr join rubros r on r.id = cr.rubro_id
    where cr.comercio_id = tx.id and r.slug = s.slug)
 group by 1 order by 2 desc limit 30;

\echo ''
\echo '################ 5. LOS QUE NO TIENEN NINGÚN RUBRO REAL ################'
\echo 'Siguen en "Otros". No aparecen en ninguna búsqueda por categoría.'
select 'URUKU-' || c.codigo as codigo, left(c.nombre, 24) as comercio,
       left(coalesce(c.prod_det_ia, '(sin productos)'), 44) as productos
  from comercios c
 where c.activo
   and not exists (select 1 from comercio_rubros cr join rubros r on r.id = cr.rubro_id
                    where cr.comercio_id = c.id and r.slug <> 'otros')
 order by c.nombre limit 40;

\echo ''
\echo '################ 6. SUBCATEGORÍAS QUE NO PEGAN CON SU RUBRO ################'
\echo 'La subcategoría es lo más específico que escribió la IA. Si no coincide'
\echo 'con ninguno de los rubros del comercio, una de las dos cosas está mal.'
with base as (
  select c.id, c.nombre, c.codigo, c.subcategoria,
         rubros_sugeridos(c.subcategoria) as sugiere
    from comercios c
   where c.activo and coalesce(c.subcategoria,'') <> ''
)
select 'URUKU-' || b.codigo          as codigo,
       left(b.nombre, 20)            as comercio,
       b.subcategoria,
       array_to_string(b.sugiere, ', ')                    as la_subcat_sugiere,
       (select string_agg(r.slug, ', ') from comercio_rubros cr
          join rubros r on r.id = cr.rubro_id and r.slug <> 'otros'
         where cr.comercio_id = b.id)                      as tiene_asignado
  from base b
 where cardinality(b.sugiere) > 0
   and not exists (
     select 1 from comercio_rubros cr join rubros r on r.id = cr.rubro_id
      where cr.comercio_id = b.id and r.slug = any (b.sugiere))
 order by 2 limit 40;
