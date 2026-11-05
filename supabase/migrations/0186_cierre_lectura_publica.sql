-- 0186 · Cierre de lectura pública (paso 0 de la revisión de seguridad de noviembre).
--
-- Cuatro cosas, todas para que el navegador (anon / authenticated) vea y pueda hacer
-- menos de lo estrictamente necesario:
--
--  1. TIEMPO MÁXIMO por consulta para anon y authenticated: 3 segundos. Una consulta
--     pública que tarda más se corta sola en vez de ocupar la base. El backend
--     (service_role) no se toca: sus procesos largos siguen igual. PostgREST aplica
--     la configuración del rol en cada pedido.
--
--  2. `leads` y `visitas`: el navegador ya no lee ni inserta ahí. Las escrituras las
--     hace el backend (POST /lead, /visita) con service_role, que tiene sus propios
--     permisos. Ningún código del frontend toca estas tablas directo.
--
--  3. Columnas de `comercios` que el sitio público no usa dejan de ser legibles para
--     anon y authenticated: email, origen_importacion, ia_analizado_at,
--     rubro_revisado_at, sinonimos, subcategoria_norm y busqueda. El backend las
--     sigue leyendo y escribiendo. `buscar_comercios` es SECURITY DEFINER, así que la
--     búsqueda pública sigue usando `busqueda` por dentro sin exponerla.
--     (Regla 11 de AGENTS.md: ningún select del frontend las pide; se sacaron de
--     COLUMNAS_COMERCIO. test_comercios_columnas_publicas.py lo vigila.)
--
--  4. `buscar_comercios`: p_limit <= 0 o nulo ya no significa «sin límite». Devuelve la
--     página normal (24) y el máximo es 500. Es el mismo cuerpo que la 0143; sólo
--     cambia la línea del `limit`.
--
-- Idempotente: se puede correr dos veces. Todo en una transacción y con comprobación:
-- si algo no quedó como se espera, no se aplica nada.
-- Copia idéntica en supabase/migrations/ y selfhost/postgres-init/.

begin;

-- ── 1. Tiempo máximo por consulta ────────────────────────────────────────────
alter role anon          set statement_timeout = '3s';
alter role authenticated set statement_timeout = '3s';

-- ── 2. leads y visitas: sólo el backend ──────────────────────────────────────
revoke insert, select on public.leads    from anon, authenticated;
revoke insert, select on public.visitas  from anon, authenticated;

-- ── 3. Columnas internas de comercios ────────────────────────────────────────
revoke select (email, origen_importacion, ia_analizado_at, rubro_revisado_at,
               sinonimos, subcategoria_norm, busqueda)
  on public.comercios from anon, authenticated;

