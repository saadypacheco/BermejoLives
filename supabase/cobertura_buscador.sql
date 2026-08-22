-- ¿El comprador encuentra lo que la IA vio en las fotos? SÓLO LECTURA.
--
--   cd /docker/uruku
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U postgres -d postgres -f - < supabase/cobertura_buscador.sql
--
-- Dos preguntas distintas, en ese orden:
--
--   1. ¿Cuánto vocabulario salió de las imágenes? (rubros, subcategorías,
--      productos, sinónimos)
--   2. De ese vocabulario, ¿cuánto es realmente buscable? Para cada término se
--      compara lo que el buscador devuelve contra los comercios que de verdad
--      lo tienen. La diferencia es lo que el comprador NO encuentra.
--
-- El punto 2 es el que importa: tener el dato cargado y que el buscador no lo
-- devuelva es exactamente igual a no tenerlo.

\pset border 2

\echo ''
\echo '################ 1. QUÉ SALIÓ DE LAS IMÁGENES ################'
select
  count(*) filter (where activo)                                as comercios,
  count(*) filter (where activo and ia_analizado_at is not null) as analizados,
  count(distinct subcategoria)      filter (where activo)       as subcat_escritas,
  count(distinct subcategoria_norm) filter (where activo)       as subcat_reales,
  count(*) filter (where activo and coalesce(sinonimos,'') <> '') as con_sinonimos,
  (select count(distinct rubro_id) from comercio_rubros)        as rubros_en_uso,
  (select count(*) from rubros)                                 as rubros_totales
from comercios;

\echo ''
\echo 'La diferencia entre subcat_escritas y subcat_reales es la fragmentación:'
\echo 'cuántas categorías creíamos tener de más por escribirlas distinto.'

\echo ''
\echo '################ 2. FRAGMENTACIÓN: VARIANTES DE LO MISMO ################'
select subcategoria_norm                       as categoria_real,
       count(*)                                as comercios,
       string_agg(distinct subcategoria, ' | ') as se_escribio_como
  from comercios
 where activo and coalesce(subcategoria_norm,'') <> ''
 group by 1 having count(distinct subcategoria) > 1
 order by 2 desc;

\echo ''
\echo '################ 3. COBERTURA POR RUBRO ################'
\echo 'tiene   = comercios con ese rubro en comercio_rubros (la verdad)'
\echo 'encuentra = los que devuelve el buscador escribiendo el nombre del rubro'
\echo 'Si encuentra < tiene, hay comercios cargados que el comprador no ve.'
with reales as (
  select r.id, r.nombre,
         -- Se busca por la palabra sola, sin el emoji ni el "y construcción":
         -- es lo que la gente escribe de verdad.
         lower(unaccent(split_part(regexp_replace(r.nombre, '[^[:alnum:] áéíóúñÁÉÍÓÚÑ]', '', 'g'), ' y ', 1))) as termino,
         count(cr.comercio_id) as tiene
    from rubros r
    join comercio_rubros cr on cr.rubro_id = r.id
    join comercios c on c.id = cr.comercio_id and c.activo
   group by 1, 2, 3
)
select re.nombre                        as rubro,
       re.termino                       as se_busca_como,
       re.tiene,
       b.encuentra,
       case when b.encuentra >= re.tiene then 'ok'
            when b.encuentra = 0        then 'NO ENCUENTRA NADA'
            else 'incompleto' end       as estado
  from reales re
  cross join lateral (
    select count(*) as encuentra
      from buscar_comercios(trim(re.termino), null,null,null,null,null,null, 60, 0)
  ) b
 where re.tiene > 0
 order by (b.encuentra < re.tiene) desc, re.tiene desc;

\echo ''
\echo '################ 4. COBERTURA POR SUBCATEGORÍA ################'
\echo 'Lo mismo, pero con las palabras que escribió la IA mirando las vidrieras.'
\echo 'Estas son las búsquedas más probables: nadie busca "Moda y ropa", buscan'
\echo '"zapatillas".'
with subs as (
  select subcategoria_norm as termino, count(*) as tiene
    from comercios
   where activo and coalesce(subcategoria_norm,'') <> ''
   group by 1
)
select s.termino, s.tiene, b.encuentra,
       case when b.encuentra >= s.tiene then 'ok'
            when b.encuentra = 0        then 'NO ENCUENTRA NADA'
            else 'incompleto' end as estado
  from subs s
  cross join lateral (
    select count(*) as encuentra
      from buscar_comercios(s.termino, null,null,null,null,null,null, 60, 0)
  ) b
 order by (b.encuentra < s.tiene) desc, s.tiene desc
 limit 60;

