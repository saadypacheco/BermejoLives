-- Cerca de mí con abiertos, el orden por plan y la estrella (docs/cerca-abiertos-estrella.md).
--
-- 1. `comercios.plan_cortesia`: el admin puede poner a un comercio en un plan sin
--    cobro y sin vencimiento (gente que ayuda a URUKU). Tiene estrella, nunca
--    vence y no cuenta como «por vencer» en el tablero ni en Suscripciones.
--
-- 2. Reglas (el «hoy» es el de Bolivia, no el del servidor):
--      plan pago  = el plan tiene precio_mes > 0 en `planes`
--      al día     = plan_cortesia  OR  (paga_hasta >= hoy  AND  NOT suspendido)
--      estrella   = plan pago  AND  al día
--      plan_orden = 0 si no hay estrella; si hay, 1..n según el precio del plan
--                   (más caro = número más alto; planes de igual precio empatan)
--
-- 3. NINGÚN precio llega al público (decisión del 4/10, migración 0134: anon no
--    tiene permiso sobre `planes.precio_mes`). Por eso el cálculo vive en
--    `planes_orden()`, una función SECURITY DEFINER con search_path fijo que sólo
--    devuelve (slug, orden) de los planes pagos, nunca el precio. `plan_orden_de`
--    y `plan_publico` se apoyan en ella.
--
-- 4. `buscar_comercios` devuelve además `estrella`, `plan_orden` y
--    `horario_estimado` (al final del `returns table`; los parámetros y las demás
--    columnas no cambian) y ordena: relevancia, después plan_orden desc, después
--    lo de siempre. Une `planes_orden()` UNA vez (no calcula el ranking por fila)
--    y resuelve el «al día» en línea con la misma regla.
--    Es SECURITY DEFINER desde acá: la 0145 le saca al público el permiso de leer
--    `plan_cortesia` y `paga_hasta`, y la función los necesita. Como un definer
--    se salta las políticas RLS, repite a mano lo que el público veía: sólo
--    comercios activos, sólo rubros y zonas activos, sólo publicaciones aprobadas
--    y activas. Devuelve las mismas columnas públicas de siempre.
--
-- 5. `plan_publico(p_comercio)` para la ficha: la estrella y el orden de UN
--    comercio activo, sin precios. Si el comercio no existe o está dado de baja
--    no devuelve filas.
--
-- 6. `admin_resumen` (0139) deja de contar a los de cortesía como suscripción
--    por vencer.
--
-- Idempotente: se puede correr dos veces.

alter table comercios add column if not exists plan_cortesia boolean not null default false;
comment on column comercios.plan_cortesia is
  'Plan de cortesía: el comercio tiene su plan sin pagar y sin vencimiento (personas que ayudan a URUKU). Tiene estrella, no cuenta en cobros ni en suscripciones por vencer. Lo marca el admin (PUT /admin/comercio/{id}/plan).';

-- ----------------------------------------------------------- planes_orden
-- (slug, orden) de los planes PAGOS: orden = dense_rank del precio (más caro =
-- número más alto; mismo precio, mismo número). Sin precios en la salida.
-- SECURITY DEFINER para poder leer `precio_mes`, que el público no puede leer;
-- search_path fijo para que nadie pueda esconder una tabla falsa en otro esquema.
create or replace function public.planes_orden()
returns table (slug text, orden int)
language sql
stable
security definer
set search_path = public, pg_temp
as $fn$
  select pl.slug, (dense_rank() over (order by pl.precio_mes))::int
    from public.planes pl
   where pl.precio_mes > 0
$fn$;

comment on function public.planes_orden() is
  'Orden de los planes pagos (1 = el más barato). No devuelve precios.';

revoke execute on function public.planes_orden() from public;
grant  execute on function public.planes_orden() to anon, authenticated, service_role;

-- ----------------------------------------------------------- plan_orden_de
-- Una sola fila (la ficha). La búsqueda NO la usa: une `planes_orden()` una vez.
create or replace function public.plan_orden_de(
  p_plan text, p_cortesia boolean, p_paga_hasta date, p_suspendido boolean
) returns int
language sql
stable
security definer
set search_path = public, pg_temp
as $fn$
  -- Suspendido = sin estrella, también la cortesía: si URUKU lo suspendió, la
  -- ficha no puede seguir diciendo «Verificado por URUKU».
  select case
    when coalesce(p_suspendido, false)
      or not (coalesce(p_cortesia, false)
              or (p_paga_hasta is not null
                  and p_paga_hasta >= (now() at time zone 'America/La_Paz')::date))
      then 0
    else coalesce((select po.orden from public.planes_orden() po where po.slug = p_plan), 0)
  end
