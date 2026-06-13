-- ============================================================
-- Bermejo Live Market · 0003_seed
-- Datos de ejemplo para desarrollo (zonas, comercios, productos, feed).
-- Idempotente: usa slugs/ids estables con on conflict do nothing.
-- ============================================================

-- ZONAS
insert into zonas (slug, nombre, descripcion, color, icono, orden) values
  ('importadoras', 'Zona Importadoras', 'Electrónica y tecnología de frontera', '#9b5cff', 'box',     1),
  ('zona-moda',    'Zona Moda',         'Ropa, calzado y accesorios',           '#2e6bff', 'shirt',   2),
  ('tecnologia',   'Zona Tecnología',   'Computación, celulares y gadgets',     '#39ff9e', 'cpu',     3),
  ('galerias',     'Galerías',          'Galerías comerciales del centro',      '#ff4d8d', 'building',4),
  ('gastronomia',  'Gastronomía',       'Comida, bebidas y delivery',           '#ffc23d', 'utensils',5),
  ('centro',       'Centro Comercial',  'Comercios del centro de Bermejo',      '#ff8a3d', 'store',   6)
on conflict (slug) do nothing;

-- COMERCIOS (con todos los datos de contacto/redes/ubicación)
insert into comercios
  (slug, nombre, descripcion, logo_url, portada_url, whatsapp, telefono,
   tiktok_url, facebook_url, instagram_url, sitio_web,
   zona_id, direccion, lat, lng, plan, verificado, rating, destacado, wa_jid)
values
  ('importadora-abc', 'Importadora ABC',
   'Importadora líder en Bermejo. Electrónica, tecnología y electrodomésticos a precio de frontera. Mayorista y minorista.',
   'https://picsum.photos/seed/abclogo/200/200', '/comercios2.png',
   '59170000001', '+591 3 0000001',
   'https://www.tiktok.com/@importadora.abc', 'https://facebook.com/importadoraabc',
   'https://instagram.com/importadora.abc', 'https://importadoraabc.com',
   (select id from zonas where slug='importadoras'), 'Galería Central, Local 14 · Bermejo',
   -22.7361, -64.3433, 'premium', true, 4.9, true, '59170000001@c.us'),

  ('moda-bermejo', 'Moda Bermejo',
   'Las últimas tendencias en ropa y calzado. Talles para toda la familia.',
   'https://picsum.photos/seed/modalogo/200/200', '/comercios3.png',
   '59170000002', null,
   'https://www.tiktok.com/@moda.bermejo', 'https://facebook.com/modabermejo', null, null,
   (select id from zonas where slug='zona-moda'), 'Av. Comercio 245 · Bermejo',
   -22.7370, -64.3440, 'pro', true, 4.8, true, '59170000002@c.us'),

  ('tecno-store', 'Tecno Store',
   'Computadoras, celulares y accesorios. Servicio técnico propio.',
   'https://picsum.photos/seed/teclogo/200/200', '/comercios4.png',
   '59170000003', null,
   null, 'https://facebook.com/tecnostore', 'https://instagram.com/tecnostore', null,
   (select id from zonas where slug='tecnologia'), 'Galería Tecnológica, Local 8 · Bermejo',
   -22.7355, -64.3428, 'pro', false, 4.7, true, '59170000003@c.us'),

  ('perfumeria-vip', 'Perfumería VIP',
   'Perfumes importados originales. Ideal para regalo.',
   'https://picsum.photos/seed/perflogo/200/200', '/comercios6.png',
   '59170000004', null,
   'https://www.tiktok.com/@perfumeria.vip', null, 'https://instagram.com/perfumeria.vip', null,
   (select id from zonas where slug='centro'), 'Centro Comercial, Local 3 · Bermejo',
   -22.7365, -64.3435, 'premium', true, 4.9, true, '59170000004@c.us'),

  ('calzados-top', 'Calzados Top',
   'Calzado de cuero legítimo. Mayoristas y minoristas.',
   'https://picsum.photos/seed/calzlogo/200/200', '/comercio5.png',
   '59170000005', null,
   null, 'https://facebook.com/calzadostop', null, null,
   (select id from zonas where slug='zona-moda'), 'Galería Norte, Local 22 · Bermejo',
   -22.7372, -64.3445, 'gratis', false, 4.6, true, '59170000005@c.us')
on conflict (slug) do nothing;

-- PRODUCTOS (catálogo de Importadora ABC)
insert into productos (comercio_id, nombre, descripcion, precio, moneda, foto_url, destacado)
select c.id, p.nombre, p.descripcion, p.precio, p.moneda, p.foto_url, p.destacado
from comercios c
cross join (values
  ('iPhone 13 128GB',  'Sellado, batería 100%, garantía 6 meses', 499, 'USD', 'https://picsum.photos/seed/iphone13/400/400', true),
  ('Smart TV 55" 4K',  'Última generación, con garantía',         399, 'USD', 'https://picsum.photos/seed/tv55/400/400',     true),
  ('Notebook Gamer',   'Recién llegada, stock limitado',          650, 'USD', 'https://picsum.photos/seed/laptop/400/400',   false),
  ('AirPods Pro',      'Originales con estuche de carga',          120, 'USD', 'https://picsum.photos/seed/airpods/400/400',  false)
) as p(nombre, descripcion, precio, moneda, foto_url, destacado)
where c.slug = 'importadora-abc'
on conflict do nothing;

-- PUBLICACIONES de ejemplo (feed). Algunas aprobadas, algunas pendientes.
insert into publicaciones
  (comercio_id, tipo, titulo, descripcion, precio, moneda, imagen_url, tiktok_url,
   estado, origen, wa_message_id, approved_at)
select c.id, v.tipo, v.titulo, v.descripcion, v.precio, v.moneda, v.imagen_url, v.tiktok_url,
       v.estado, 'whatsapp', v.wamid,
       case when v.estado = 'aprobado' then now() else null end
from comercios c
join (values
  ('importadora-abc', 'oferta', 'iPhone 13 128GB',  'Sellado, garantía. Precio de frontera.', 499, 'USD', 'https://picsum.photos/seed/iphone13/700/440', null,                                              'aprobado',  'seed-wa-001'),
  ('moda-bermejo',    'oferta', 'Zapatillas Nike Air','Nuevas, todos los talles.',            120, 'BOB', 'https://picsum.photos/seed/nike/700/440',     null,                                              'aprobado',  'seed-wa-002'),
  ('perfumeria-vip',  'oferta', 'Perfume 212 VIP',   'Original importado.',                   250, 'BOB', 'https://picsum.photos/seed/perfume/700/440',  null,                                              'aprobado',  'seed-wa-003'),
  ('tecno-store',     'video',  'Unboxing Smart TV', 'Mirá la review completa.',              null, 'BOB', 'https://picsum.photos/seed/tvbox/700/440',   'https://www.tiktok.com/@tecnostore/video/123',     'aprobado',  'seed-wa-004'),
  ('calzados-top',    'oferta', 'Botas de cuero',    'Temporada invierno, todos los talles.', 320, 'BOB', 'https://picsum.photos/seed/boots/700/440',    null,                                              'pendiente', 'seed-wa-005'),
  ('importadora-abc', 'novedad','Llegó stock nuevo', 'Notebooks gamer recién llegadas.',      null, 'BOB', 'https://picsum.photos/seed/laptop2/700/440', null,                                              'pendiente', 'seed-wa-006')
) as v(slug, tipo, titulo, descripcion, precio, moneda, imagen_url, tiktok_url, estado, wamid)
  on c.slug = v.slug
on conflict (wa_message_id) do nothing;
