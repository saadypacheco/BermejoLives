-- 0022: Recuperación de contraseña por código enviado a WhatsApp.
-- Código de 6 dígitos, corta vida (ver expiración validada en backend).

alter table comercio_usuarios
  add column if not exists reset_code         text,
  add column if not exists reset_code_expira  timestamptz;
