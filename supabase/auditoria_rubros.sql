-- ¿Los 54 rubros describen bien lo que hay en Bermejo? SÓLO LECTURA, SIN IA.
--
--   cd /docker/uruku
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U postgres -d postgres -f - < supabase/auditoria_rubros.sql
--
-- La taxonomía de 54 rubros se escribió ANTES de ver un solo comercio. Ahora hay
-- 161 locales con productos detectados: eso es evidencia para juzgarla, y no
-- hace falta preguntarle nada al modelo para obtenerla.
--
-- Cuatro defectos posibles, y cada consulta busca uno:
--
--   SOBRAN   — rubros que nadie usa. Ocupan lugar en el filtro y no filtran nada.
--   FALTAN   — productos que no caen en ningún rubro real.
--   ESTORBAN — rubros tan grandes que elegirlos no reduce la búsqueda.
--   SE PISAN — rubros distintos con el mismo vocabulario adentro.

\pset border 2

\echo ''
\echo '################ 1. RUBROS QUE NADIE USA ################'
\echo 'Cero comercios. Cada uno es una opción de más en el filtro que siempre'
\echo 'devuelve vacío. O se sacan, o hay que salir a buscar esos negocios.'
select r.nombre as rubro, r.slug
  from rubros r
 where not exists (select 1 from comercio_rubros cr where cr.rubro_id = r.id)
 order by r.nombre;

\echo ''
\echo '################ 2. RUBROS DEMASIADO GRANDES ################'
\echo 'Un filtro con 86 locales de 161 no filtra: el comprador queda igual que'
\echo 'antes de usarlo. La columna subcategorias dice si hay con qué partirlo.'
select coalesce(r.nombre, '(sin rubro)')            as rubro,
       count(distinct c.id)                          as comercios,
       round(100.0 * count(distinct c.id) /
             nullif((select count(*) from comercios where activo), 0), 1) as porcentaje,
       count(distinct c.subcategoria_norm)           as subcategorias
  from comercio_rubros cr
  join rubros r    on r.id = cr.rubro_id
  join comercios c on c.id = cr.comercio_id and c.activo
 group by 1
having count(distinct c.id) >= 15
 order by 2 desc;

\echo ''
\echo '################ 3. CÓMO PARTIR LOS GRANDES ################'
\echo 'Las subcategorías que viven dentro de cada rubro grande. Si una junta'
\echo 'varios comercios y es específica, ya es un rubro esperando que lo creen.'
select r.nombre                as rubro,
       c.subcategoria_norm     as subcategoria,
       count(*)                as comercios
  from comercio_rubros cr
  join rubros r    on r.id = cr.rubro_id
  join comercios c on c.id = cr.comercio_id and c.activo
 where coalesce(c.subcategoria_norm, '') <> ''
   and r.id in (
     select cr2.rubro_id from comercio_rubros cr2
     join comercios c2 on c2.id = cr2.comercio_id and c2.activo
     group by cr2.rubro_id having count(*) >= 15)
 group by 1, 2
having count(*) >= 2
 order by 1, 3 desc;

\echo ''
\echo '################ 4. PRODUCTOS SIN RUBRO REAL ################'
\echo 'Lo que se ve en las vidrieras de los comercios que siguen en "Otros".'
\echo 'Si una palabra se repite acá, es un rubro que falta: son negocios que'
\echo 'existen y que hoy no aparecen en ninguna búsqueda por categoría.'
with sin_rubro as (
  select c.id, c.prod_det_ia, c.subcategoria
    from comercios c
   where c.activo
     and not exists (
       select 1 from comercio_rubros cr join rubros r on r.id = cr.rubro_id
        where cr.comercio_id = c.id and r.slug <> 'otros')
)
select trim(lower(unaccent(p))) as termino, count(*) as veces
  from sin_rubro s,
       lateral unnest(string_to_array(coalesce(s.prod_det_ia,'') || ',' ||
                                      coalesce(s.subcategoria,''), ',')) as p
 where length(trim(p)) >= 3
 group by 1 order by 2 desc, 1 limit 40;

\echo ''
\echo '################ 5. RUBROS QUE SE PISAN ################'
\echo 'Pares que comparten muchos comercios. Compartir algunos es normal —un'
\echo 'local vende de todo— pero si casi siempre van juntos, son un rubro solo'
\echo 'partido en dos, y obligan al comprador a elegir sin saber cuál.'
with pares as (
  select r1.nombre as rubro_a, r2.nombre as rubro_b, count(*) as juntos
    from comercio_rubros a
    join comercio_rubros b on b.comercio_id = a.comercio_id and b.rubro_id > a.rubro_id
    join rubros r1 on r1.id = a.rubro_id
    join rubros r2 on r2.id = b.rubro_id
    join comercios c on c.id = a.comercio_id and c.activo
   where r1.slug <> 'otros' and r2.slug <> 'otros'
   group by 1, 2
)
select p.rubro_a, p.rubro_b, p.juntos,
       (select count(*) from comercio_rubros x join rubros rx on rx.id = x.rubro_id
         where rx.nombre = p.rubro_a) as total_a,
       (select count(*) from comercio_rubros y join rubros ry on ry.id = y.rubro_id
         where ry.nombre = p.rubro_b) as total_b
  from pares p
 where p.juntos >= 8
 order by p.juntos desc limit 25;

\echo ''
\echo '################ 6. EL VOCABULARIO DE CADA RUBRO ################'
\echo 'Los productos más vistos dentro de cada rubro. Sirve para dos cosas: ver'
\echo 'si el nombre del rubro describe lo que realmente hay adentro, y detectar'
\echo 'comercios mal clasificados (un producto raro en un rubro que no le toca).'
with prod as (
  select r.nombre as rubro, trim(lower(unaccent(p))) as termino
    from comercio_rubros cr
    join rubros r    on r.id = cr.rubro_id
    join comercios c on c.id = cr.comercio_id and c.activo,
         lateral unnest(string_to_array(coalesce(c.prod_det_ia,''), ',')) as p
   where length(trim(p)) >= 3 and r.slug <> 'otros'
)
select rubro, string_agg(termino || ' (' || n || ')', ', ' order by n desc) as productos
  from (select rubro, termino, count(*) as n from prod group by 1, 2) t
 where n >= 2
 group by rubro order by rubro;
