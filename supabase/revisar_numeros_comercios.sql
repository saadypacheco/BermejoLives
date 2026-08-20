-- Revisión de números de comercios. Sólo lectura: no modifica nada.
--
-- Correr en el VPS antes de prender DIAS_GRACIA_SIN_PAGO y antes de confiar en
-- la reconciliación por número:
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U postgres -d postgres -f - < supabase/revisar_numeros_comercios.sql

\echo ''
\echo '=== 1. Números repetidos entre comercios ==='
\echo 'comercios.whatsapp NO es único. Si un número aparece en dos comercios, la'
\echo 'reconciliación al recibir un WhatsApp resuelve a UNO SOLO (arbitrario) y el'
\echo 'backfill de comercio_numeros dejó al otro sin fila.'
select regexp_replace(whatsapp, '\D', '', 'g') as numero,
       count(*)                                as cuantos,
       string_agg(nombre || ' (' || slug || ')', ' | ') as comercios
  from comercios
 where whatsapp is not null and whatsapp <> ''
 group by 1
having count(*) > 1
 order by 2 desc;

\echo ''
\echo '=== 2. Comercios SIN número: no pueden recibir reservas ==='
\echo 'Aparecen en el catálogo de Reservalo sin botón de WhatsApp.'
select slug, nombre, created_at::date as alta, cargado_por
  from comercios
 where activo and (whatsapp is null or whatsapp = '')
 order by created_at desc;

\echo ''
\echo '=== 3. Números con formato dudoso (no son celular boliviano) ==='
\echo 'El link de wa.me contra estos no abre ningún chat.'
select slug, nombre, whatsapp
  from comercios
 where activo
   and whatsapp is not null and whatsapp <> ''
   and regexp_replace(whatsapp, '\D', '', 'g') !~ '^(591)?[67][0-9]{7}$'
 order by nombre;

\echo ''
\echo '=== 4. A quiénes alcanzaría DIAS_GRACIA_SIN_PAGO=60 ==='
\echo 'Estos comercios SE CAERÍAN DEL MAPA en el próximo ciclo del job si se'
\echo 'prende la baja por gracia. Revisar ANTES de prenderla.'
select slug, nombre, created_at::date as alta,
       (current_date - created_at::date) as dias_desde_alta, cargado_por
  from comercios
 where activo
   and paga_hasta is null
   and created_at < now() - interval '60 days'
 order by created_at;

\echo ''
\echo '=== 5. Resumen ==='
select
  count(*) filter (where activo)                                        as activos,
  count(*) filter (where activo and (whatsapp is null or whatsapp = '')) as sin_numero,
  count(*) filter (where activo and paga_hasta is null)                  as nunca_pagaron,
  count(*) filter (where activo and paga_hasta is not null)              as alguna_vez_pagaron,
  count(*) filter (where activo and confiable)                           as confiables
  from comercios;
