-- 0193 · Medición v2: el navegador deja de escribir, resumen por SQL y retención con piso.
--
-- Spec: docs/estadisticas-v2.md §4.1 (aprobada el 6/11/2026). La spec la llama 0185/0184; esos números
-- ya estaban tomados.
--
--  1. `visitas`: columnas `device` y `standalone`; sin policy de INSERT ni permisos para anon/authenticated
--     (la 0186 ya les había quitado el permiso: acá se cierra también la policy, por si alguien vuelve a darlo);
--     service_role queda sólo con insert + select (sin UPDATE, DELETE ni TRUNCATE).
--  2. `leads`: columnas `sesion` y `detalle`, índice por sesión; igual que `visitas`, pero service_role
--     CONSERVA update (el «¿te contestó?» escribe `respondio`).
--  3. `site_events`: eventos del sitio (catálogo cerrado), sólo para el backend.
--  4. `site_metrics_summary`, `comercio_origins` y `comercio_lead_counts`: el resumen del panel y de «Mi
--     comercio» por SQL, sin bajar 50.000 filas a Python. SECURITY INVOKER, sólo service_role.
--  5. `purge_site_metrics`: ÚNICO camino para borrar visitas y eventos, con el piso de 13 meses adentro.
--     Es la excepción «logs con TTL» a la regla de no borrar (AGENTS.md §7). `leads` y `busquedas` NO se purgan.
--  6. `admin_resumen`: mismo cuerpo que la 0143; «contactos» ya no cuenta `compartir` ni `red` (los dos tipos
--     nuevos de `leads` no son contactos con el comercio).
--
-- NO se toca `cost_switches` (la clave `umami_stats` de la spec queda para cuando se haga Umami).
-- PERMISOS (regla 11 de AGENTS.md): ninguna columna nueva es pública: anon y authenticated no leen
-- `visitas`, `leads` ni `site_events` (el bloque de comprobación del final lo verifica).
-- Idempotente: se puede correr dos veces. Todo en una transacción.
-- Copia idéntica en supabase/migrations/ y selfhost/postgres-init/.

begin;

-- ───────────────────────────────────────────── 1. visitas
alter table public.visitas add column if not exists device text
  check (device in ('mobile', 'tablet', 'desktop'));
alter table public.visitas add column if not exists standalone boolean not null default false;   -- abierta desde la app instalada

comment on column public.visitas.device is 'Tipo de pantalla (mobile, tablet, desktop). Lo manda el navegador; sin User-Agent.';
comment on column public.visitas.standalone is 'true si la abrió desde la app instalada (PWA) y no desde el navegador.';

drop policy if exists visitas_insert_public on public.visitas;
revoke all on public.visitas from public, anon, authenticated;
revoke update, delete, truncate on public.visitas from service_role;
grant select, insert on public.visitas to service_role;

-- ───────────────────────────────────────────── 2. leads
alter table public.leads add column if not exists sesion text
  check (char_length(sesion) <= 40);
alter table public.leads add column if not exists detalle text
  check (char_length(detalle) <= 20);       -- la red ('instagram'…) o el canal de compartir ('native' | 'copy')

comment on column public.leads.sesion is 'Id al azar de la pestaña (sessionStorage) que hizo el contacto: cruza con visitas.sesion para el embudo. Privada.';
comment on column public.leads.detalle is 'Para tipo red: la red (instagram, facebook, tiktok, youtube). Para compartir: native o copy. Privada.';

create index if not exists idx_leads_sesion on public.leads (sesion) where sesion is not null;

drop policy if exists leads_insert_public on public.leads;
revoke all on public.leads from public, anon, authenticated;
revoke delete, truncate on public.leads from service_role;
grant select, insert, update on public.leads to service_role;

