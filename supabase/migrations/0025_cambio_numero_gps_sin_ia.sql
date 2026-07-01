-- 0025: solicitudes_cambio_numero pasa a lat/lng (GPS), sin IA de similitud.
-- El admin decide solo con foto + coordenadas + WhatsApp nuevo.

alter table solicitudes_cambio_numero
  add column if not exists lat double precision,
  add column if not exists lng double precision,
  drop column if exists similitud_estimada;
