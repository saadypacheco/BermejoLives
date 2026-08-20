-- campo_verificar.sql — Tablero del recorrido. SÓLO LECTURA, no modifica nada.
--
-- Correr las veces que haga falta durante la jornada:
--   cd /docker/uruku
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U postgres -d postgres -f - < supabase/campo_verificar.sql
--
-- Está pensado para leerse de arriba abajo: los bloques 1 y 2 son el semáforo de
-- lo que cargaste; el 3 al 5 son lo que llega por WhatsApp; el 6 es el resumen.

\pset border 2

\echo ''
\echo '################ 1. LO QUE CARGASTE HOY ################'
\echo 'Un ✗ en WA significa que ese local NO puede recibir reservas.'
select
  c.slug,
  left(c.nombre, 24)                                  as nombre,
  'URUKU-' || c.codigo                                as codigo,
  case when c.whatsapp is null or c.whatsapp = '' then '✗ FALTA'
       when regexp_replace(c.whatsapp, '\D', '', 'g') ~ '^(591)?[67][0-9]{7}$' then '✓'
       else '⚠ FORMATO' end                           as wa,
  case when c.lat is not null and c.lng is not null then '✓' else '✗' end as gps,
  case when c.portada_url is not null then '✓' else '✗' end               as foto,
  case when c.rubro_id  is not null then '✓' else '✗' end                 as rubro,
  to_char(c.created_at, 'HH24:MI')                    as hora
from comercios c
where c.activo
  and c.created_at::date = current_date
order by c.created_at;

\echo ''
\echo '################ 2. QUÉ LE FALTA A CADA UNO (todos los activos) ################'
\echo 'Esta es tu lista de trabajo: lo que hay que completar en la próxima pasada.'
select
  c.slug,
  left(c.nombre, 22) as nombre,
  'URUKU-' || c.codigo as codigo,
  nullif(concat_ws(', ',
    case when c.whatsapp is null or c.whatsapp = ''            then 'sin WhatsApp' end,
    case when c.nombre is null or c.nombre = '' or lower(c.nombre) = 'comercio'
                                                                then 'sin nombre real' end,
    case when c.portada_url is null                             then 'sin foto' end,
    case when c.lat is null or c.lng is null                    then 'sin GPS' end,
    case when c.rubro_id is null                                then 'sin rubro' end,
    case when c.direccion is null or c.direccion = ''           then 'sin dirección' end
  ), '') as le_falta
from comercios c
where c.activo
  and nullif(concat_ws(', ',
    case when c.whatsapp is null or c.whatsapp = '' then 'x' end,
    case when c.nombre is null or c.nombre = '' or lower(c.nombre) = 'comercio' then 'x' end,
    case when c.portada_url is null then 'x' end,
    case when c.lat is null or c.lng is null then 'x' end,
    case when c.rubro_id is null then 'x' end,
    case when c.direccion is null or c.direccion = '' then 'x' end
  ), '') is not null
order by c.created_at desc;

\echo ''
\echo '################ 3. LO QUE ENTRÓ POR WHATSAPP HOY ################'
\echo 'identidad: numero = el remitente ya estaba asociado'
\echo '           codigo = número desconocido + código del local (REVISAR antes de aprobar)'
\echo '           desconocido = no se pudo atribuir: se creó un borrador nuevo'
select
  to_char(p.created_at, 'HH24:MI')                    as hora,
  left(coalesce(c.nombre, '?'), 20)                   as comercio,
  p.estado,
  coalesce(p.identidad_origen, 'numero')              as identidad,
  case when p.codigo_recibido is not null then 'URUKU-' || p.codigo_recibido end as codigo,
  left(coalesce(p.titulo, p.descripcion, ''), 40)     as texto
from publicaciones p
left join comercios c on c.id = p.comercio_id
where p.origen = 'whatsapp'
  and p.created_at::date = current_date
order by p.created_at desc;

\echo ''
\echo '################ 4. PENDIENTES DE MODERACIÓN ################'
\echo 'Todo esto está esperando que lo apruebes o rechaces desde el panel.'
select
  to_char(p.created_at, 'DD/MM HH24:MI')              as cuando,
  left(coalesce(c.nombre, '?'), 22)                   as comercio,
  p.tipo,
  coalesce(p.identidad_origen, 'panel')               as identidad,
  left(coalesce(p.titulo, p.descripcion, ''), 40)     as texto
from publicaciones p
left join comercios c on c.id = p.comercio_id
where p.estado = 'pendiente' and p.activo
order by p.created_at desc
limit 40;

\echo ''
\echo '################ 5. MENSAJES QUE NO SE PUDIERON ATRIBUIR ################'
\echo 'Alguien escribió desde un número desconocido y SIN código: se creó un'
\echo 'comercio borrador "Comercio XXXX". Si es un local que ya cargaste, hay que'
\echo 'autorizarle el número desde el panel (⚙️) y borrar el duplicado.'
select
  c.slug, c.nombre, c.whatsapp, 'URUKU-' || c.codigo as codigo,
  to_char(c.created_at, 'DD/MM HH24:MI') as creado
from comercios c
where c.activo
  and c.slug like 'comercio-%'
  and c.wa_jid is not null
order by c.created_at desc;

\echo ''
\echo '################ 6. NÚMEROS AUTORIZADOS A PUBLICAR ################'
select
  left(c.nombre, 22) as comercio,
  n.numero,
  coalesce(n.etiqueta, '—') as de_quien,
  n.created_by as origen
from comercio_numeros n
join comercios c on c.id = n.comercio_id
where n.activo and c.activo
order by c.nombre, n.created_at;

\echo ''
\echo '################ 7. RESUMEN ################'
select
  count(*) filter (where activo)                                          as activos,
  count(*) filter (where activo and created_at::date = current_date)      as cargados_hoy,
  count(*) filter (where activo and (whatsapp is null or whatsapp = ''))  as sin_whatsapp,
  count(*) filter (where activo and portada_url is null)                  as sin_foto,
  count(*) filter (where activo and codigo is null)                       as sin_codigo,
  count(*) filter (where activo and confiable)                            as confiables,
  count(*) filter (where activo and paga_hasta is not null)               as pagando
from comercios;

\echo ''
\echo 'Publicaciones:'
select
  count(*) filter (where estado = 'pendiente' and activo)                 as pendientes,
  count(*) filter (where estado = 'aprobado'  and activo)                 as aprobadas,
  count(*) filter (where origen = 'whatsapp' and created_at::date = current_date) as entraron_hoy_por_wa
from publicaciones;
