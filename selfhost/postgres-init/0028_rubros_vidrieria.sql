-- ============================================================
-- Bermejo Live Market · 0028_rubros_vidrieria
-- Nuevos rubros: vidriería no encajaba bien en ninguno de los existentes.
-- ============================================================
insert into rubros (slug, nombre, icono, orden) values
  ('vidrios', 'Vidrios', 'square', 15),
  ('cuadros', 'Cuadros y espejos', 'image', 16)
on conflict (slug) do nothing;
