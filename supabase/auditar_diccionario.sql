-- ¿QUÉ PALABRA causó cada rubro que completar_rubros.py quiere agregar?
-- SÓLO LECTURA. Cuesta $0: es texto contra texto.
--
--   cd /docker/uruku
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U postgres -d postgres -f - < supabase/auditar_diccionario.sql
--
-- POR QUÉ EXISTE
-- ==============
--
-- `completar_rubros.py` propuso 131 rubros faltantes y ~10 estaban claramente
-- mal ("masa para moldear" mandaba un comercio a panadería, una perfumería caía
-- en ferretería). El script informa QUÉ rubro agregaría y a quién, pero no POR
-- QUÉ: no dice cuál de los 200 y pico patrones de `rubro_palabras` matcheó.
--
-- Sin ese dato, corregir el diccionario es adivinar cuál de las palabras del
-- patrón fue. Y un patrón es una alternancia de veinte términos: `ferreteria`
-- incluye `pintura`, `foco`, `luces`, `cable`… cualquiera de ellos pudo ser.
--
-- Este informe muestra el patrón y el FRAGMENTO DE TEXTO que lo disparó. Un
-- patrón que aparece diez veces con el mismo fragmento equivocado no es un error
-- suelto: es una fila del diccionario para borrar o acotar, y borrarla arregla
-- los diez de una vez.
--
-- ORDEN DE TRABAJO: correr esto → arreglar los patrones que la sección 2 muestre
-- como ruido → recién ahí `completar_rubros.py` con APLICAR=1.
--
-- El texto que se arma acá es el MISMO que arma completar_rubros.py
-- (prod_det_ia + subcategoria + sinonimos + nombre). Si allá cambia, acá también.
--
-- ACOTAR A UNA SALIDA AL CAMPO
-- ============================
--
--   ... psql -U postgres -d postgres -v desde="'2026-08-24'" -f - < supabase/auditar_diccionario.sql
--
-- Sin `desde` mira los comercios activos TODOS. Con `desde`, sólo los dados de
-- alta a partir de esa fecha — para leer lo que trajo una tanda sin que se
-- mezcle con lo que ya venía de antes.
--
-- El corte va por `created_at` y NO por `ia_analizado_at`, por la misma razón
-- que lo explica novedades.sql: el análisis por tandas vuelve a pasar sobre
-- comercios viejos y les mueve la fecha de análisis, así que cortar por ahí
-- marca a todos como nuevos y el informe entero miente. La fecha de alta no la
-- mueve nadie.
--
-- OJO CON LEER EL DICCIONARIO EN UNA TANDA SOLA: los patrones son compartidos
-- por los 273 comercios. Que una palabra no falle en 70 no dice que esté bien,
-- y una que falla una vez acá puede estar fallando diez veces afuera del corte.
-- Para decidir si un patrón sobra, mirar la base entera; el corte sirve para
-- ver qué trajo la salida, no para juzgar el diccionario.

\pset border 2
\pset pager off

\if :{?desde}
\else
  \set desde '1970-01-01'
\endif

\echo ''
\echo '########## EL CORTE ##########'
\echo 'Altas por día. Si el corte no agarra la tanda que esperabas, correr de'
\echo 'nuevo con  -v desde="'"'"'AAAA-MM-DD'"'"'"'
select created_at::date as dia_de_alta,
       count(*)                                                as comercios,
       count(*) filter (where created_at::date >= :desde)      as dentro_del_corte
  from comercios where activo
 group by 1 order by 1 desc limit 10;

drop view if exists _audit_match;
drop view if exists _audit_texto;
drop view if exists _audit_sin_sin;

create temp view _audit_texto as
  select c.id,
         coalesce(c.codigo::text, '????')                     as codigo,
         coalesce(c.nombre, '')                               as nombre,
         unaccent(lower(concat_ws(' ', c.prod_det_ia, c.subcategoria,
                                       c.sinonimos, c.nombre))) as t
    from comercios c
   where c.activo
     and c.created_at::date >= :desde;

-- Cada (comercio, patrón) que matchea, con el pedazo de texto que lo disparó y
-- si el comercio YA tiene ese rubro. Lo que no tiene es lo que se propondría.
create temp view _audit_match as
  select x.id, x.codigo, x.nombre,
         rp.rubro_slug,
         rp.patron,
         substring(x.t from rp.patron)                        as fragmento,
         exists (select 1
                   from comercio_rubros cr
                   join rubros r on r.id = cr.rubro_id
                  where cr.comercio_id = x.id and r.slug = rp.rubro_slug) as ya_lo_tiene
    from _audit_texto x
    join rubro_palabras rp on x.t ~ rp.patron
   where rp.rubro_slug <> 'otros';