\echo ''
\echo '################ 5. COBERTURA POR PRODUCTO SUELTO ################'
\echo 'Se parten los productos que detectó la IA y se busca cada uno por'
\echo 'separado. Un producto que nadie encuentra es una venta perdida concreta.'
with productos as (
  select trim(lower(unaccent(p))) as producto, count(*) as tiene
    from comercios c,
         lateral unnest(string_to_array(coalesce(c.prod_det_ia,''), ',')) as p
   where c.activo and trim(p) <> ''
   group by 1
  having count(*) >= 2
)
select pr.producto, pr.tiene, b.encuentra,
       case when b.encuentra >= pr.tiene then 'ok'
            when b.encuentra = 0        then 'NO ENCUENTRA NADA'
            else 'incompleto' end as estado
  from productos pr
  cross join lateral (
    select count(*) as encuentra
      from buscar_comercios(pr.producto, null,null,null,null,null,null, 60, 0)
  ) b
 order by (b.encuentra < pr.tiene) desc, pr.tiene desc
 limit 60;

\echo ''
\echo '################ 6. PRUEBA DE TOLERANCIA A ERRORES ################'
\echo 'Escrito mal a propósito. Antes de pg_trgm esto daba cero.'
\echo ''
\echo '--- ferreteia (falta la r) ---'
select nombre, round(rank::numeric,3) as rank
  from buscar_comercios('ferreteia', null,null,null,null,null,null, 3, 0);
\echo '--- jugeteria (falta la u) ---'
select nombre, round(rank::numeric,3) as rank
  from buscar_comercios('jugeteria', null,null,null,null,null,null, 3, 0);
\echo '--- zapatiyas (con y) ---'
select nombre, round(rank::numeric,3) as rank
  from buscar_comercios('zapatiyas', null,null,null,null,null,null, 3, 0);

\echo ''
\echo '################ 7. PRUEBA DE SINÓNIMOS ################'
\echo 'Vocabulario argentino contra vocabulario boliviano: las dos formas'
\echo 'tienen que devolver lo mismo. Si una da cero, el sinónimo no se cargó.'
\echo ''
\echo '--- remera / polera / camiseta ---'
select 'remera' as q, count(*) from buscar_comercios('remera',null,null,null,null,null,null,60,0)
union all select 'polera',   count(*) from buscar_comercios('polera',null,null,null,null,null,null,60,0)
union all select 'camiseta', count(*) from buscar_comercios('camiseta',null,null,null,null,null,null,60,0);
\echo '--- zapatilla / tenis / championes ---'
select 'zapatilla' as q, count(*) from buscar_comercios('zapatilla',null,null,null,null,null,null,60,0)
union all select 'tenis',      count(*) from buscar_comercios('tenis',null,null,null,null,null,null,60,0)
union all select 'championes', count(*) from buscar_comercios('championes',null,null,null,null,null,null,60,0);
\echo '--- campera / casaca / chamarra ---'
select 'campera' as q, count(*) from buscar_comercios('campera',null,null,null,null,null,null,60,0)
union all select 'casaca',   count(*) from buscar_comercios('casaca',null,null,null,null,null,null,60,0)
union all select 'chamarra', count(*) from buscar_comercios('chamarra',null,null,null,null,null,null,60,0);

\echo ''
\echo '################ 8. RANKING: EL PRIMERO IMPORTA ################'
\echo 'Encontrar no alcanza si el resultado correcto sale sexto. Rank 0.000 en'
\echo 'la primera fila significa que el orden quedó alfabético.'
\echo ''
\echo '--- ferreteria ---'
select nombre, round(rank::numeric,3) as rank
  from buscar_comercios('ferreteria', null,null,null,null,null,null, 5, 0);
\echo '--- ropa deportiva ---'
select nombre, round(rank::numeric,3) as rank
  from buscar_comercios('ropa deportiva', null,null,null,null,null,null, 5, 0);
