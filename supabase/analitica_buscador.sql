-- Qué busca la gente, qué no encuentra, y a quién termina eligiendo. SÓLO LECTURA.
--
--   cd /docker/uruku
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U postgres -d postgres -f - < supabase/analitica_buscador.sql
--
-- Otra ventana: -v dias=7
--
-- Este informe se lee al revés de como se escribe. Lo primero que hay que mirar
-- no es qué se busca sino qué NO se encuentra: cada búsqueda con cero
-- resultados es una persona que vino a URUKU con una intención concreta y se
-- fue con las manos vacías. Eso es demanda medida, no supuesta — sirve para
-- decidir a qué comercios salir a buscar.
--
-- Y hay algo peor que el cero, que es la sección 3: búsquedas que SÍ mostraron
-- resultados y nadie tocó ninguno. Desde los números se ven como un éxito.

\set ON_ERROR_STOP off
\if :{?dias}
\else
  \set dias 30
\endif

\pset border 2

\echo ''
\echo '################ 0. CUÁNTO HAY PARA ANALIZAR ################'
\echo 'Con pocas búsquedas registradas, todo lo de abajo es anécdota y no dato.'
select count(*)                                        as busquedas,
       count(*) filter (where resultados = 0)          as sin_resultado,
       count(distinct lower(btrim(query)))             as terminos_distintos,
       min(created_at)::date                           as desde,
       max(created_at)::date                           as hasta
  from busquedas
 where created_at > now() - (:dias || ' days')::interval;

\echo ''
\echo '################ 1. LO QUE LA GENTE NO ENCUENTRA ################'
\echo 'Cero resultados. Cada línea es alguien que vino buscando algo concreto y'
\echo 'se fue sin nada. Es la lista de comercios que faltan cargar, medida con'
\echo 'demanda real en vez de con intuición.'
select lower(btrim(query))     as buscaron,
       count(*)                as veces,
       max(created_at)::date   as ultima_vez
  from busquedas
 where resultados = 0
   and created_at > now() - (:dias || ' days')::interval
 group by 1 order by 2 desc, 3 desc limit 40;

\echo ''
\echo '################ 2. LO MÁS BUSCADO ################'
\echo 'Ordenado por cuántas personas lo buscaron. La columna sin_resultado dice'
\echo 'cuántas de esas veces no encontraron nada: un término muy buscado que'
\echo 'falla seguido es lo más urgente que hay.'
select lower(btrim(query))                          as termino,
       count(*)                                     as veces,
       count(*) filter (where resultados = 0)       as sin_resultado,
       round(avg(resultados), 1)                    as promedio_resultados
  from busquedas
 where created_at > now() - (:dias || ' days')::interval
 group by 1 order by 2 desc limit 40;

\echo ''
\echo '################ 3. BUSCÓ, VIO RESULTADOS, Y NO TOCÓ NADA ################'
\echo 'Peor que el cero: la lista tenía algo pero no lo que la persona buscaba,'
\echo 'y en los números figura como búsqueda exitosa. Si un término aparece'
\echo 'seguido acá, el buscador está trayendo lo que no es.'
select lower(btrim(b.query))   as termino,
       count(*)                as veces_sin_contacto,
       round(avg(b.resultados), 1) as mostraba
  from busquedas b
 where b.resultados > 0
   and b.created_at > now() - (:dias || ' days')::interval
   and not exists (select 1 from leads l where l.busqueda_id = b.id)
 group by 1 order by 2 desc limit 30;

\echo ''
\echo '################ 4. ¿EL BUSCADOR ACIERTA? ################'
\echo 'De las búsquedas que llevaron a un contacto, en qué posición estaba el'
\echo 'comercio elegido. Si la gente elige seguido el quinto o el sexto, el'
\echo 'ranking ordena mal aunque encuentre bien.'
select coalesce(bc.posicion, -1) + 1                  as puesto_elegido,
       count(*)                                        as veces
  from leads l
  join busquedas b          on b.id = l.busqueda_id
  left join busqueda_comercios bc
         on bc.busqueda_id = b.id and bc.comercio_id = l.comercio_id
 where l.busqueda_id is not null
   and l.created_at > now() - (:dias || ' days')::interval
 group by 1 order by 1;