-- ───────────────────────────────────────────── 3. eventos del sitio
create table if not exists public.site_events (
  id         uuid primary key default gen_random_uuid(),
  day        date not null default ((now() at time zone 'America/La_Paz')::date),
  event      text not null check (event in ('share', 'pwa_install', 'video_play', 'video_network_click', 'uruku_whatsapp_click')),
  detail     text not null default '' check (char_length(detail) <= 40),
  path       text not null check (char_length(path) <= 200),
  session    text check (char_length(session) <= 40),
  city_slug  text check (char_length(city_slug) <= 40),
  created_at timestamptz not null default now()
);

comment on table public.site_events is
  'Eventos del sitio (catálogo cerrado, docs/estadisticas-v2.md §4.5). Sin IP, sin User-Agent, sin cookies. Sólo el backend. Se purga a los 13 meses.';

create index if not exists idx_site_events_day     on public.site_events (day desc);
create index if not exists idx_site_events_session on public.site_events (session) where session is not null;

alter table public.site_events enable row level security;
revoke all on public.site_events from public, anon, authenticated;
revoke update, delete, truncate on public.site_events from service_role;
grant select, insert on public.site_events to service_role;

-- ───────────────────────────────────────────── 4. resúmenes por SQL
-- Resumen del sitio entre dos días (inclusivos, hora de Bolivia). Todo lo que sale de `visitas` y de
-- `site_events` filtra por `p_city` (slug) si viene; los contactos de `leads` filtran por la ciudad del
-- comercio contactado. La canonicalización de los referidos se hace en Python (services/site_metrics.py).
create or replace function public.site_metrics_summary(p_from date, p_to date, p_city text default null)
returns jsonb
language sql
stable
set search_path = public, pg_temp
set work_mem = '64MB'           -- que las ~300.000 filas de 90 días se agrupen en memoria
as $$
  with params as (
    select p_from as d1,
           p_to   as d2,
           nullif(btrim(p_city), '') as city,
           (p_from::timestamp at time zone 'America/La_Paz')         as ts1,
           ((p_to + 1)::timestamp at time zone 'America/La_Paz')     as ts2
  ),
  v as materialized (
    select x.dia, x.ruta, x.sesion, x.origen, x.referido, x.primera, x.device, x.standalone
      from public.visitas x, params p
     where x.dia between p.d1 and p.d2
       and (p.city is null or x.ciudad_slug = p.city)
  ),
  -- Una fila por sesión (un solo pase en vez de tres `count(distinct)`): si vio una ficha de comercio.
  sess as materialized (
    select sesion, bool_or(ruta like '/comercios/%') as ficha from v group by sesion
  ),
  leads_rango as (
    select l.tipo, l.sesion
      from public.leads l, params p
     where l.created_at >= p.ts1 and l.created_at < p.ts2
       and (p.city is null or exists (
             select 1 from public.comercios c
               join public.ciudades ci on ci.id = c.ciudad_id
              where c.id = l.comercio_id and ci.slug = p.city))
  )
  select jsonb_build_object(
    'totals', (
      select jsonb_build_object(
               'pageviews',   count(*),
               'sessions',    (select count(*) from sess),
               'first_pages', count(*) filter (where primera))
        from v),
    'by_day', (
      select coalesce(jsonb_agg(jsonb_build_object('dia', d.dia, 'visitas', coalesce(a.visitas, 0), 'personas', coalesce(a.personas, 0))
                                order by d.dia), '[]'::jsonb)
        from (select g::date as dia
                from params p, generate_series(p.d1::timestamp, p.d2::timestamp, interval '1 day') g) d
        left join (select dia, count(*) as visitas, count(*) filter (where primera) as personas
                     from v group by dia) a on a.dia = d.dia),
    'top_paths', (
      select coalesce(jsonb_agg(jsonb_build_object('ruta', t.ruta, 'n', t.n) order by t.n desc, t.ruta), '[]'::jsonb)
        from (select ruta, count(*) as n from v group by ruta order by n desc, ruta limit 15) t),
    'referrers_raw', (
      select coalesce(jsonb_agg(jsonb_build_object('referido', t.referido, 'origen', t.origen, 'n', t.n) order by t.n desc), '[]'::jsonb)
        from (select referido, origen, count(*) as n
                from v where primera
               group by referido, origen order by n desc limit 300) t),
    'origins', (
      select coalesce(jsonb_agg(jsonb_build_object('origen', t.origen, 'n', t.n) order by t.n desc, t.origen), '[]'::jsonb)
        from (select origen, count(*) as n from v where origen is not null
               group by origen order by n desc, origen limit 50) t),
    'devices', (
      select coalesce(jsonb_agg(jsonb_build_object('device', t.device, 'n', t.n) order by t.n desc), '[]'::jsonb)
        from (select coalesce(device, 'unknown') as device, count(*) as n
                from v where primera group by 1) t),
    'standalone_share', (
      select coalesce(round(avg(case when standalone then 1.0 else 0.0 end), 4), 0)
        from v where primera),
    'events', (
      select coalesce(jsonb_agg(jsonb_build_object('event', t.event, 'detail', t.detail, 'n', t.n) order by t.n desc, t.event, t.detail), '[]'::jsonb)
        from (select e.event, e.detail, count(*) as n
                from public.site_events e, params p
               where e.day between p.d1 and p.d2
                 and (p.city is null or e.city_slug = p.city)
               group by e.event, e.detail order by n desc limit 200) t),
    'funnel', (
      select jsonb_build_object(
               'sessions', (select count(*) from sess),
               'sessions_with_ficha', (select count(*) from sess where ficha),
               'sessions_with_contact', (
                  select count(*) from sess s
                   where s.sesion in (select l.sesion from leads_rango l
                                       where l.sesion is not null and l.tipo in ('whatsapp', 'telefono', 'reserva'))))),
    'leads_by_type', (
      select coalesce(jsonb_object_agg(t.tipo, t.n), '{}'::jsonb)
        from (select coalesce(tipo, 'otro') as tipo, count(*) as n from leads_rango group by 1) t),
    'ai_groups', (
      select coalesce(jsonb_agg(jsonb_build_object('origen', t.origen, 'referido', t.referido, 'n', t.n,
                                                   'people', t.people, 'fichas', t.fichas) order by t.n desc), '[]'::jsonb)
        from (select origen, referido, count(*) as n, count(distinct sesion) as people,
                     count(*) filter (where ruta like '/comercios/%') as fichas
                from v where origen is not null or referido is not null
               group by origen, referido order by n desc limit 500) t),
    'ai_routes', (
      select coalesce(jsonb_agg(jsonb_build_object('origen', t.origen, 'referido', t.referido, 'ruta', t.ruta, 'n', t.n) order by t.n desc), '[]'::jsonb)
        from (select origen, referido, ruta, count(*) as n
                from v where origen is not null or referido is not null
               group by origen, referido, ruta order by n desc limit 2000) t)
  );
