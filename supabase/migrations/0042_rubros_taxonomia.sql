-- 0042: taxonomía URUKU v2 (42 categorías, con los agregados de Bermejo:
-- gastronomía, servicios + cambio de moneda, feria americana/usado, hospedaje, otros).
-- Desactiva los rubros viejos y siembra los nuevos. Los comercios existentes conservan
-- su rubro_id (la FK es por id; el join resuelve el nombre aunque el rubro esté inactivo);
-- solo dejan de aparecer como chip elegible. El nombre lleva el emoji para el alta/filtros.
-- El nivel "familia" y el diccionario de sinónimos van en una migración posterior.

update rubros set activo = false;

insert into rubros (slug, nombre, icono, orden) values
  ('ropa', '👕 Moda y ropa', '👕', 1),
  ('calzado', '👟 Calzado', '👟', 2),
  ('bolsos', '🎒 Bolsos y accesorios', '🎒', 3),
  ('joyeria', '💍 Joyería, relojes y accesorios', '💍', 4),
  ('belleza', '💄 Perfumería y belleza', '💄', 5),
  ('optica', '👓 Óptica', '👓', 6),
  ('celulares', '📱 Celulares y accesorios', '📱', 7),
  ('computacion', '💻 Tecnología y computación', '💻', 8),
  ('electronica', '📺 TV, audio y electrónica', '📺', 9),
  ('electrodomesticos', '🔌 Electrodomésticos', '🔌', 10),
  ('bazar', '🍳 Bazar y cocina', '🍳', 11),
  ('hogar', '🛏️ Hogar, blanco y decoración', '🛏️', 12),
  ('muebles', '🛋️ Muebles y colchones', '🛋️', 13),
  ('ferreteria', '🔧 Ferretería y construcción', '🔧', 14),
  ('repuestos-autos', '🚗 Repuestos para autos', '🚗', 15),
  ('neumaticos', '🛞 Neumáticos y lubricantes', '🛞', 16),
  ('motos', '🏍️ Motos y accesorios', '🏍️', 17),
  ('bicicletas', '🚲 Bicicletas', '🚲', 18),
  ('alimentos', '🛒 Supermercado y alimentos', '🛒', 19),
  ('bebidas', '🥤 Bebidas', '🥤', 20),
  ('farmacia', '💊 Farmacia y salud', '💊', 21),
  ('mascotas', '🐾 Mascotas', '🐾', 22),
  ('restaurantes', '🍽️ Restaurantes', '🍽️', 23),
  ('comida-rapida', '🍔 Rotisería y comida rápida', '🍔', 24),
  ('cafeteria', '☕ Café, heladería y postres', '☕', 25),
  ('panaderia', '🥖 Panadería', '🥖', 26),
  ('cambio', '💱 Cambio de moneda', '💱', 27),
  ('envios', '📦 Envíos y encomiendas', '📦', 28),
  ('peluqueria', '💈 Peluquería y barbería', '💈', 29),
  ('lavadero', '🧼 Lavadero', '🧼', 30),
  ('gomeria-servicio', '🔩 Gomería (servicio)', '🔩', 31),
  ('cerrajeria', '🗝️ Cerrajería', '🗝️', 32),
  ('hospedaje', '🏨 Hospedaje', '🏨', 33),
  ('jugueteria', '🧸 Juguetería, librería y escolar', '🧸', 34),
  ('bebes', '👶 Bebés y niños', '👶', 35),
  ('deportes', '⚽ Deportes y fitness', '⚽', 36),
  ('regaleria', '🎉 Regalería y cotillón', '🎉', 37),
  ('ropa-americana', '👕 Ropa americana', '👕', 38),
  ('calzado-usado', '👟 Calzado usado / zapatillas americanas', '👟', 39),
  ('usados', '♻️ Usados en general', '♻️', 40),
  ('otros', '📦 Otros (a clasificar)', '📦', 41),
  ('floreria', '🌷 Florería', '🌷', 42)
on conflict (slug) do update set
  nombre = excluded.nombre,
  icono  = excluded.icono,
  orden  = excluded.orden,
  activo = true;