\echo ''
\echo '################ 5. TÉRMINOS QUE TERMINAN EN CONTACTO ################'
\echo 'Los que de verdad mueven la aguja: no los más tipeados, los que llevan a'
\echo 'escribirle a un comercio.'
select lower(btrim(b.query))                      as termino,
       count(distinct b.id)                        as busquedas,
       count(l.id)                                 as contactos,
       round(100.0 * count(l.id) / nullif(count(distinct b.id), 0), 1) as pct
  from busquedas b
  left join leads l on l.busqueda_id = b.id
 where b.created_at > now() - (:dias || ' days')::interval
 group by 1
having count(l.id) > 0
 order by 3 desc limit 30;

\echo ''
\echo '################ 6. LOS COMERCIOS MÁS CONSULTADOS ################'
\echo 'vistas    = abrieron su ficha'
\echo 'whatsapp  = tocaron el botón para escribirle'
\echo 'apariciones = cuántas veces salió en una lista de resultados'
\echo 'Un comercio que aparece mucho y recibe poco está mal presentado (sin'
\echo 'nombre, sin foto) o mal clasificado: lo encuentran y lo descartan.'
select left(c.nombre, 26)                                            as comercio,
       'URUKU-' || c.codigo                                          as codigo,
       count(*) filter (where l.tipo = 'vista')                      as vistas,
       count(*) filter (where l.tipo = 'whatsapp')                   as whatsapp,
       (select count(*) from busqueda_comercios bc join busquedas b on b.id = bc.busqueda_id
         where bc.comercio_id = c.id
           and b.created_at > now() - (:dias || ' days')::interval)  as apariciones
  from comercios c
  left join leads l on l.comercio_id = c.id
                   and l.created_at > now() - (:dias || ' days')::interval
 where c.activo
 group by c.id, c.nombre, c.codigo
having count(l.id) > 0
 order by 3 desc, 4 desc limit 30;

\echo ''
\echo '################ 7. INFORME PARA MANDARLE AL COMERCIO ################'
\echo 'Una línea por local, con lo que le importa a él: cuánta gente lo vio y'
\echo 'cuántos le escribieron por URUKU en la ventana. Es la base del mensaje'
\echo 'mensual — y el argumento concreto a la hora de cobrar el plan.'
select left(c.nombre, 24)                                    as comercio,
       'URUKU-' || c.codigo                                  as codigo,
       coalesce(c.whatsapp, '(sin whatsapp)')                as contacto,
       count(*) filter (where l.tipo = 'vista')              as vieron_su_ficha,
       count(*) filter (where l.tipo = 'whatsapp')           as le_escribieron,
       (select string_agg(distinct lower(btrim(b.query)), ', ')
          from busqueda_comercios bc join busquedas b on b.id = bc.busqueda_id
         where bc.comercio_id = c.id and bc.posicion < 5
           and b.created_at > now() - (:dias || ' days')::interval) as lo_encuentran_buscando
  from comercios c
  left join leads l on l.comercio_id = c.id
                   and l.created_at > now() - (:dias || ' days')::interval
 where c.activo
 group by c.id, c.nombre, c.codigo, c.whatsapp
having count(l.id) > 0
 order by 5 desc, 4 desc limit 40;

\echo ''
\echo '################ 8. PRUEBA: ¿TRAE LO CORRECTO? ################'
\echo 'Para cada término real que la gente buscó, qué devuelve HOY el buscador.'
\echo 'Sirve para revisar a ojo si los primeros resultados tienen sentido, con'
\echo 'las búsquedas de verdad y no con las que se nos ocurren a nosotros.'
with top as (
  select lower(btrim(query)) as q, count(*) as veces
    from busquedas
   where created_at > now() - (:dias || ' days')::interval
   group by 1 order by 2 desc limit 10
)
select t.q as se_busco, t.veces,
       r.nombre as trae_primero,
       round(r.rank::numeric, 3) as rank,
       left(coalesce(r.descripcion, ''), 40) as de_que_es
  from top t
  cross join lateral (
    select * from buscar_comercios(t.q, null,null,null,null,null,null, 3, 0)
  ) r
 order by t.veces desc, r.rank desc;