$$;

-- De dónde llegaron a la ficha de UN comercio: las visitas cuya ruta es su ficha y que abrieron la sesión.
-- Sólo origen y referido (crudos) con su cuenta; el backend los canonicaliza. Nunca otros comercios.
create or replace function public.comercio_origins(p_comercio uuid, p_from date)
returns jsonb
language sql
stable
set search_path = public, pg_temp
as $$
  select coalesce(jsonb_agg(jsonb_build_object('origen', t.origen, 'referido', t.referido, 'n', t.n) order by t.n desc), '[]'::jsonb)
    from (select v.origen, v.referido, count(*) as n
            from public.comercios c
            join public.visitas v on v.ruta = '/comercios/' || c.slug
           where c.id = p_comercio
             and v.primera
             and v.dia >= p_from
           group by v.origen, v.referido
           order by n desc
           limit 100) t;
$$;

-- Contactos de UN comercio por tipo (últimos p_days y últimos 7 días) y toques a sus redes por red.
create or replace function public.comercio_lead_counts(p_comercio uuid, p_days int default 30)
returns jsonb
language sql
stable
set search_path = public, pg_temp
as $$
  select jsonb_build_object(
    'por_tipo', (
      select coalesce(jsonb_object_agg(t.tipo, t.n), '{}'::jsonb)
        from (select coalesce(tipo, 'otro') as tipo, count(*) as n
                from public.leads
               where comercio_id = p_comercio
                 and created_at >= now() - make_interval(days => greatest(1, p_days))
               group by 1) t),
    'por_tipo_7d', (
      select coalesce(jsonb_object_agg(t.tipo, t.n), '{}'::jsonb)
        from (select coalesce(tipo, 'otro') as tipo, count(*) as n
                from public.leads
               where comercio_id = p_comercio
                 and created_at >= now() - make_interval(days => least(7, greatest(1, p_days)))
               group by 1) t),
    'redes', (
      select coalesce(jsonb_object_agg(t.detalle, t.n), '{}'::jsonb)
        from (select coalesce(detalle, 'otra') as detalle, count(*) as n
                from public.leads
               where comercio_id = p_comercio
                 and tipo = 'red'
                 and created_at >= now() - make_interval(days => greatest(1, p_days))
               group by 1) t)
  );
