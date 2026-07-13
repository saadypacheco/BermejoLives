-- ============================================================
-- Bermejo Live Market · 0029_confirmacion_whatsapp_entrante
-- Login/recuperación por mensaje ENTRANTE de WhatsApp (en vez de que el
-- bot mande el código, el usuario lo confirma mandando un WhatsApp) — ver
-- docs/pendientes.md, sección 0, análisis 2026-07-13.
--
-- reset_code_confirmado_at: solo lo setea el webhook (ingest.py), cuando
-- llega un "CONFIRMAR-XXXXXX" que matchea código + número. El endpoint de
-- verificación exige que esto esté seteado, no solo que el código matchee
-- (si no, alcanzaría con conocer el código para pasar la verificación, sin
-- probar nunca que el celular es real).
-- ============================================================
alter table usuarios add column if not exists reset_code_confirmado_at timestamptz;
alter table comercio_usuarios add column if not exists reset_code_confirmado_at timestamptz;
