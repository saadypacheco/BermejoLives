-- ¿POR QUÉ matcheó cada resultado? SÓLO LECTURA.
--
--   cd /docker/uruku
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U postgres -d postgres -v q="'remera'" -f - < supabase/diagnostico_buscador.sql
--
-- Sin -v q, prueba una lista de consultas típicas.
--
-- El reclamo es "me trae lo que pido pero además cosas que no tienen nada que
-- ver". buscar_comercios() acepta un resultado por CUALQUIERA de seis caminos
-- distintos, y desde afuera todos se ven igual: una fila en la lista. Sin saber
-- por cuál entró cada uno es imposible decir si sobra un camino, si sobra un
-- umbral, o si el dato está mal cargado — y cualquier arreglo sería a ciegas.
--
-- Esta consulta repite las mismas condiciones del buscador pero mostrando cuál
-- se cumplió. La columna `via` es la respuesta.

\set ON_ERROR_STOP off
\if :{?q}
  \set unaq :q
\else
  \set q '''__todas__'''
\endif

\pset border 2

\echo ''
\echo '################ POR QUÉ ENTRÓ CADA RESULTADO ################'
\echo 'texto      = la palabra está en su ficha (nombre, productos, sinónimos…)'
\echo 'nombre     = el nombre del local contiene lo buscado'
\echo 'CATEGORIA  = pertenece a un rubro cuyo NOMBRE contiene lo buscado'
\echo '             (trae el rubro entero, aunque ese local no venda eso)'
\echo 'parecido   = trigramas: se PARECE a lo buscado, sin contenerlo'
\echo ''
\echo 'Los "parecido" y los "CATEGORIA" son los sospechosos de traer ruido.'

with consultas as (
  select unnest(case when :q = '__todas__'
                     then array['remera','olla','ropa','termo','celular','zapatilla','bazar']
                     else array[:q] end) as q
)
select
  co.q                                   as consulta,
  left(c.nombre, 26)                     as comercio,
  case
    when c.busqueda @@ websearch_to_tsquery('spanish_unaccent', co.q) then 'texto'
    when unaccent(lower(c.nombre)) like '%' || unaccent(lower(co.q)) || '%' then 'nombre'
    when exists (select 1 from comercio_rubros cr join rubros r on r.id = cr.rubro_id
                  where cr.comercio_id = c.id
                    and unaccent(lower(r.nombre)) like '%' || unaccent(lower(co.q)) || '%')
         then 'CATEGORIA'
    else 'parecido'
  end                                    as via,
  round(similarity(lower(unaccent(c.nombre)), lower(unaccent(co.q)))::numeric, 2) as sim_nombre,
  left(coalesce(c.subcategoria, ''), 18) as subcategoria,
  left(coalesce(c.prod_det_ia, ''), 46)  as productos
from consultas co
cross join lateral (
  select * from buscar_comercios(co.q, null,null,null,null,null,null, 12, 0)
) res
-- buscar_comercios() no devuelve `busqueda` (es interna), así que para saber si
-- el match fue por texto hay que volver a la tabla por id.
join comercios c on c.id = res.id
order by co.q, 3, 4 desc;

\echo ''
\echo '################ CUÁNTO TRAE CADA CAMINO ################'
\echo 'Si "CATEGORIA" o "parecido" son la mayoría, el buscador está contestando'
\echo 'algo distinto de lo que se le preguntó.'
with consultas as (
  select unnest(case when :q = '__todas__'
                     then array['remera','olla','ropa','termo','celular','zapatilla','bazar']
                     else array[:q] end) as q
), clasificado as (
  select co.q,
    case
      when c.busqueda @@ websearch_to_tsquery('spanish_unaccent', co.q) then 'texto'
      when unaccent(lower(c.nombre)) like '%' || unaccent(lower(co.q)) || '%' then 'nombre'
      when exists (select 1 from comercio_rubros cr join rubros r on r.id = cr.rubro_id
                    where cr.comercio_id = c.id
                      and unaccent(lower(r.nombre)) like '%' || unaccent(lower(co.q)) || '%')
           then 'CATEGORIA'
      else 'parecido'
    end as via
  from consultas co
  cross join lateral (
    select * from buscar_comercios(co.q, null,null,null,null,null,null, 60, 0)
  ) res
  join comercios c on c.id = res.id
)
select q as consulta,
       count(*)                                   as total,
       count(*) filter (where via = 'texto')      as por_texto,
       count(*) filter (where via = 'nombre')     as por_nombre,
       count(*) filter (where via = 'CATEGORIA')  as por_categoria,
       count(*) filter (where via = 'parecido')   as por_parecido
  from clasificado group by 1 order by 1;

