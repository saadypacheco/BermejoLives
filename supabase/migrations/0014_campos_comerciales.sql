-- 0014: campos comerciales adicionales (marca, sucursal, cocina, atm, estrellas, etc.)
alter table comercios
  add column if not exists marca           text,
  add column if not exists sucursal        text,
  add column if not exists tipo_cocina     text,
  add column if not exists tiene_atm       boolean default false,
  add column if not exists estrellas       int,
  add column if not exists combustibles    text[],
  add column if not exists internet_access boolean default false,
  add column if not exists especialidad    text,
  add column if not exists operador        text;