\echo ''
\echo '########## 1. RESUMEN: cuánto propondría cada rubro ##########'
\echo 'Es lo mismo que informa completar_rubros.py, para poder cotejar que este'
\echo 'informe está mirando los mismos datos. Si los números no coinciden, no'
\echo 'sigas: uno de los dos está leyendo mal.'
select rubro_slug,
       count(*) filter (where not ya_lo_tiene) as propondria,
       count(*) filter (where ya_lo_tiene)     as ya_asignado
  from _audit_match
 group by 1
having count(*) filter (where not ya_lo_tiene) > 0
 order by 2 desc;

\echo ''
\echo '########## 2. EL DIAGNÓSTICO: qué patrón dispara cada propuesta ##########'
\echo 'Una fila por patrón. `propondria` es a cuántos comercios metería en ese'
\echo 'rubro, y `ejemplos` muestra el texto que matcheó.'
\echo ''
\echo 'CÓMO LEERLO: si el fragmento no nombra lo que el rubro vende, el patrón'
\echo 'está de más. "pintura" en ferretería matcheando "pintura de uñas" es una'
\echo 'fila para acotar, no un comercio para corregir a mano.'
select rubro_slug,
       patron,
       count(*) filter (where not ya_lo_tiene) as propondria,
       string_agg(distinct fragmento, ' · ') filter (where not ya_lo_tiene) as fragmentos,
       left(string_agg(distinct nullif(nombre,''), ' · ')
              filter (where not ya_lo_tiene), 90)              as comercios
  from _audit_match
 group by 1, 2
having count(*) filter (where not ya_lo_tiene) > 0
 order by 3 desc, 1;

\echo ''
\echo '########## 3. DETALLE comercio por comercio ##########'
\echo 'Para revisar a ojo los casos raros que la sección 2 deje picando.'
select codigo,
       left(nombre, 22)     as comercio,
       rubro_slug           as le_agregaria,
       fragmento            as por_la_palabra,
       left(patron, 40)     as patron
  from _audit_match
 where not ya_lo_tiene
 order by rubro_slug, codigo;

\echo ''
\echo '########## 4. PATRONES QUE NO MATCHEAN NADA ##########'
\echo 'No hacen daño, pero mienten: el rubro parece cubierto por el diccionario'
\echo 'y en realidad ninguna de esas palabras aparece en ningún comercio. Si un'
\echo 'rubro entero está acá, sus comercios no se van a clasificar solos nunca.'
\echo 'CON `desde` PUESTO ESTA SECCIÓN NO SIRVE PARA BORRAR NADA: un patrón que'
\echo 'no matchea en 70 comercios puede estar matcheando en los otros 200.'
select rp.rubro_slug, rp.patron
  from rubro_palabras rp
  left join _audit_match m on m.patron = rp.patron and m.rubro_slug = rp.rubro_slug
 where m.patron is null
   and rp.rubro_slug <> 'otros'
 order by 1, 2;

\echo ''
\echo '########## 5. LOS QUE QUEDARÍAN CON DEMASIADOS RUBROS ##########'
\echo 'completar_rubros.py saltea a los que superarían 6 rubros (MAX_RUBROS): un'
\echo 'comercio en todas las categorías no filtra en ninguna. Estos quedan sin'
\echo 'tocar y son justamente los que hay que mirar a mano.'
-- `tiene` sale de comercio_rubros y NO de los matches: un rubro puesto a mano
-- que ninguna palabra del diccionario respalda igual ocupa lugar, y contarlo de
-- menos haría pasar el tope a comercios que en realidad ya lo superan.
with total as (
  select x.id, x.codigo, x.nombre,
         (select count(*) from comercio_rubros cr
            join rubros r on r.id = cr.rubro_id and r.slug <> 'otros'
           where cr.comercio_id = x.id)                            as tiene,
         (select count(distinct m.rubro_slug) from _audit_match m
           where m.id = x.id and not m.ya_lo_tiene)                as sumaria
    from _audit_texto x
)
select codigo, left(nombre, 30) as comercio, tiene, sumaria,
       tiene + sumaria as quedaria
  from total
 where tiene + sumaria > 6
 order by 5 desc;

