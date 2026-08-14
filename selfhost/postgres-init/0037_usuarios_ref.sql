-- 0037: atribución de origen del usuario (referidos).
--   `ref` = código del QR/partner por el que llegó el usuario (negocio, punto,
--   creador, vendedor). Se guarda al CREAR el usuario (first-touch, no se pisa).
--   Es la base del sistema de recompensas por usuario nuevo (pago por usuario
--   verificado, no por "instalación" — que en iOS no se puede medir).
alter table usuarios add column if not exists ref text;
create index if not exists idx_usuarios_ref on usuarios (ref) where ref is not null;