$fn$;

comment on function public.plan_orden_de(text, boolean, date, boolean) is
  '0 = sin estrella (plan gratis, o pago vencido/suspendido); mayor = plan más caro. No devuelve precios.';

revoke execute on function public.plan_orden_de(text, boolean, date, boolean) from public;
grant  execute on function public.plan_orden_de(text, boolean, date, boolean) to anon, authenticated, service_role;

-- ------------------------------------------------------------ plan_publico
create or replace function public.plan_publico(p_comercio uuid)
returns table (estrella boolean, plan_orden int)
language sql
stable
security definer
set search_path = public, pg_temp
as $fn$
  select x.o > 0, x.o
    from (select public.plan_orden_de(c.plan, c.plan_cortesia, c.paga_hasta, c.suspendido) as o
            from public.comercios c
           where c.id = p_comercio and c.activo) x
$fn$;

comment on function public.plan_publico(uuid) is
  'La estrella «Verificado por URUKU» y el orden del plan de un comercio, para la ficha. Sin precios.';

revoke execute on function public.plan_publico(uuid) from public;
grant  execute on function public.plan_publico(uuid) to anon, authenticated, service_role;

-- ------------------------------------------------------- buscar_comercios
-- Devuelve tres columnas más (estrella, plan_orden, horario_estimado): cambia el
-- tipo de retorno y hay que tirar la función antes. Mismo cuerpo que la 0120 más
-- el orden por plan.
drop function if exists buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text);

create function buscar_comercios(
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
   limit case when p_limit <= 0 then null else greatest(1, least(p_limit, 500)) end
  offset greatest(0, p_offset);
$$;

revoke execute on function buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text) from public;
grant  execute on function buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text)
  to anon, authenticated, service_role;

-- ------------------------------------------------------------ admin_resumen
-- Mismo cuerpo que la 0139; cambia sólo la cuenta de suscripciones por vencer.
create or replace function public.admin_resumen(
  p_ciudad_slug text default null,
  p_hoy date default null
) returns jsonb
language plpgsql
stable
set search_path = public
as $fn$
declare
  v_hoy        date := coalesce(p_hoy, (now() at time zone 'America/La_Paz')::date);
  v_filtra     boolean := p_ciudad_slug is not null and btrim(p_ciudad_slug) <> '';
  v_ciudad_id  uuid;
  -- Ventanas, en días de Bolivia. Inclusivas: «7 días» es hoy y los 6 anteriores.
  v_desde_7    date := v_hoy - 6;
  v_desde_30   date := v_hoy - 29;
  -- Los mismos límites como instantes (inicio del día de Bolivia), para que los
  -- filtros por created_at puedan usar el índice.
  v_ts_desde   timestamptz := (v_hoy - 29)::timestamp at time zone 'America/La_Paz';
  v_ts_hasta   timestamptz := (v_hoy + 1)::timestamp at time zone 'America/La_Paz';

  v_comercios  jsonb;
  v_por_ciudad jsonb;
  v_sin_verificar integer;

  v_pub        integer;
  v_pagos      integer;
  v_reclamos   integer;
  v_cambio     integer;
  v_susc       integer;
  v_recepcion  integer;

  v_visitas_7d  integer;
  v_contactos_7d integer;
  v_serie      jsonb;