-- ── 4. buscar_comercios sin «sin límite» ─────────────────────────────────────
create or replace function public.buscar_comercios(
  q text default null, p_rubro text default null, p_modalidad text default null,
  p_zona text default null, p_precio_min numeric default null, p_precio_max numeric default null,
  p_ciudad text default null, p_limit int default 24, p_offset int default 0,
  p_subcategoria text default null
)
returns table (
  id uuid, slug text, nombre text, descripcion text, logo_url text, portada_url text,
  whatsapp text, direccion text, lat double precision, lng double precision, modalidad text,
  rubro_slug text, rubro_nombre text, subcategoria text, zona_nombre text, rating numeric, verificado boolean,
  ofertas bigint, rank real, monedas_aceptadas text[], envios_internacionales boolean,
  tiene_factura boolean, horario text, tiene_stock boolean, ciudad_nombre text, ciudad_pais text,
  prod_obs_human text, prod_det_ia text,
  destacado boolean, plan text, portada_thumb_url text, portada_pos smallint,
  contacto_ok int, contacto_no int,
  total bigint,
  estrella boolean, plan_orden int,
  horario_estimado boolean
)
language sql stable
security definer
set search_path = public, pg_temp
as $$
  with entrada as (
    select
      (now() at time zone 'America/La_Paz')::date as hoy,      -- el «hoy» de Bolivia
      lower(unaccent(coalesce(q, ''))) as texto,
      '\m' || regexp_replace(lower(unaccent(coalesce(q, ''))),
                             '([.^$*+?()\[\]{}|\\-])', '\\\1', 'g') as inicio_palabra,
      websearch_to_tsquery('spanish_unaccent', coalesce(q, '')) as tsq_todas,
      websearch_to_tsquery('spanish_unaccent',
        regexp_replace(btrim(coalesce(q, '')), '\s+', ' or ', 'g')) as tsq_alguna
  ),
  base as (
    select distinct on (c.id)
      c.id, c.slug, c.nombre, c.descripcion, c.logo_url, c.portada_url,
      c.whatsapp, c.direccion, c.lat, c.lng, c.modalidad,
      r.slug as rubro_slug, r.nombre as rubro_nombre, c.subcategoria, z.nombre as zona_nombre,
      c.rating, c.verificado,
      (select count(*) from publicaciones pp
         where pp.comercio_id = c.id and pp.estado = 'aprobado' and pp.activo) as ofertas,
      coalesce(
      q is null or q = ''
       or c.busqueda @@ e.tsq_todas
       or p.busqueda @@ e.tsq_todas
       or lower(unaccent(c.nombre)) ~ e.inicio_palabra
       or exists (
            select 1 from comercio_rubros cr4 join rubros r5 on r5.id = cr4.rubro_id and r5.activo
             where cr4.comercio_id = c.id
               and (to_tsvector('spanish_unaccent', r5.nombre) @@ e.tsq_todas
                    or lower(unaccent(r5.nombre)) ~ e.inicio_palabra))
       or similarity(lower(unaccent(c.nombre)), e.texto) > 0.35
       or similarity(lower(unaccent(coalesce(c.subcategoria, ''))), e.texto) > 0.35
      , false) as fuerte,
      (case when q is null or q = '' then 1.0
            else
              least(ts_rank(c.busqueda, e.tsq_todas) * 4, 1.0)
              + least(ts_rank(c.busqueda, e.tsq_alguna) * 1.5, 0.4)
              + case when lower(unaccent(c.nombre)) ~ e.inicio_palabra then 0.5 else 0 end
              + case when exists (
                  select 1 from comercio_rubros cr3 join rubros r4 on r4.id = cr3.rubro_id and r4.activo
                  where cr3.comercio_id = c.id
                    and (to_tsvector('spanish_unaccent', r4.nombre) @@ e.tsq_todas
                         or lower(unaccent(r4.nombre)) ~ e.inicio_palabra)
                ) then 0.35 else 0 end
              + similarity(lower(unaccent(c.nombre)), e.texto) * 0.3
              + similarity(lower(unaccent(coalesce(c.subcategoria, ''))), e.texto) * 0.25
            end)::real as rank,
      (p_rubro is not null and r.slug = p_rubro) as principal,
      -- Cinco «no me contestó» y ningún «sí»: va al final, no desaparece.
      (coalesce(c.contacto_no, 0) >= 5 and coalesce(c.contacto_ok, 0) = 0) as no_contesta,
      coalesce(c.monedas_aceptadas, '{}') as monedas_aceptadas,
      coalesce(c.envios_internacionales, false) as envios_internacionales,
      coalesce(c.tiene_factura, false) as tiene_factura,
      c.horario, coalesce(c.tiene_stock, true) as tiene_stock,
      ci.nombre as ciudad_nombre, ci.pais as ciudad_pais,
      c.prod_obs_human, c.prod_det_ia,
      coalesce(c.destacado, false) as destacado, coalesce(c.plan, 'gratis') as plan,
      c.portada_thumb_url, c.portada_pos,
      coalesce(c.contacto_ok, 0) as contacto_ok, coalesce(c.contacto_no, 0) as contacto_no,
      coalesce(c.plan_cortesia, false) as plan_cortesia, c.paga_hasta,
      coalesce(c.suspendido, false) as suspendido, e.hoy,
      coalesce(c.horario_estimado, false) as horario_estimado
    from comercios c
    cross join entrada e
    left join rubros r on r.id = c.rubro_id and r.activo
    left join zonas z on z.id = c.zona_id and z.activo
    left join ciudades ci on ci.id = c.ciudad_id
    left join publicaciones p on p.comercio_id = c.id and p.estado = 'aprobado' and p.activo
    where c.activo
      and not coalesce(c.suspendido, false)
      and (p_rubro is null or exists (
        select 1 from comercio_rubros cr join rubros r2 on r2.id = cr.rubro_id and r2.activo
        where cr.comercio_id = c.id and r2.slug = p_rubro))
      and (p_modalidad is null or c.modalidad = p_modalidad)
      and (p_subcategoria is null
           or strip(to_tsvector('spanish_unaccent', coalesce(c.subcategoria, '')))
              = strip(to_tsvector('spanish_unaccent', p_subcategoria)))
      and (p_zona is null or z.slug = p_zona)
      and (p_ciudad is null or ci.slug = p_ciudad)
      and (p_precio_min is null or p.precio is null or p.precio >= p_precio_min)
      and (p_precio_max is null or p.precio is null or p.precio <= p_precio_max)
      and (
        q is null or q = ''
        or c.busqueda @@ e.tsq_alguna
        or p.busqueda @@ e.tsq_alguna
        or lower(unaccent(c.nombre)) ~ e.inicio_palabra
        or exists (
          select 1 from comercio_rubros cr2 join rubros r3 on r3.id = cr2.rubro_id and r3.activo
          where cr2.comercio_id = c.id
            and (to_tsvector('spanish_unaccent', r3.nombre) @@ e.tsq_todas
                 or lower(unaccent(r3.nombre)) ~ e.inicio_palabra))
        or similarity(lower(unaccent(c.nombre)), e.texto) > 0.35
        or similarity(lower(unaccent(coalesce(c.subcategoria, ''))), e.texto) > 0.35
      )
    order by c.id, fuerte desc, rank desc
  ),
  medidos as (
    select b.*, sum(case when b.fuerte then 1 else 0 end) over () as n_fuertes from base b
  ),
  filtrados as (
    select * from medidos where coalesce(n_fuertes, 0) < 5 or fuerte
  ),
  -- El orden del plan se calcula SOLO para los que quedaron (no por cada fila de
  -- la unión con publicaciones), y `planes_orden()` se une UNA vez: el ranking de
  -- precios no se recalcula por comercio. «Al día» = cortesía, o paga_hasta de hoy
  -- (Bolivia) en adelante; suspendido = sin estrella, también la cortesía. Es la
  -- misma regla de `plan_orden_de`. Ningún precio sale de acá.
  con_plan as (
    select f.*,
           case when f.suspendido
                  or not (f.plan_cortesia or (f.paga_hasta is not null and f.paga_hasta >= f.hoy))
                then 0
                else coalesce(po.orden, 0)
           end as plan_orden
      from filtrados f
      left join public.planes_orden() po on po.slug = f.plan
  )
  select id, slug, nombre, descripcion, logo_url, portada_url, whatsapp, direccion,
         lat, lng, modalidad, rubro_slug, rubro_nombre, subcategoria, zona_nombre, rating, verificado,
         ofertas, rank, monedas_aceptadas, envios_internacionales, tiene_factura,
         horario, tiene_stock, ciudad_nombre, ciudad_pais,
         prod_obs_human, prod_det_ia,
         destacado, plan, portada_thumb_url, portada_pos,
         contacto_ok, contacto_no,
         count(*) over () as total,
         (plan_orden > 0) as estrella, plan_orden,
         horario_estimado
    from con_plan order by rank desc, plan_orden desc, principal desc, no_contesta asc, nombre, id
   -- Sin límite NO existe: 0, negativo o nulo = la página normal (24); el tope es 500
   -- (el mapa pide de a 500 con p_offset).
   limit greatest(1, least(case when coalesce(p_limit, 0) <= 0 then 24 else p_limit end, 500))
  offset greatest(0, p_offset);
