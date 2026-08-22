-- Informe completo de comercios, en CSV. SÓLO LECTURA.
--
--   cd /docker/uruku
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U postgres -d postgres -f - < supabase/export_comercios_completo.sql > comercios.csv
--
-- Después se baja del VPS con scp y se abre en Excel (UTF-8, separador coma).
--
-- Una fila por comercio con TODO lo que hay hoy: lo que cargó la persona, lo que
-- detectó la IA, el estado de plataforma y —lo más útil— tres columnas
-- calculadas que responden las preguntas que importan:
--
--   encontrable  ¿lo encuentra un comprador buscando por texto?
--   reservable   ¿puede recibir un mensaje, o es sólo un punto en el mapa?
--   que_falta    qué habría que completar en la próxima pasada
--
-- El orden pone primero lo que menos sirve: los que no se encuentran ni se
-- pueden contactar. Esa es la lista de trabajo.

\pset format csv
\pset tuples_only off

with rubros_de AS (
  select cr.comercio_id, string_agg(r.nombre, ' | ' order by r.orden) as todos
    from comercio_rubros cr join rubros r on r.id = cr.rubro_id
   group by cr.comercio_id
),
fotos_de as (
  select comercio_id, count(*) as n from comercio_fotos group by comercio_id
)
select
  -- Identidad
  c.slug,
  c.nombre,
  'URUKU-' || c.codigo                                   as codigo,

  -- Ubicación
  coalesce(l.nombre, '(a la calle)')                     as lugar,
  coalesce(c.puesto, '')                                 as puesto,
  coalesce(c.direccion, '')                              as direccion,
  c.lat, c.lng,

  -- Contacto
  coalesce(c.whatsapp, '')                               as whatsapp,
  case
    when coalesce(c.whatsapp,'') = '' then 'FALTA'
    when regexp_replace(c.whatsapp, '\D', '', 'g') ~ '^(591)?[67][0-9]{7}$' then 'ok BO'
    when regexp_replace(c.whatsapp, '\D', '', 'g') ~ '^549[0-9]{10}$'       then 'ok AR'
    else 'FORMATO DUDOSO'
  end                                                     as whatsapp_estado,
  coalesce(c.telefono, '')                               as telefono,

  -- Clasificación
  coalesce(r.nombre, '(sin rubro)')                      as rubro_principal,
  coalesce(rd.todos, '')                                 as todos_los_rubros,
  coalesce(c.subcategoria, '')                           as subcategoria,

  -- Contenido: humano vs IA, separados a propósito
  coalesce(c.prod_obs_human, '')                         as productos_humano,
  coalesce(c.prod_det_ia, '')                            as productos_ia,
  coalesce(c.descripcion, '')                            as descripcion_ia,
  case when c.ia_analizado_at is null then 'NO' else to_char(c.ia_analizado_at, 'DD/MM HH24:MI') end
                                                          as analizado_ia,

  -- Fotos
  case when c.portada_url is not null then 'sí' else 'NO' end as portada,
  coalesce(f.n, 0)                                       as fotos_galeria,

  -- Estado de plataforma
  case when c.verificado then 'sí' else 'no' end         as verificado,
  case when c.confiable  then 'sí' else 'no' end         as confiable,
  c.plan,
  coalesce(c.paga_hasta::text, '')                       as paga_hasta,
  c.modalidad,

  -- Trazabilidad
  to_char(c.created_at, 'DD/MM/YYYY HH24:MI')            as cargado_el,
  coalesce(c.cargado_por, '')                            as cargado_por,

  -- ── Lo calculado: las respuestas que importan ──────────────────────────────
  -- Encontrable = el buscador indexa nombre + descripción + productos +
  -- dirección, y matchea por nombre de rubro. Sin nada de eso, sólo lo ve quien
  -- pase por el mapa.
  case when (c.nombre is not null and lower(c.nombre) <> 'comercio')
         or coalesce(c.descripcion,'') <> ''
         or coalesce(c.prod_obs_human,'') <> ''
         or coalesce(c.prod_det_ia,'') <> ''
         or exists (select 1 from comercio_rubros cr2 join rubros r2 on r2.id = cr2.rubro_id
                     where cr2.comercio_id = c.id and r2.slug <> 'otros')
       then 'sí' else 'NO' end                            as encontrable,

  -- Reservable = tiene un canal por el que le llegue un mensaje.
  case when coalesce(c.whatsapp,'') <> '' then 'sí' else 'NO' end as reservable,

  nullif(concat_ws(' · ',
    case when c.nombre is null or lower(c.nombre) = 'comercio' then 'nombre real' end,
    case when coalesce(c.whatsapp,'') = ''                     then 'whatsapp' end,
    case when c.portada_url is null                            then 'foto' end,
    case when coalesce(r.slug,'otros') = 'otros'               then 'clasificar' end,
    case when coalesce(c.prod_obs_human,'') = ''
          and coalesce(c.prod_det_ia,'') = ''                  then 'productos' end,
    case when c.lat is null or c.lng is null                   then 'GPS' end
  ), '')                                                  as que_falta

from comercios c
left join rubros r      on r.id = c.rubro_id
left join lugares l     on l.id = c.lugar_id
left join rubros_de rd  on rd.comercio_id = c.id
left join fotos_de f    on f.comercio_id  = c.id
where c.activo
order by
  -- Primero los que no sirven para nada todavía: ni se encuentran ni se contactan.
  (case when coalesce(c.whatsapp,'') = '' then 1 else 0 end)
  + (case when coalesce(r.slug,'otros') = 'otros' then 1 else 0 end)
  + (case when c.nombre is null or lower(c.nombre) = 'comercio' then 1 else 0 end) desc,
  c.nombre;
