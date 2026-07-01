-- 0023: comercio_usuarios sin email/contraseña obligatorios.
-- El alta self-service (autoregistro) y de campo (/publicar) ya no piden
-- email+contraseña: el negocio queda identificado por WhatsApp y entra por
-- código (OTP), igual que la recuperación de clave (migración 0022).
-- `unique` sobre email sigue funcionando con NULLs (Postgres no las compara).

alter table comercio_usuarios
  alter column email drop not null,
  alter column password_hash drop not null;
