-- ¿Quién tiene razón: el informe SQL o el script? Prueba sobre los casos
-- concretos que el informe listó como "alimentos sin respaldo".
--
-- Las dos puntas dicen usar el mismo criterio: pasarle el texto del comercio a
-- rubros_sugeridos() y ver si el rubro asignado aparece. Si el resultado
-- difiere, es que el TEXTO que arma cada una no es el mismo — y esta consulta
-- muestra el texto exacto y lo que devuelve la función.
\pset border 2
select 'URUKU-' || c.codigo                    as codigo,
       left(c.nombre, 18)                      as comercio,
       left(coalesce(c.subcategoria,''), 14)   as subcat,
       ('alimentos' = any (rubros_sugeridos(
          coalesce(c.prod_det_ia,'') || ' ' || coalesce(c.subcategoria,'') || ' ' ||
          coalesce(c.sinonimos,'')   || ' ' || coalesce(c.nombre,''))))  as sugiere_alimentos,
       array_to_string(rubros_sugeridos(
          coalesce(c.prod_det_ia,'') || ' ' || coalesce(c.subcategoria,'') || ' ' ||
          coalesce(c.sinonimos,'')   || ' ' || coalesce(c.nombre,'')), ', ') as sugiere
  from comercios c
 where c.codigo in ('EJD6','6NC8','HNED','6PDX','QKPN','PBG7','FCSZ','RSRU');

\echo ''
\echo 'Y el mismo texto SIN los sinónimos (que es lo único que puede diferir):'
select 'URUKU-' || c.codigo as codigo,
       ('alimentos' = any (rubros_sugeridos(
          coalesce(c.prod_det_ia,'') || ' ' || coalesce(c.subcategoria,'')))) as sin_sinonimos,
       left(coalesce(c.sinonimos,''), 60) as sinonimos
  from comercios c
 where c.codigo in ('EJD6','6NC8','HNED');
