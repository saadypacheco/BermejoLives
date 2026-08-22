-- ¿Qué trajo la última salida al campo? SÓLO LECTURA.
--
--   cd /docker/uruku
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U postgres -d postgres -f - < supabase/novedades.sql
--
-- Para comparar contra otro corte, cambiar la fecha de abajo:
--   ... psql -U postgres -d postgres -v desde="'2026-08-22'" -f - < supabase/novedades.sql
--
-- "Nuevo" significa analizado por la IA a partir de esa fecha. La sección 0
-- muestra cómo se reparten los análisis por día: si el corte quedó mal, se ve
-- ahí antes de sacar ninguna conclusión.
--
-- Esta tanda es la PRIMERA analizada con el prompt que puede proponer
-- categorías nuevas y devolver sinónimos por producto. Las 161 anteriores se
-- analizaron con el prompt viejo, que obligaba a elegir de la lista y no dejaba
-- sugerir nada — por eso `rubros_propuestos` estaba vacío, y no porque no
-- faltaran rubros.

\set ON_ERROR_STOP off
\if :{?desde}
\else
  \set desde 'current_date'
\endif

\pset border 2

\echo ''
\echo '################ 0. EL CORTE ################'
\echo 'Análisis por día. Si los "nuevos" no son los que esperabas, correr de'
\echo 'nuevo con  -v desde="'"'"'AAAA-MM-DD'"'"'"'
select ia_analizado_at::date as dia, count(*) as comercios
  from comercios where activo and ia_analizado_at is not null
 group by 1 order by 1 desc limit 10;

\echo ''
\echo '################ 1. CUÁNTO ENTRÓ ################'
select count(*) filter (where ia_analizado_at::date >= :desde)          as nuevos,
       count(*) filter (where ia_analizado_at::date <  :desde)          as ya_estaban,
       count(*) filter (where ia_analizado_at::date >= :desde
                          and prod_det_ia is not null)                  as con_productos,
       count(*) filter (where ia_analizado_at::date >= :desde
                          and coalesce(sinonimos,'') <> '')             as con_sinonimos,
       count(*) filter (where ia_analizado_at::date >= :desde
                          and prod_det_ia is null)                      as foto_sin_mercaderia
  from comercios where activo;

\echo ''
\echo '################ 2. CATEGORÍAS QUE LA IA PIDIÓ ################'
\echo 'Cada fila es el modelo diciendo "este negocio no entra en ninguno de tus'
\echo 'rubros". Es la primera vez que puede decirlo: hasta ahora el prompt se lo'
\echo 'prohibía. Las de arriba, primero.'
select rp.normalizado,
       count(*)                                  as veces,
       string_agg(distinct rp.texto, ' | ')       as como_lo_escribio,
       string_agg(distinct left(c.nombre, 22), ', ') as en_estos_comercios
  from rubros_propuestos rp
  left join comercios c on c.id = rp.comercio_id
 group by 1 order by 2 desc, 1 limit 30;

\echo ''
\echo '################ 3. SUBCATEGORÍAS NUEVAS ################'
\echo 'Las que aparecieron ahora y NO existían en lo ya cargado. Son las que'
\echo 'ensanchan el catálogo; el resto confirma lo que ya sabíamos.'
with nuevas as (
  select distinct subcategoria_norm as s
    from comercios
   where activo and ia_analizado_at::date >= :desde
     and coalesce(subcategoria_norm,'') <> ''
), viejas as (
  select distinct subcategoria_norm as s
    from comercios
   where activo and ia_analizado_at::date < :desde
     and coalesce(subcategoria_norm,'') <> ''
)
select n.s as subcategoria_nueva,
       (select count(*) from comercios c
         where c.activo and c.subcategoria_norm = n.s) as comercios
  from nuevas n
 where not exists (select 1 from viejas v where v.s = n.s)
 order by 2 desc, 1;

\echo ''
\echo '################ 4. PRODUCTOS QUE NUNCA SE HABÍAN VISTO ################'
\echo 'Vocabulario que entra al buscador por primera vez. Si alguno se repite en'
\echo 'varios locales, además es candidato a rubro.'
with terminos_nuevos as (
  select trim(lower(unaccent(p))) as t, count(*) as veces
    from comercios c,
         lateral unnest(string_to_array(coalesce(c.prod_det_ia,''), ',')) as p
   where c.activo and c.ia_analizado_at::date >= :desde and length(trim(p)) >= 3
   group by 1
), terminos_viejos as (
  select distinct trim(lower(unaccent(p))) as t
    from comercios c,
         lateral unnest(string_to_array(coalesce(c.prod_det_ia,''), ',')) as p
   where c.activo and c.ia_analizado_at::date < :desde and length(trim(p)) >= 3
)
select tn.t as producto_nuevo, tn.veces
  from terminos_nuevos tn
 where not exists (select 1 from terminos_viejos tv where tv.t = tn.t)
 order by 2 desc, 1 limit 40;

\echo ''
\echo '################ 5. RUBROS DE LOS NUEVOS ################'
\echo 'Cómo se repartieron. "Otros" alto acá significa que la clasificación no'
\echo 'agarró y hay que mirar esas fotos.'
select r.nombre as rubro, count(*) as comercios
  from comercio_rubros cr
  join rubros r    on r.id = cr.rubro_id
  join comercios c on c.id = cr.comercio_id
 where c.activo and c.ia_analizado_at::date >= :desde
 group by 1 order by 2 desc;

\echo ''
\echo '################ 6. EL DICCIONARIO CRECIÓ SOLO ################'
\echo 'Términos que la IA aportó mirando estas vidrieras. Antes se quedaban en'
\echo 'un comercio; ahora entran al diccionario y sirven para todos los locales'
\echo 'que venden lo mismo.'
select count(*) filter (where creado_at::date >= :desde)    as terminos_agregados_hoy,
       count(*)                                              as terminos_totales,
       count(*) filter (where origen = 'manual')             as corregidos_a_mano
  from producto_sinonimos;

select termino, sinonimos
  from producto_sinonimos
 where creado_at::date >= :desde
 order by termino limit 30;

\echo ''
\echo '################ 7. LO QUE TODAVÍA NO TIENE SINÓNIMOS ################'
\echo 'Vocabulario nuevo sin cubrir. Se llena con:'
\echo '  construir_sinonimos.py con APLICAR=1  (sólo pregunta lo que falta)'
with en_uso as (
  select distinct trim(lower(unaccent(p))) as t
    from comercios c,
         lateral unnest(string_to_array(coalesce(c.prod_det_ia,'') || ',' ||
                                        coalesce(c.subcategoria,''), ',')) as p
   where c.activo and c.ia_analizado_at::date >= :desde and length(trim(p)) >= 3
)
select count(*) as terminos_de_los_nuevos,
       count(*) filter (where exists (
         select 1 from producto_sinonimos ps
          where ps.termino = termino_normalizado(e.t))) as ya_cubiertos
  from en_uso e;

\echo ''
\echo '################ 8. LOS QUE HAY QUE VOLVER A VER ################'
\echo 'Sin nombre, sin productos detectados o sin WhatsApp. Con el código a mano'
\echo 'para buscarlos en el admin.'
select 'URUKU-' || codigo as codigo, left(nombre, 26) as nombre,
       case when nombre ilike 'comercio%' then 'SIN NOMBRE'
            when prod_det_ia is null      then 'foto sin mercaderia'
            else 'sin whatsapp' end       as falta
  from comercios
 where activo and ia_analizado_at::date >= :desde
   and (nombre ilike 'comercio%' or prod_det_ia is null or coalesce(whatsapp,'') = '')
 order by 3, 2;