\echo ''
\echo '################ FALSOS POSITIVOS POR PARECIDO ################'
\echo 'Nombres que se parecen a la consulta SIN tener nada que ver. El caso'
\echo 'clásico acá: buscar "olla" y que aparezca "Comercial molla".'
with consultas as (
  select unnest(array['olla','remera','termo','gorra','saco','top','jean']) as q
)
select co.q as consulta, c.nombre as trae,
       round(similarity(lower(unaccent(c.nombre)), lower(unaccent(co.q)))::numeric, 2) as parecido
  from consultas co, comercios c
 where c.activo
   and similarity(lower(unaccent(c.nombre)), lower(unaccent(co.q))) > 0.35
   and not (c.busqueda @@ websearch_to_tsquery('spanish_unaccent', co.q))
   and unaccent(lower(c.nombre)) not like '%' || unaccent(lower(co.q)) || '%'
 order by 3 desc limit 30;

\echo ''
\echo '################ LOS FILTROS ################'
\echo 'Cada filtro contra el total. Un filtro que no cambia el número, o que'
\echo 'deja todo en cero, no le sirve a nadie.'
select 'sin filtro'          as filtro, count(*) from buscar_comercios(null,null,null,null,null,null,null,60,0)
union all select 'modalidad=mayorista', count(*) from buscar_comercios(null,null,'mayorista',null,null,null,null,60,0)
union all select 'modalidad=minorista', count(*) from buscar_comercios(null,null,'minorista',null,null,null,null,60,0)
union all select 'ciudad=bermejo',  count(*) from buscar_comercios(null,null,null,null,null,null,'bermejo',60,0);

\echo ''
\echo '################ CADA FILTRO DE CATEGORÍA, UNO POR UNO ################'
\echo 'tiene    = comercios con ese rubro'
\echo 'devuelve = lo que trae el filtro con ese slug'
\echo 'Un rubro con comercios cuyo filtro devuelve 0 es un chip que el comprador'
\echo 'toca y le vacía la pantalla. Se prueban TODOS los slugs y no uno elegido'
\echo 'a mano, que fue el error de la corrida anterior: probé "moda-y-ropa", dio'
\echo 'cero, y el cero era mío por inventar el slug — no del filtro.'
select r.slug,
       left(r.nombre, 26)                                   as rubro,
       count(cr.comercio_id)                                 as tiene,
       f.devuelve,
       case when f.devuelve = 0 and count(cr.comercio_id) > 0 then 'ROTO'
            when f.devuelve >= least(count(cr.comercio_id), 60) then 'ok'
            else 'incompleto' end                            as estado
  from rubros r
  left join comercio_rubros cr on cr.rubro_id = r.id
  left join comercios c on c.id = cr.comercio_id and c.activo
  cross join lateral (
    select count(*) as devuelve
      from buscar_comercios(null, r.slug, null,null,null,null,null, 60, 0)
  ) f
 group by r.slug, r.nombre, f.devuelve
having count(cr.comercio_id) > 0
 order by 5 desc, 3 desc;

\echo ''
\echo '################ LAS "OFERTAS" DE LAS TARJETAS ################'
\echo 'La tarjeta muestra "N ofertas" contando publicaciones aprobadas y activas.'
\echo 'Si no hay ninguna publicación cargada, ese contador siempre da 0 y el'
\echo 'filtro "solo ofertas" deja la lista vacía.'
select count(*)                                                as publicaciones,
       count(*) filter (where estado = 'aprobado' and activo)   as aprobadas_activas,
       count(distinct comercio_id) filter (where estado = 'aprobado' and activo) as comercios_con_ofertas
  from publicaciones;
