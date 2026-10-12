-- Ronda 2 de portada y permisos (docs/portada-y-permisos.md, «Ronda 2»).
--
-- 1. PERMISO `comercios.cuenta`
--    Cambiar el WhatsApp de una ficha (es la llave de ingreso a Mi comercio), marcar
--    `confiable` (publicar sin cola), autorizar números, atar grupos y escribirle al
--    comercio son cosas de la CUENTA, no de la ficha. Con la 0146 el publicador
--    corrige fichas (`comercios.editar`) pero NO maneja cuentas: este permiso lo
--    tienen el admin (`*`) y el moderador. Acá se le suma al rol `moderador`.
--    Igual que la 0146: no prende un rol que el admin vació (cardinality > 0) y no
--    duplica el permiso (idempotente).
--
-- 2. `comercios.baja_motivo`: POR QUÉ un comercio está dado de baja (`activo = false`).
--      admin     lo dio de baja una persona del equipo («Rechazar»). Sólo se deshace
--                con «Reactivar» en Dados de baja.
--      vencido   lo ocultó el job de vencimientos (`ocultar_comercios_vencidos`). Se
--                reactiva solo al registrar el pago.
--      borrador  nació apagado de un WhatsApp desconocido, a la espera de que alguien
--                mire lo que mandó. Aprobar una publicación suyo lo enciende.
--      null      activo, o una baja anterior a esta migración que no se pudo clasificar.
--    Antes todo era `activo = false` y no se podía distinguir: aprobar una oferta
--    reactivaba a un comercio que el admin acababa de dar de baja, y un comercio
--    vencido aparecía en «Dados de baja» pidiendo un «Reactivar» que el pago ya hace.
--
--    PRIVADA para anon: la 0145 da `select` por columnas, así que una columna nueva
--    nace cerrada y acá NO se le da `grant`. El backend (service_role) la lee y escribe.
--
-- Idempotente: se puede correr dos veces. Todo en una transacción.

begin;

-- ── 1. El permiso, al rol moderador ──────────────────────────────────────────
update roles
   set permisos = array_append(permisos, 'comercios.cuenta')
 where slug = 'moderador'
   and cardinality(permisos) > 0
   and not ('comercios.cuenta' = any(permisos));

-- ── 2. El motivo de la baja ──────────────────────────────────────────────────
alter table comercios
  add column if not exists baja_motivo text
  check (baja_motivo in ('admin', 'vencido', 'borrador'));

comment on column comercios.baja_motivo is
  'Por qué está dado de baja (activo = false): admin (lo bajó una persona), vencido (lo ocultó el job de vencimientos; se reactiva al pagar), borrador (nació apagado de un WhatsApp desconocido). Null si está activo o es una baja vieja sin clasificar. Privada para anon.';

-- Los que ya están inactivos, clasificados con el mismo criterio que usa el código.
-- Sólo donde todavía no hay motivo (si se corre dos veces no pisa nada).
--
-- borrador: el que armaba el 1 a 1 sin código de la ingesta vieja: slug `comercio-NNNNNN`,
-- nombre `Comercio NNNN`, con `wa_jid`, sin agente que lo haya cargado.
update comercios
   set baja_motivo = 'borrador'
 where activo = false
   and baja_motivo is null
   and slug ~ '^comercio-[0-9]+$'
   and nombre ~ '^Comercio [0-9]+$'
   and wa_jid is not null
   and cargado_por is null;

-- vencido: el que ocultó `ocultar_comercios_vencidos` (repository.py): no es de
-- cortesía y su `paga_hasta` venció hace más de `dias_vencido_baja` (40 por defecto).
-- Los que nunca pagaron (paga_hasta null) se ocultan sólo si se prende
-- DIAS_GRACIA_SIN_PAGO, que está apagado: no se pueden distinguir de una baja del admin,
-- así que quedan sin motivo y aparecen en «Dados de baja» (lo prudente: ahí se ven).
update comercios
   set baja_motivo = 'vencido'
 where activo = false
   and baja_motivo is null
   and coalesce(plan_cortesia, false) = false
   and paga_hasta is not null
   and paga_hasta < (current_date - 40);

commit;

-- PostgREST: columna nueva.
notify pgrst, 'reload schema';