$$;

revoke execute on function public.site_metrics_summary(date, date, text) from public, anon, authenticated;
revoke execute on function public.comercio_origins(uuid, date) from public, anon, authenticated;
revoke execute on function public.comercio_lead_counts(uuid, int) from public, anon, authenticated;
grant  execute on function public.site_metrics_summary(date, date, text) to service_role;
grant  execute on function public.comercio_origins(uuid, date) to service_role;
grant  execute on function public.comercio_lead_counts(uuid, int) to service_role;

-- ───────────────────────────────────────────── 5. retención con piso
-- Único camino para borrar `visitas` y `site_events` (service_role no tiene DELETE). El piso de 13 meses
-- está ADENTRO: un llamado con 1 mes falla. Devuelve la cantidad de filas borradas.
create or replace function public.purge_site_metrics(p_months int default 13)
returns int
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_corte date;
  v_visitas int;
  v_eventos int;
begin
  if p_months is null or p_months < 13 then
    raise exception 'retención mínima: 13 meses' using errcode = '22023';
  end if;
  v_corte := ((now() at time zone 'America/La_Paz') - make_interval(months => p_months))::date;
  delete from public.visitas where dia < v_corte;
  get diagnostics v_visitas = row_count;
  delete from public.site_events where day < v_corte;
  get diagnostics v_eventos = row_count;
  return v_visitas + v_eventos;
end
$$;

revoke execute on function public.purge_site_metrics(int) from public, anon, authenticated;
grant  execute on function public.purge_site_metrics(int) to service_role;

-- ───────────────────────────────────────────── 6. admin_resumen
-- Mismo cuerpo que la 0143. Cambia sólo la cuenta de contactos: `compartir` y `red` no son contactos.
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
     where coalesce(l.tipo, '') not in ('vista', 'compartir', 'red')
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
             where coalesce(l.tipo, '') not in ('vista', 'compartir', 'red')
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
revoke execute on function public.admin_resumen(text, date) from public, anon, authenticated;
grant  execute on function public.admin_resumen(text, date) to service_role;

-- ───────────────────────────────────────────── comprobación (si algo falla, no queda nada)
do $chk$
declare
  v_rol text;
  v_tabla text;
  v_col text;
  v_fn text;
