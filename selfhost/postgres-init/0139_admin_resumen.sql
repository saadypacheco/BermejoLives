-- El tablero del panel: UN pedido en vez de bajar listas (docs/admin-rediseno.md §3-§5).
--
-- Hasta hoy el panel, para mostrar unos contadores, bajaba la lista COMPLETA de
-- comercios (1.300+ filas con todas sus columnas) y seis listas más, y contaba en
-- el navegador. Esta función devuelve todos los números ya contados, en un solo
-- jsonb, y NUNCA baja filas: PostgREST corta en 1000 sin avisar, así que
-- contar filas bajadas daría un número plausible y falso.
--
-- Idempotente (`create or replace`): se puede correr dos veces.
--
-- Parámetros
--   p_ciudad_slug  slug de la ciudad, o null = todas. Un slug que no existe NO es
--                  un error: los conteos de comercios dan 0.
--   p_hoy          el «hoy» de Bolivia. Lo manda el backend (así se prueba sin
--                  depender del reloj); sin él, se calcula acá en America/La_Paz.
--
-- Qué respeta la ciudad y qué no
--   Respetan la ciudad: `comercios`, `pendientes.comercios_sin_verificar` y la
--   `actividad` (altas, visitas y contactos). NO la respetan —son el badge de una
--   sección que hoy lista todo— los demás pendientes. `por_ciudad` trae SIEMPRE
--   todas las ciudades activas.
--
-- Si una parte falla
--   Cada pendiente y cada número de actividad va en su propio bloque: si uno
--   falla, ese número sale null, queda un WARNING en el log de Postgres con el
--   motivo y el resto sigue. `comercios` y `por_ciudad` no se atajan: si fallan,
--   la función falla (no hay tablero sin ellos) y el backend contesta 503.
--
-- La serie de 30 días sale rala (sólo los días con algo): rellenar los días
-- vacíos con 0 lo hace el backend, que además sabe cuál es «hoy» en Bolivia.
-- El día es el de Bolivia (UTC−4, sin horario de verano): lo dado de alta después
-- de las 20:00 no puede caer en el día siguiente.

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
  begin
    select count(*)::integer into v_susc
      from comercios c
     where c.activo
       and (c.suspendido or (c.paga_hasta is not null and c.paga_hasta <= v_hoy + 5));
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
