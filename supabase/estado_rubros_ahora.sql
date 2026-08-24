-- ¿Cuántos comercios tienen hoy cada rubro, y cuántos sin respaldo? SÓLO LECTURA.
--
-- El informe del 23/8 encontró 25 comercios con "alimentos" (22 sin respaldo) y
-- 25 con "hogar" (15 sin respaldo). El script de limpieza, con los mismos datos,
-- no encuentra ninguno — y el modo DEBUG mostró por qué: el comercio que el
-- informe listaba con "alimentos" hoy sólo tiene "ropa".
--
-- Algo reescribió las asignaciones en el medio. Antes de tocar nada hay que
-- saber qué quedó: `aplicar_rubros()` usa set_comercio_rubros(), que REEMPLAZA
-- el conjunto entero por lo deducido del texto. Si eso corrió, pudo llevarse
-- puestos rubros correctos junto con los de más.
\pset border 2

\echo ''
\echo 'Asignaciones por rubro, y cuántas no tienen respaldo en los productos:'
with texto as (
  select c.id, coalesce(c.prod_det_ia,'') || ' ' || coalesce(c.subcategoria,'') || ' ' ||
                coalesce(c.sinonimos,'')   || ' ' || coalesce(c.nombre,'') as t
    from comercios c where c.activo
)
select r.slug, left(r.nombre, 24) as rubro,
       count(*) as asignado_a,
       count(*) filter (where not (r.slug = any (rubros_sugeridos(tx.t)))) as sin_respaldo
  from comercio_rubros cr
  join rubros r  on r.id = cr.rubro_id and r.slug <> 'otros'
  join texto tx  on tx.id = cr.comercio_id
 group by 1, 2 order by 3 desc;

\echo ''
\echo 'Total de asignaciones y promedio por comercio (el 23/8: 542 y 2,69):'
select count(*) as asignaciones,
       count(distinct cr.comercio_id) as comercios,
       round(count(*)::numeric / nullif(count(distinct cr.comercio_id), 0), 2) as promedio
  from comercio_rubros cr
  join comercios c on c.id = cr.comercio_id and c.activo
  join rubros r on r.id = cr.rubro_id and r.slug <> 'otros';