\echo ''
\echo '########## 6. ¿CUÁNTAS PALABRAS DISTINTAS RESPALDAN CADA PROPUESTA? ##########'
\echo 'La pregunta que decide el umbral: ¿vender ropa interior alcanza para SER'
\echo 'una lencería? Un local dedicado matchea diez o doce palabras del rubro;'
\echo 'uno que la tiene de paso matchea una o dos. Si la distribución se parte'
\echo 'en dos grupos, el corte está donde se parte y no hace falta discutirlo.'
select rubro_slug,
       palabras                                as palabras_distintas,
       count(*)                                as comercios,
       left(string_agg(nombre, ' · '), 70)     as ejemplos
  from (
    select rubro_slug, id, max(nombre) as nombre,
           count(distinct patron) as palabras
      from _audit_match
     where not ya_lo_tiene
     group by 1, 2
  ) q
 where rubro_slug in ('lenceria', 'marroquineria', 'blanqueria')
 group by 1, 2
 order by 1, 2 desc;

\echo ''
\echo '########## 7. EL TEXTO COMPLETO DE LOS CASOS DUDOSOS ##########'
\echo 'Los que hay que leer enteros antes de tocar el diccionario: una propuesta'
\echo 'de ferretería disparada por `led` o `pintura` puede ser una ferretería de'
\echo 'verdad o una perfumería con luces en la vidriera, y el fragmento solo no'
\echo 'lo distingue.'
select distinct
       x.codigo,
       left(x.nombre, 24)                as comercio,
       m.rubro_slug                      as le_agregaria,
       m.fragmento                       as por_la_palabra,
       left(coalesce(c.prod_det_ia, ''), 150) as vende
  from _audit_match m
  join _audit_texto x on x.id = m.id
  join comercios    c on c.id = m.id
 where not m.ya_lo_tiene
   and m.fragmento in ('led', 'pintura', 'construccion', 'masita', 'casco',
                       'jugo', 'fruta', 'toalla', 'lapiz', 'termo', 'olla')
 order by 3, 1;

\echo ''
\echo '########## 8. ¿CUÁNTO RUIDO METE EL BLOB DE SINÓNIMOS? ##########'
\echo 'El texto que se matchea incluye comercios.sinonimos, que son las OTRAS'
\echo 'formas de decir lo que vende — y ahí entran palabras que el local no'
\echo 'vende: "bolso matero" arrastra `termo`, "licuado" arrastra `jugo`, un'
\echo '"juego de cocina" de juguete arrastra `olla`.'
\echo ''
\echo 'Los sinónimos existen para que el COMPRADOR encuentre (busca "polera" y'
\echo 'aparece el que vende remeras). Clasificar es otra cosa: ahí la pregunta'
\echo 'es qué vende, y la respuesta ya está escrita en prod_det_ia.'
\echo ''
\echo 'Esta tabla compara las propuestas con y sin el blob. La diferencia es'
\echo 'exactamente lo que se ganaría sacándolo de completar_rubros.py.'
create temp view _audit_sin_sin as
  select c.id,
         unaccent(lower(concat_ws(' ', c.prod_det_ia, c.subcategoria, c.nombre))) as t
    from comercios c
   where c.activo
     and c.created_at::date >= :desde;

with limpio as (
  select rp.rubro_slug, s.id
    from _audit_sin_sin s
    join rubro_palabras rp on s.t ~ rp.patron
   where rp.rubro_slug <> 'otros'
     and not exists (select 1 from comercio_rubros cr
                       join rubros r on r.id = cr.rubro_id
                      where cr.comercio_id = s.id and r.slug = rp.rubro_slug)
),
con as (
  select rubro_slug, count(distinct id) as n
    from _audit_match where not ya_lo_tiene group by 1
)
select coalesce(con.rubro_slug, l.rubro_slug)       as rubro_slug,
       coalesce(con.n, 0)                            as con_sinonimos,
       coalesce(count(distinct l.id), 0)             as solo_lo_que_vende,
       coalesce(con.n, 0) - coalesce(count(distinct l.id), 0) as se_caen
  from con
  full join limpio l on l.rubro_slug = con.rubro_slug
 group by 1, con.n
 order by 4 desc, 2 desc;

\echo ''
\echo 'Nada de esto escribió una sola fila. Ver la cabecera para el orden de trabajo.'