begin
  if v_filtra then
    select id into v_ciudad_id from ciudades where slug = btrim(p_ciudad_slug);
    -- Slug desconocido: v_ciudad_id queda null y `ciudad_id = null` no es
    -- verdadero para nadie, así que todo da 0.
  end if;

  -- ── Comercios activos (de la ciudad pedida, o todos) ──────────────────────
  -- Sin rubro = sin rubro principal, o con el comodín «otros». El horario
  -- estimado (puesto por calle) cuenta como CON horario: `sin_horario` mira sólo
  -- que `horario` esté vacío.
  select jsonb_build_object(
           'total',             count(*),
           'verificados',       count(*) filter (where c.verificado),
           'sin_verificar',     count(*) filter (where not c.verificado),
           'sin_horario',       count(*) filter (where coalesce(btrim(c.horario), '') = ''),
           'horario_estimado',  count(*) filter (where c.horario_estimado),
           'sin_whatsapp',      count(*) filter (where coalesce(btrim(c.whatsapp), '') = ''),
           'sin_foto',          count(*) filter (where coalesce(btrim(c.portada_url), '') = ''),
           'sin_rubro',         count(*) filter (where c.rubro_id is null or r.slug = 'otros')
         ),
         (count(*) filter (where not c.verificado))::integer
    into v_comercios, v_sin_verificar
    from comercios c
    left join rubros r on r.id = c.rubro_id
   where c.activo
     and (not v_filtra or c.ciudad_id = v_ciudad_id);

  -- ── Todas las ciudades activas, siempre (no depende de p_ciudad_slug) ─────
  select coalesce(jsonb_agg(jsonb_build_object(
           'slug', t.slug, 'nombre', t.nombre, 'total', t.total,
           'sin_verificar', t.sin_verificar, 'sin_horario', t.sin_horario
         ) order by t.orden, t.nombre), '[]'::jsonb)
    into v_por_ciudad
    from (
      select ci.slug, ci.nombre, ci.orden,
             count(c.id)::integer as total,
             (count(c.id) filter (where not c.verificado))::integer as sin_verificar,
             (count(c.id) filter (where coalesce(btrim(c.horario), '') = ''))::integer as sin_horario
        from ciudades ci
        left join comercios c on c.ciudad_id = ci.id and c.activo
       where ci.activa
       group by ci.id, ci.slug, ci.nombre, ci.orden
    ) t;

  -- ── Pendientes: cada uno en su bloque ─────────────────────────────────────
  -- Publicaciones por moderar (lo que lista /moderacion/publicaciones, sin su tope de 200).
  begin
    select count(*)::integer into v_pub
      from publicaciones where activo and estado = 'pendiente';
  exception when others then
    v_pub := null; raise warning 'admin_resumen: publicaciones: %', sqlerrm;
  end;

  -- Pagos por confirmar (/admin/pagos/pendientes).
  begin
    select count(*)::integer into v_pagos from pagos where estado = 'pendiente';
  exception when others then
    v_pagos := null; raise warning 'admin_resumen: pagos: %', sqlerrm;
  end;

  -- Reclamos sin responder (/admin/reclamos). Las consultas de Reservalo las suma el backend.
  begin
    select count(*)::integer into v_reclamos from reclamos where estado = 'pendiente';
  exception when others then
    v_reclamos := null; raise warning 'admin_resumen: reclamos: %', sqlerrm;
  end;

  -- Cambios de número sin resolver (/admin/solicitudes-cambio-numero).
  begin
    select count(*)::integer into v_cambio
      from solicitudes_cambio_numero where estado = 'pendiente';
  exception when others then
    v_cambio := null; raise warning 'admin_resumen: cambio_numero: %', sqlerrm;
  end;

  -- Suscripciones por vencer + vencidas + suspendidas (/admin/suscripciones, sin
  -- su tope de 500). Misma regla: suspendido; o paga_hasta ya pasó (vencido); o
  -- vence dentro de 5 días (por vencer). Sin paga_hasta = sin plan: no cuenta.
  -- Los de cortesía (0143) no pagan ni vencen: sólo cuentan si están suspendidos.
  begin
    select count(*)::integer into v_susc
      from comercios c
     where c.activo
       and (c.suspendido
            or (not c.plan_cortesia and c.paga_hasta is not null and c.paga_hasta <= v_hoy + 5));
  exception when others then
    v_susc := null; raise warning 'admin_resumen: suscripciones: %', sqlerrm;
  end;

  -- Mensajes de Recepción sin comercio, últimos 7 días (/admin/whatsapp/entrantes).
  begin
    select count(*)::integer into v_recepcion
      from wa_inbox
     where resultado = 'sin_comercio'
       and created_at >= (v_desde_7::timestamp at time zone 'America/La_Paz');  -- días de Bolivia, como visitas y contactos
  exception when others then
    v_recepcion := null; raise warning 'admin_resumen: recepcion_sin_comercio: %', sqlerrm;
  end;

  -- ── Actividad ─────────────────────────────────────────────────────────────
  -- Visitas: filas de `visitas` (lo que cuenta /admin/visitas). El día ya está
  -- guardado en hora de Bolivia. La ciudad es `visitas.ciudad_slug`.
  begin
    select count(*)::integer into v_visitas_7d
      from visitas v
     where v.dia between v_desde_7 and v_hoy
       and (not v_filtra or v.ciudad_slug = btrim(p_ciudad_slug));
  exception when others then
    v_visitas_7d := null; raise warning 'admin_resumen: visitas_7d: %', sqlerrm;
  end;

  -- Contactos: leads que NO son una ficha vista (lo que cuenta /admin/estadisticas
  -- como contactos: WhatsApp, teléfono, mapa, reserva...). La ciudad es la del
  -- comercio contactado.
  begin
    select count(*)::integer into v_contactos_7d
      from leads l
      join comercios c on c.id = l.comercio_id
     where coalesce(l.tipo, '') <> 'vista'
       and l.created_at >= (v_desde_7::timestamp at time zone 'America/La_Paz')
       and l.created_at <  v_ts_hasta
       and (not v_filtra or c.ciudad_id = v_ciudad_id);
  exception when others then
    v_contactos_7d := null; raise warning 'admin_resumen: contactos_7d: %', sqlerrm;
  end;

  -- La serie de 30 días, rala: un renglón por día que tenga algo.
  --   altas      = comercios activos creados ese día (igual que «Altas por día»)
  --   visitas    = filas de `visitas` de ese día
  --   contactos  = leads que no son «vista»
  begin
    select coalesce(jsonb_agg(jsonb_build_object(
             'dia', e.dia, 'altas', e.altas, 'visitas', e.visitas, 'contactos', e.contactos
           ) order by e.dia), '[]'::jsonb)
      into v_serie
      from (
        select x.dia,
               sum(x.altas)::integer as altas,
               sum(x.visitas)::integer as visitas,
               sum(x.contactos)::integer as contactos
          from (
            select (c.created_at at time zone 'America/La_Paz')::date as dia,
                   1 as altas, 0 as visitas, 0 as contactos
              from comercios c
             where c.activo
               and c.created_at >= v_ts_desde and c.created_at < v_ts_hasta
               and (not v_filtra or c.ciudad_id = v_ciudad_id)
            union all
            select v.dia, 0, 1, 0
              from visitas v
             where v.dia between v_desde_30 and v_hoy
               and (not v_filtra or v.ciudad_slug = btrim(p_ciudad_slug))
            union all
            select (l.created_at at time zone 'America/La_Paz')::date, 0, 0, 1
              from leads l
              join comercios c on c.id = l.comercio_id
             where coalesce(l.tipo, '') <> 'vista'
               and l.created_at >= v_ts_desde and l.created_at < v_ts_hasta
               and (not v_filtra or c.ciudad_id = v_ciudad_id)
          ) x
         group by x.dia
      ) e;
  exception when others then
    v_serie := null; raise warning 'admin_resumen: serie_30d: %', sqlerrm;
  end;

  return jsonb_build_object(
    'comercios',  v_comercios,
    'por_ciudad', v_por_ciudad,
    'pendientes', jsonb_build_object(
      'publicaciones',          v_pub,
      'comercios_sin_verificar', v_sin_verificar,
      'pagos',                  v_pagos,
      'reclamos',               v_reclamos,
      'cambio_numero',          v_cambio,
      'suscripciones',          v_susc,
      'recepcion_sin_comercio', v_recepcion
    ),
    'actividad',  jsonb_build_object(
      'visitas_7d',    v_visitas_7d,
      'contactos_7d',  v_contactos_7d,
      'serie_30d',     v_serie
    )
  );
end
$fn$;

comment on function public.admin_resumen(text, date) is
  'Los números del tablero del panel en un solo jsonb (ver docs/admin-rediseno.md). Sólo el backend.';

-- Sólo el backend. Las funciones nacen ejecutables por PUBLIC: se les quita, y
-- se repite el GRANT por explícito (lección de Supabase Cloud). El público no
-- puede llamarla: devuelve cuántos pagos y reclamos hay pendientes.
revoke execute on function public.admin_resumen(text, date) from public, anon, authenticated;
grant  execute on function public.admin_resumen(text, date) to service_role;

-- PostgREST cachea el esquema: sin esto la función nueva no existe para `.rpc()`
-- hasta reiniciarlo.
notify pgrst, 'reload schema';
