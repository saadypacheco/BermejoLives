-- 0180 · city_category_pages(): los pares ciudad + rubro con comercios.
--
-- Fuente de las páginas /{ciudad}/{rubro} y del sitemap (docs/visibilidad-buscadores-ia.md,
-- §3.1 y §3.2). Devuelve UN BOOLEANO (`indexable`) y NUNCA el conteo: la cantidad de
-- comercios no sale al público (regla de producto).
--
-- Qué entra:
--   · ciudades activas (`ciudades.activa`)
--   · rubros activos y distintos de `otros` (el rubro sale de `comercio_rubros`, que
--     incluye el principal, 0113)
--   · comercios activos y no suspendidos (mismo filtro que `buscar_comercios`, 0143)
--   · el par aparece si tiene al menos 1 comercio así.
--
-- `indexable` = al menos 5 comercios DISTINTOS que NO sean «finos». La regla de
-- «fino» es la misma de §3.1 (`isBusinessThin` en frontend/lib/seo.ts): rubro principal
-- vacío u `otros` y sin subcategoría, descripción, productos observados ni detectados
-- por IA; o el nombre dice «a clasificar».
--
-- SECURITY INVOKER: corre con los permisos y el RLS de anon. Todas las columnas de
-- `comercios` que lee (id, ciudad_id, rubro_id, activo, suspendido, nombre, subcategoria,
-- descripcion, prod_obs_human, prod_det_ia, updated_at) tienen `grant select` por
-- columna desde la 0145, así que no hace falta SECURITY DEFINER ni toca las privadas.
-- No agrega columnas a `comercios`: no afecta test_comercios_columnas_publicas.py.
--
-- Idempotente: se puede correr dos veces.

create or replace function public.city_category_pages()
returns table (
  city_slug text,
  city_name text,
  region text,                 -- ciudades.departamento
  category_slug text,
  category_name text,
  indexable boolean,           -- 5 o más comercios no finos
  last_modified timestamptz    -- max(comercios.updated_at) del par
)
language sql
stable
security invoker
set search_path = public, pg_temp
as $fn$
  select ci.slug::text,
         ci.nombre::text,
         ci.departamento::text,
         ru.slug::text,
         ru.nombre::text,
         (count(distinct c.id) filter (where not (
              ( (rp.slug is null or rp.slug = 'otros')
                and btrim(coalesce(c.subcategoria, '')) = ''
                and btrim(coalesce(c.descripcion, '')) = ''
                and btrim(coalesce(c.prod_obs_human, '')) = ''
                and btrim(coalesce(c.prod_det_ia, '')) = '' )
              or c.nombre ~* 'a clasificar'
         ))) >= 5,
         max(c.updated_at)
    from public.comercios c
    join public.ciudades ci on ci.id = c.ciudad_id and ci.activa
    join public.comercio_rubros cr on cr.comercio_id = c.id
    join public.rubros ru on ru.id = cr.rubro_id and ru.activo and ru.slug <> 'otros'
    left join public.rubros rp on rp.id = c.rubro_id and rp.activo
   where c.activo
     and not coalesce(c.suspendido, false)
   group by ci.slug, ci.nombre, ci.departamento, ru.slug, ru.nombre
  having count(distinct c.id) >= 1
$fn$;

comment on function public.city_category_pages() is
  'Pares ciudad+rubro con comercios activos (ciudades y rubros activos, sin otros, sin suspendidos). indexable = 5 o más comercios no finos (§3.1). No devuelve el conteo: el número no sale al público.';

revoke execute on function public.city_category_pages() from public;
grant  execute on function public.city_category_pages() to anon, authenticated, service_role;

notify pgrst, 'reload schema';