begin
  -- 1. Ni anon ni authenticated tocan las tres tablas (ni las columnas nuevas).
  foreach v_rol in array array['anon', 'authenticated'] loop
    foreach v_tabla in array array['public.visitas', 'public.leads', 'public.site_events'] loop
      if has_table_privilege(v_rol, v_tabla, 'select') or has_table_privilege(v_rol, v_tabla, 'insert')
         or has_table_privilege(v_rol, v_tabla, 'update') or has_table_privilege(v_rol, v_tabla, 'delete') then
        raise exception '0193: % tiene permisos sobre %', v_rol, v_tabla;
      end if;
    end loop;
    foreach v_col in array array['device', 'standalone'] loop
      if has_column_privilege(v_rol, 'public.visitas', v_col, 'select') or has_column_privilege(v_rol, 'public.visitas', v_col, 'insert') then
        raise exception '0193: % toca visitas.%', v_rol, v_col;
      end if;
    end loop;
    foreach v_col in array array['sesion', 'detalle'] loop
      if has_column_privilege(v_rol, 'public.leads', v_col, 'select') or has_column_privilege(v_rol, 'public.leads', v_col, 'insert') then
        raise exception '0193: % toca leads.%', v_rol, v_col;
      end if;
    end loop;
  end loop;

  -- 2. No quedan policies de INSERT para el navegador.
  if exists (select 1 from pg_policies
              where schemaname = 'public' and tablename in ('visitas', 'leads', 'site_events')
                and cmd in ('INSERT', 'ALL')
                and (roles && array['anon', 'authenticated', 'public']::name[])) then
    raise exception '0193: queda una policy de escritura pública en visitas, leads o site_events';
  end if;

  -- 3. service_role: escribe y lee, pero no borra (visitas y eventos se purgan sólo con la función).
  if not has_table_privilege('service_role', 'public.visitas', 'insert')
     or not has_table_privilege('service_role', 'public.visitas', 'select')
     or not has_table_privilege('service_role', 'public.site_events', 'insert')
     or not has_table_privilege('service_role', 'public.site_events', 'select')
     or not has_table_privilege('service_role', 'public.leads', 'insert')
     or not has_table_privilege('service_role', 'public.leads', 'select')
     or not has_table_privilege('service_role', 'public.leads', 'update') then
    raise exception '0193: service_role perdió un permiso que necesita';
  end if;
  foreach v_tabla in array array['public.visitas', 'public.site_events', 'public.leads'] loop
    if has_table_privilege('service_role', v_tabla, 'delete') or has_table_privilege('service_role', v_tabla, 'truncate') then
      raise exception '0193: service_role puede borrar en %', v_tabla;
    end if;
  end loop;
  if has_table_privilege('service_role', 'public.visitas', 'update')
     or has_table_privilege('service_role', 'public.site_events', 'update') then
    raise exception '0193: service_role puede modificar visitas o site_events';
  end if;

  -- 4. Las funciones: sólo service_role.
  foreach v_fn in array array['public.site_metrics_summary(date, date, text)', 'public.comercio_origins(uuid, date)',
                              'public.comercio_lead_counts(uuid, int)', 'public.purge_site_metrics(int)',
                              'public.admin_resumen(text, date)'] loop
    foreach v_rol in array array['anon', 'authenticated'] loop
      if has_function_privilege(v_rol, v_fn, 'execute') then
        raise exception '0193: % puede ejecutar %', v_rol, v_fn;
      end if;
    end loop;
    if not has_function_privilege('service_role', v_fn, 'execute') then
      raise exception '0193: service_role no puede ejecutar %', v_fn;
    end if;
  end loop;

  -- 5. La retención tiene el piso adentro y corre con los permisos de su dueño.
  if not exists (select 1 from pg_proc where oid = 'public.purge_site_metrics(int)'::regprocedure and prosecdef) then
    raise exception '0193: purge_site_metrics tiene que ser SECURITY DEFINER';
  end if;
  begin
    perform public.purge_site_metrics(12);
    raise exception '0193: purge_site_metrics(12) no falló';
  exception when sqlstate '22023' then
    null;
  end;

  -- 6. El tablero ya no cuenta compartir ni red como contacto.
  if pg_get_functiondef('public.admin_resumen(text, date)'::regprocedure) not like '%not in (''vista'', ''compartir'', ''red'')%' then
    raise exception '0193: admin_resumen todavía cuenta compartir y red como contactos';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
