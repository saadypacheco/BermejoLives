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

\pset border 2
\pset pager off

drop view if exists _audit_match;
drop view if exists _audit_texto;

create temp view _audit_texto as
  select c.id,
         coalesce(c.codigo::text, '????')                     as codigo,
         coalesce(c.nombre, '')                               as nombre,
         unaccent(lower(concat_ws(' ', c.prod_det_ia, c.subcategoria,
                                       c.sinonimos, c.nombre))) as t
    from comercios c
   where c.activo;

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
\echo 'Nada de esto escribió una sola fila. Ver la cabecera para el orden de trabajo.'
