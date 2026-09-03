-- Los rubros que faltaban, sacados de lo que la IA venía pidiendo.
--
-- `rubros_propuestos` guarda las categorías que el modelo propuso mirando
-- vidrieras reales y que no existían. Leída por frecuencia, esa lista dice tres
-- cosas distintas y cada una se arregla de otra forma:
--
--   1. Categorías que faltan de verdad     -> rubro nuevo (abajo)
--   2. Otra forma de decir una que existe  -> una palabra al diccionario
--   3. Cosas que ya cubrimos esta semana   -> nada (coca, tornería)
--
-- Confundirlas es lo que llevó a los 19 rubros vacíos que hubo que apagar en
-- agosto: se creaba un rubro por cada nombre distinto que alguien dijera.

-- ── 1. LOS QUE FALTABAN ──────────────────────────────────────────────────────

insert into rubros (slug, nombre, icono, orden, comercial) values
  -- 13 pedidos, más que florería (9) u óptica (9), que sí tienen el suyo.
  -- La pollería va acá y no aparte: son el mismo local en Bermejo, y separadas
  -- quedarían de tres comercios cada una.
  ('carniceria', '🥩 Carnicería y pollería',        '🥩', 51, true),
  -- 6 pedidos. Hoy caen en alimentos, junto a los que venden comida.
  ('limpieza',   '🧴 Artículos de limpieza',        '🧴', 52, true),
  -- 3 pedidos. Un servicio que se busca una vez y con urgencia: si no está, no
  -- se busca dos veces.
  ('funeraria',  '🕯️ Funeraria',                    '🕯️', 53, true),
  -- 3 pedidos. `ropa` es prenda hecha; esto es la tela por metro y la mercería.
  ('telas',      '🧵 Telas y mercería',             '🧵', 54, true),
  -- gimnasio (3) + cancha de fútbol (3). Es un SERVICIO: se va a entrenar, no a
  -- comprar. Mezclado con `deportes` —que vende pelotas y suplementos— quien
  -- busca comprar recibe gimnasios y al revés.
  ('gimnasios',  '🏋️ Gimnasios y canchas',          '🏋️', 55, true)
on conflict (slug) do update set
  nombre = excluded.nombre, icono = excluded.icono,
  orden = excluded.orden, comercial = excluded.comercial, activo = true;

insert into rubro_palabras (rubro_slug, patron) values
  -- "pollo" y "chorizo" a secas NO van: los vende media comida rápida de la
  -- ciudad. Van las formas del negocio, no las del plato.
  ('carniceria', '\m(carniceria|carniceria y polleria|polleria|media res|carne vacuna|carne de cerdo|carne molida|achura|matambre|embutido casero)'),
  -- "detergente" y "lavandina" a secas tampoco: los vende cualquier almacén y
  -- cualquier kiosco. Sólo las formas compuestas nombran al negocio.
  ('limpieza',   '\m(articulo de limpieza|articulos de limpieza|producto de limpieza|productos de limpieza|limpieza del hogar|papelera y limpieza|distribuidora de limpieza)'),
  ('funeraria',  '\m(funeraria|servicio funebre|servicios funebres|sala velatoria|velatorio|cajon mortuorio|coronas funebres)'),
  -- "tela" a secas aparece en bazares ("tela plástica", "mantel de tela").
  ('telas',      '\m(merceria|tienda de tela|tienda de telas|venta de tela|venta de telas|tela por metro|telas por metro|lenceria de tela|hilo y aguja)'),
  ('gimnasios',  '\m(gimnasio|crossfit|musculacion|spinning|clase de zumba|cancha de futbol|cancha sintetica|futbol 5|futbol cinco|natatorio)')
on conflict (rubro_slug, patron) do nothing;

-- Un gimnasio dejó de ser "deportes": el patrón viejo tenía `gimnasio` y
-- `fitness`, así que una tienda de suplementos y un local que da clases
-- terminaban en el mismo rubro por palabras que nombran cosas distintas.
delete from rubro_palabras
 where rubro_slug = 'deportes'
   and patron = '\m(deporte|deportivo|gimnasio|fitness|pelota|futbol|suplemento)';
insert into rubro_palabras (rubro_slug, patron) values
  ('deportes', '\m(articulo deportivo|articulos deportivos|indumentaria deportiva|pelota|suplemento deportivo|proteina en polvo|camiseta de futbol|botin de futbol)')
on conflict (rubro_slug, patron) do nothing;

-- ── 2. LAS QUE SON OTRA FORMA DE DECIR LO MISMO ──────────────────────────────
--
-- Éstas NO llevan rubro: llevan una palabra al que ya existe. Un rubro nuevo
-- por cada sinónimo es exactamente cómo se llega a 19 rubros vacíos.
insert into rubro_palabras (rubro_slug, patron) values
  ('neumaticos',  '\m(lubricentro|cambio de aceite|engrase)'),
  ('jugueteria',  '\m(pelucheria|peluche)'),
  ('ropa',        '\m(jeaneria|vestido de fiesta|vestidos de fiesta|ropa de fiesta)'),
  ('ferreteria',  '\m(buloneria|bulon|perfileria)'),
  ('joyeria',     '\m(bijouterie|bisuteria|fantasia fina)'),
  ('bazar',       '\m(articulo de plastico|articulos de plastico|plastiquería|plastiqueria)'),
  ('restaurantes','\m(comedor popular|comedor|pension de comida)'),
  ('farmacia',    '\m(ortopedia|laboratorio clinico|analisis clinico|dietetica|herboristeria|suplemento natural)'),
  ('celulares',   '\m(servicio tecnico de celular|reparacion de celular|desbloqueo de celular)')
on conflict (rubro_slug, patron) do nothing;
