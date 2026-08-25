-- Los rubros, con cuántos comercios tiene cada uno. SÓLO LECTURA.
--
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U postgres -d postgres -f - < supabase/rubros_y_conteo.sql
--
-- Lo mismo que muestra Admin › Catálogo, para cuando se lo quiere en la
-- terminal o pegar en un informe.
--
-- Un rubro vacío no es necesariamente un error: puede ser una categoría que
-- todavía no se salió a cargar. Pero un rubro vacío y ACTIVO sí es un problema
-- visible — aparece como chip en el buscador y en el mapa, alguien lo toca, y
-- no devuelve nada. Es la peor forma de no encontrar algo: parecía que había.

\pset border 2
\pset pager off

\echo ''
\echo '################ TODOS LOS RUBROS ################'
select case when r.activo then '' else 'apagado' end          as estado,
       r.slug,
       r.nombre,
       count(distinct c.id)                                    as comercios
  from rubros r
  left join comercio_rubros cr on cr.rubro_id = r.id
  left join comercios c        on c.id = cr.comercio_id and c.activo
 group by 1, 2, 3
 order by 4 desc, r.nombre;

\echo ''
\echo '################ LOS VACÍOS Y ENCENDIDOS ################'
\echo 'Estos son los que salen como chip y no devuelven nada. Cada uno es un'
\echo 'filtro que promete y no cumple: o se cargan comercios, o se apaga.'
select r.slug, r.nombre
  from rubros r
 where r.activo
   and not exists (
     select 1 from comercio_rubros cr
       join comercios c on c.id = cr.comercio_id and c.activo
      where cr.rubro_id = r.id)
 order by r.nombre;

\echo ''
\echo '################ EL RESUMEN ################'
with n as (
  select r.id, r.activo, count(distinct c.id) as comercios
    from rubros r
    left join comercio_rubros cr on cr.rubro_id = r.id
    left join comercios c        on c.id = cr.comercio_id and c.activo
   group by 1, 2
)
select count(*)                                          as rubros_en_total,
       count(*) filter (where activo)                    as activos,
       count(*) filter (where not activo)                as apagados,
       count(*) filter (where activo and comercios = 0)  as activos_y_vacios,
       count(*) filter (where comercios > 0)             as con_al_menos_uno
  from n;
