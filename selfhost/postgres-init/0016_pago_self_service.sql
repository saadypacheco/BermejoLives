-- ============================================================
-- Encontralo · 0016_pago_self_service
-- Pago QR self-service: el comercio sube su comprobante desde el panel
-- (queda 'pendiente'); el admin lo confirma y recién ahí extiende paga_hasta.
-- Los pagos que registra el admin directo siguen naciendo 'confirmado'.
-- ============================================================

alter table pagos add column if not exists estado          text not null default 'confirmado';  -- 'pendiente'|'confirmado'|'rechazado'
alter table pagos add column if not exists comprobante_url text;

create index if not exists idx_pagos_pendientes on pagos (created_at desc) where estado = 'pendiente';
