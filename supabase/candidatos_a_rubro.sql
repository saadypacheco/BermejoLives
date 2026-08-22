-- ¿Qué categorías le faltan al buscador? SÓLO LECTURA.
--
--   cd /docker/uruku
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U postgres -d postgres -f - < supabase/candidatos_a_rubro.sql
--
-- Las subcategorías que la IA ya escribió mirando 161 vidrieras son evidencia
-- suficiente: no hace falta volver a llamar al modelo para saber qué falta.
--
-- Una subcategoría merece ser rubro cuando se repite en varios locales Y su
-- rubro actual es demasiado genérico. "Ropa deportiva" con 15 comercios metidos
-- dentro de "Moda y ropa" es un filtro que la gente va a querer; "termos y
-- vasos" con 2 no.

\pset border 2

\echo ''
\echo '################ 1. CANDIDATAS A RUBRO PROPIO ################'
\echo 'Subcategorías con 3 o más comercios, y en qué rubro caen hoy.'
\echo 'Si el rubro actual es genérico y la subcategoría es específica, es'
\echo 'candidata: hoy esos comercios comparten filtro con cosas muy distintas.'
select
  lower(unaccent(c.subcategoria))            as subcategoria,
  count(*)                                    as comercios,
  string_agg(distinct coalesce(r.nombre, '(sin rubro)'), ' | ') as rubro_actual
from comercios c
left join rubros r on r.id = c.rubro_id
where c.activo and coalesce(c.subcategoria, '') <> ''
group by 1
having count(*) >= 3
order by 2 desc;

\echo ''
\echo '################ 2. LA COLA LARGA ################'
\echo 'Aparecen 1 o 2 veces. No justifican un rubro, pero YA funcionan en el'
\echo 'buscador: alguien que escriba "marroquinería" encuentra ese local.'
select lower(unaccent(subcategoria)) as subcategoria, count(*) as comercios
  from comercios where activo and coalesce(subcategoria,'') <> ''
 group by 1 having count(*) < 3
 order by 2 desc, 1 limit 60;

\echo ''
\echo '################ 3. RUBROS SOBRECARGADOS ################'
\echo 'Rubros con muchos comercios y muchas subcategorías distintas adentro:'
\echo 'son los que más ganarían con abrirse. Un filtro con 86 locales no filtra.'
select
  coalesce(r.nombre, '(sin rubro)')          as rubro,
  count(*)                                    as comercios,
  count(distinct lower(unaccent(c.subcategoria))) as subcategorias_distintas
from comercios c
left join rubros r on r.id = c.rubro_id
where c.activo
group by 1
having count(*) >= 5
order by 3 desc, 2 desc;

\echo ''
\echo '################ 4. LO QUE LA IA PIDIÓ EXPLÍCITAMENTE ################'
\echo 'Se llena a partir del próximo análisis: hasta ahora el prompt la obligaba'
\echo 'a elegir de la lista y nunca pudo sugerir nada.'
select normalizado, count(*) as veces, string_agg(distinct texto, ' | ') as variantes
  from rubros_propuestos group by 1 order by 2 desc limit 25;

\echo ''
\echo '################ 5. SIN NINGUNA CATEGORÍA ################'
\echo 'Ni rubro real ni subcategoría: la foto no alcanzó. Hay que volver a'
\echo 'fotografiarlos.'
select c.slug, left(c.nombre, 30) as nombre, 'URUKU-' || c.codigo as codigo
  from comercios c
 where c.activo
   and coalesce(c.subcategoria, '') = ''
   and not exists (select 1 from comercio_rubros cr join rubros r2 on r2.id = cr.rubro_id
                    where cr.comercio_id = c.id and r2.slug <> 'otros')
 order by c.nombre limit 40;
