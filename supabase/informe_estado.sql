-- Panorama del catálogo en una corrida. SÓLO LECTURA.
--
--   cd /docker/uruku
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U postgres -d postgres -f - < supabase/informe_estado.sql
--
-- Responde, en orden: cuánto hay, qué tan encontrable es, cómo quedó la
-- clasificación por IA, qué categorías faltan y qué busca la gente.

\pset border 2

\echo ''
\echo '################ 1. EL EMBUDO ################'
\echo 'De todo lo cargado, cuánto sirve realmente al comprador.'
select
  count(*)                                                                  as cargados,
  count(*) filter (where portada_url is not null)                           as con_foto,
  count(*) filter (where ia_analizado_at is not null)                       as analizados_ia,
  count(*) filter (where prod_det_ia is not null or prod_obs_human is not null) as con_productos,
  count(*) filter (where rubro_id is not null
                     and rubro_id <> (select id from rubros where slug='otros')) as clasificados,
  count(*) filter (where coalesce(whatsapp,'') <> '')                       as reservables
from comercios where activo;

\echo ''
\echo '################ 2. CLASIFICACIÓN POR RUBRO ################'
\echo 'Si "Otros" sigue arriba, la búsqueda por categoría todavía no sirve.'
select coalesce(r.nombre, '(sin rubro)') as rubro, count(*) as comercios
  from comercios c left join rubros r on r.id = c.rubro_id
 where c.activo group by 1 order by 2 desc;

\echo ''
\echo '################ 3. SUBCATEGORÍAS QUE APARECIERON ################'
\echo 'Las propuso la IA mirando fotos de locales reales. De acá sale la'
\echo 'taxonomía, en vez de inventar una lista de antemano.'
select subcategoria, count(*) as veces
  from comercios where activo and coalesce(subcategoria,'') <> ''
 group by 1 order by 2 desc, 1 limit 40;

\echo ''
\echo '################ 4. CATEGORÍAS QUE EL MODELO PIDIÓ Y NO EXISTEN ################'
\echo 'Cada una es el modelo diciendo que le falta un rubro. Las de arriba,'
\echo 'primero.'
select normalizado, count(*) as veces, string_agg(distinct texto, ' | ') as variantes
  from rubros_propuestos group by 1 order by 2 desc limit 25;

\echo ''
\echo '################ 5. LOS QUE LA IA NO PUDO LEER ################'
\echo 'Analizados pero sin productos detectados: la foto no muestra mercadería.'
\echo 'Esta es la lista de locales a los que hay que volver a sacarles foto.'
select slug, left(nombre, 26) as nombre, 'URUKU-' || codigo as codigo,
       coalesce(l.nombre, '(a la calle)') as lugar
  from comercios c left join lugares l on l.id = c.lugar_id
 where c.activo and c.ia_analizado_at is not null and c.prod_det_ia is null
 order by c.nombre limit 40;

\echo ''
\echo '################ 6. SIN WHATSAPP: NO PUEDEN RECIBIR RESERVAS ################'
select count(*) as sin_whatsapp,
       round(100.0 * count(*) / nullif((select count(*) from comercios where activo), 0), 1) as porcentaje
  from comercios where activo and coalesce(whatsapp,'') = '';

\echo ''
\echo '################ 7. QUÉ BUSCA LA GENTE ################'
select query, count(*) as veces,
       count(*) filter (where resultados = 0) as sin_resultado
  from busquedas where coalesce(query,'') <> ''
 group by 1 order by 2 desc limit 20;

\echo ''
\echo '################ 8. PRUEBA DEL BUSCADOR ################'
\echo 'Términos que antes daban cero. Si ahora devuelven, la clasificación sirvió.'
\echo ''
\echo '--- ferreteria ---'
select nombre from buscar_comercios('ferreteria', null,null,null,null,null,null, 5, 0);
\echo '--- farmacia ---'
select nombre from buscar_comercios('farmacia', null,null,null,null,null,null, 5, 0);
\echo '--- jugueteria ---'
select nombre from buscar_comercios('jugueteria', null,null,null,null,null,null, 5, 0);
\echo '--- celulares ---'
select nombre from buscar_comercios('celulares', null,null,null,null,null,null, 5, 0);
\echo '--- ropa ---'
select nombre from buscar_comercios('ropa', null,null,null,null,null,null, 5, 0);
