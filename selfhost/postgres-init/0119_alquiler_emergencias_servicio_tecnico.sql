-- Tres rubros que faltaban (pedidos el 18/9/2026):
--
--   alquiler          🏠 Alquileres: locales, casas, departamentos y
--                     habitaciones. Comercial: el que alquila publica como
--                     cualquier negocio, y la subcategoría dice qué alquila
--                     (local, habitación, departamento, casa, galpón).
--   emergencias       🚓 Policía y emergencias: policía, comisaría, bomberos,
--                     hospital, posta. NO comercial, como los baños: son
--                     puntos de la ciudad para ubicar en el mapa. Los
--                     teléfonos (110 · 119 · 168) están en la guía.
--   servicio-tecnico  🛠️ Servicio técnico: celulares, computadoras,
--                     electrodomésticos, aire acondicionado, TV. Distinto
--                     de las tiendas que los venden (celulares, computación,
--                     electrodomésticos): acá se ARREGLAN.
--
-- Bancos ya están: `cajeros` es «🏧 Cajeros y bancos».

insert into rubros (slug, nombre, icono, orden, comercial) values
  ('alquiler',         '🏠 Alquileres',             '🏠', 59, true),
  ('servicio-tecnico', '🛠️ Servicio técnico',       '🛠️', 60, true),
  ('emergencias',      '🚓 Policía y emergencias',  '🚓', 61, false)
on conflict (slug) do update set
  nombre = excluded.nombre, icono = excluded.icono,
  orden = excluded.orden, comercial = excluded.comercial, activo = true;

-- Las palabras de cada uno. "hospital" no va en farmacia (que es la tienda
-- de remedios) sino acá; "aire acondicionado" a secas es la tienda de
-- electrodomésticos, el servicio se nombra con "reparación" o "instalación".
insert into rubro_palabras (rubro_slug, patron) values
  ('alquiler',         '\m(alquiler(es)?|alquilo|alquila|se alquila|en alquiler|inmobiliaria|arriendo|anticretico)'),
  ('emergencias',      '\m(policia|comisaria|bomberos|felcc|felcn|emergencias medicas|hospital|posta sanitaria|centro de salud|defensa civil|cruz roja)'),
  ('servicio-tecnico', '\m(servicio tecnico|reparacion de (celulares|telefonos|computadoras|notebooks|electrodomesticos|heladeras|lavarropas)|reparacion de tv|arreglo de celulares|tecnico en celulares|instalacion de aire acondicionado|reparacion de aire acondicionado|refrigeracion|electricista|plomero|gasista)')
on conflict (rubro_slug, patron) do nothing;
