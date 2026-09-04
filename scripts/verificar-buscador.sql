-- Verificador del buscador: qué palabra trae cuánto.
--
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U postgres -d postgres -f - < scripts/verificar-buscador.sql
--
-- POR QUÉ ESTAS PALABRAS Y NO UNA LISTA INVENTADA
-- ==============================================
-- Se prueban tres vocabularios distintos, y cada uno responde otra pregunta:
--
--   BÚSQUEDA REAL   lo que la gente efectivamente escribió (tabla `busquedas`).
--                   Es el único que dice qué se busca de verdad en Bermejo.
--   RUBRO           el nombre de cada rubro. Si "Rotisería y comida rápida" trae
--                   3 comercios, el rubro está vacío, no el buscador.
--   DICCIONARIO     cada palabra de `rubro_palabras`. Una palabra que no trae
--                   nada es vocabulario que no clasificó a nadie: o nadie vende
--                   eso en la ciudad, o está mal escrita.
--
-- CÓMO LEER EL RESULTADO
-- ======================
-- Un cero puede ser tres cosas MUY distintas, y confundirlas hace perder el día:
--
--   1. Nadie vende eso en Bermejo            → está bien, no se toca.
--   2. Hay comercios pero no están clasificados → falta correr la revisión de
--      rubros; el buscador funciona.
--   3. El buscador no llega                  → ahí sí hay que mirar el código.
--
-- El bloque 2 separa el caso 2 del 3: compara lo que trae el buscador contra
-- cuántos comercios tienen ese rubro asignado. Si el rubro tiene 40 comercios y
-- la búsqueda por su nombre trae 3, el problema es el buscador. Si el rubro
-- tiene 3, el problema es la clasificación.

\timing off
\pset pager off

-- ── 1) Lo que la gente buscó de verdad, y qué encontró ───────────────────────
\echo ''
\echo '=== BUSQUEDAS REALES QUE NO ENCONTRARON NADA ==='
\echo '(las que más se repiten primero: es la lista de qué falta en la ciudad)'
with reales as (
  select lower(btrim(query)) as termino, count(*) as veces
    from busquedas
   where btrim(coalesce(query, '')) <> ''
   group by 1
)
select r.termino, r.veces as "veces buscada", coalesce(b.total, 0) as resultados
  from reales r
  left join lateral (select total from buscar_comercios(r.termino, p_limit => 1) limit 1) b on true
 where coalesce(b.total, 0) = 0
 order by r.veces desc, r.termino
 limit 40;

\echo ''
\echo '=== BUSQUEDAS REALES CON POCOS RESULTADOS (1 a 3) ==='
with reales as (
  select lower(btrim(query)) as termino, count(*) as veces
    from busquedas
   where btrim(coalesce(query, '')) <> ''
   group by 1
)
select r.termino, r.veces as "veces buscada", coalesce(b.total, 0) as resultados
  from reales r
  left join lateral (select total from buscar_comercios(r.termino, p_limit => 1) limit 1) b on true
 where coalesce(b.total, 0) between 1 and 3
 order by r.veces desc, r.termino
 limit 40;

-- ── 2) Cada rubro: lo que trae el buscador vs. lo que tiene asignado ─────────
\echo ''
\echo '=== RUBRO POR RUBRO: BUSCADOR vs. COMERCIOS ASIGNADOS ==='
\echo '(si asignados >> buscador, el problema es el BUSCADOR)'
\echo '(si asignados es chico, el problema es la CLASIFICACION)'
with r as (
  select rb.slug, rb.nombre,
         -- El nombre sin el emoji ni la coletilla: "🍔 Rotisería y comida
         -- rápida" se busca como "roticeria"… no: como lo escribiría alguien.
         btrim(regexp_replace(rb.nombre, '[^[:alpha:] ]', '', 'g')) as texto,
         (select count(*) from comercio_rubros cr
            join comercios c on c.id = cr.comercio_id
           where cr.rubro_id = rb.id and c.activo) as asignados
    from rubros rb
   where rb.activo
)
select r.nombre, r.asignados,
       coalesce(b.total, 0) as "trae el buscador"
  from r
  left join lateral (select total from buscar_comercios(r.texto, p_limit => 1) limit 1) b on true
 order by r.asignados desc;

-- ── 3) El diccionario entero, las peores primero ────────────────────────────
\echo ''
\echo '=== PALABRAS DEL DICCIONARIO QUE NO TRAEN NADA ==='
\echo '(vocabulario que no clasifico a nadie: o no existe en Bermejo, o esta mal escrito)'
with palabras as (
  select distinct rp.rubro_slug,
         btrim(x) as termino
    from rubro_palabras rp,
         unnest(string_to_array(
           regexp_replace(rp.patron, '^\\m\(|\)$', '', 'g'), '|')) as x
   where btrim(x) <> ''
)
select p.rubro_slug, p.termino, coalesce(b.total, 0) as resultados
  from palabras p
  left join lateral (select total from buscar_comercios(p.termino, p_limit => 1) limit 1) b on true
 where coalesce(b.total, 0) = 0
 order by p.rubro_slug, p.termino;

\echo ''
\echo '=== RESUMEN ==='
select
  (select count(*) from comercios where activo) as "comercios activos",
  (select count(distinct query) from busquedas) as "terminos buscados",
  (select count(*) from rubro_palabras) as "patrones en el diccionario",
  (select count(*) from rubros where activo) as "rubros activos";