$$;

revoke execute on function public.buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text) from public;
grant  execute on function public.buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text)
  to anon, authenticated, service_role;

-- ── Comprobación ─────────────────────────────────────────────────────────────
do $chk$
declare
  v_rol text;
  v_col text;
  v_n   bigint;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    -- tiempo máximo
    if not exists (select 1 from pg_roles r
                    where r.rolname = v_rol and 'statement_timeout=3s' = any (r.rolconfig)) then
      raise exception '0186: % no tiene statement_timeout=3s', v_rol;
    end if;
    -- leads y visitas cerradas
    if has_table_privilege(v_rol, 'public.leads', 'insert') or has_table_privilege(v_rol, 'public.leads', 'select')
       or has_table_privilege(v_rol, 'public.visitas', 'insert') or has_table_privilege(v_rol, 'public.visitas', 'select') then
      raise exception '0186: % todavía toca leads o visitas', v_rol;
    end if;
    -- columnas internas cerradas
    foreach v_col in array array['email', 'origen_importacion', 'ia_analizado_at', 'rubro_revisado_at',
                                 'sinonimos', 'subcategoria_norm', 'busqueda'] loop
      if has_column_privilege(v_rol, 'public.comercios', v_col, 'select') then
        raise exception '0186: % todavía puede leer comercios.%', v_rol, v_col;
      end if;
    end loop;
    -- lo público sigue abierto (ficha, buscador, mapa)
    foreach v_col in array array['id', 'slug', 'nombre', 'activo', 'plan', 'suspendido', 'horario',
                                 'lat', 'lng', 'whatsapp', 'telefono', 'descripcion', 'subcategoria'] loop
      if not has_column_privilege(v_rol, 'public.comercios', v_col, 'select') then
        raise exception '0186: % no puede leer comercios.%', v_rol, v_col;
      end if;
    end loop;
  end loop;

  -- el backend sigue escribiendo
  if not has_table_privilege('service_role', 'public.leads', 'insert')
     or not has_table_privilege('service_role', 'public.visitas', 'insert') then
    raise exception '0186: service_role perdió el acceso a leads o visitas';
  end if;
  foreach v_col in array array['email', 'busqueda', 'sinonimos'] loop
    if not has_column_privilege('service_role', 'public.comercios', v_col, 'select') then
      raise exception '0186: service_role no puede leer comercios.%', v_col;
    end if;
  end loop;

  -- buscar_comercios: ni 0, ni negativo, ni nulo, ni un número enorme devuelven más de lo permitido
  select count(*) into v_n from public.buscar_comercios(p_limit => 0);
  if v_n > 24 then raise exception '0186: buscar_comercios(p_limit=0) devolvió % filas', v_n; end if;
  select count(*) into v_n from public.buscar_comercios(p_limit => -5);
  if v_n > 24 then raise exception '0186: buscar_comercios(p_limit=-5) devolvió % filas', v_n; end if;
  select count(*) into v_n from public.buscar_comercios(p_limit => null);
  if v_n > 24 then raise exception '0186: buscar_comercios(p_limit=null) devolvió % filas', v_n; end if;
  select count(*) into v_n from public.buscar_comercios(p_limit => 100000);
  if v_n > 500 then raise exception '0186: buscar_comercios(p_limit=100000) devolvió % filas', v_n; end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
