-- Cuatro rubros que faltaban para poder clasificar, y limpieza de los que sobran.
--
-- Salieron de cruzar tres fuentes que coincidieron:
--
--   1. La revisión a mano de los 57 comercios de `completar_rubros.py`.
--   2. Lo que la IA venía pidiendo sola en `categoria_sugerida` (pidió
--      "lencería" por su cuenta).
--   3. Las subcategorías que ella misma escribió: 3 comercios con "lencería",
--      4 con "blanquería", 2 con "marroquinería".
--
-- Los que NO se agregan, porque ya existen con otro nombre:
--   "Bazar y Electrohogar" = bazar + electrodomesticos (dos rubros, no uno)
--   "Cotillón y Fiestas"   = regaleria
--   "Herramientas"         = ferreteria
--   "Ropa Deportiva"       = ropa + deportes
--   "Comidas"              = restaurantes / comida-rapida
--
-- Inventar un rubro que duplica a otro es peor que no tenerlo: el comprador no
-- sabe cuál tocar y los locales se reparten entre los dos.

insert into rubros (slug, nombre, icono, orden) values
  -- Hoy caen en "bolsos", que es lo mismo sólo si uno no viaja. Valijas y
  -- carteras se buscan distinto y hay locales dedicados sólo a eso.
  ('marroquineria', '🧳 Marroquinería y equipaje', 'briefcase', 30),
  -- Hoy caen en "alimentos", junto a los supermercados. Un kiosco no compite
  -- con un supermercado ni se busca igual.
  ('kiosco',        '🍬 Kiosco y golosinas',       'candy',     31),
  -- Hoy caen en "ropa" (110 comercios: un filtro que no filtra). La IA lo pidió
  -- por su cuenta en categoria_sugerida.
  ('lenceria',      '🩲 Lencería, medias y ropa interior', 'shirt', 32),
  -- El "blanco" de "Hogar, blanco y decoración" es esto, pero mezclado con
  -- decoración y muebles. Cuatro locales de Bermejo venden sólo blanquería.
  ('blanqueria',    '🛏️ Blanquería y textil de hogar', 'bed',    33)
on conflict (slug) do nothing;


-- ── El vocabulario, o los rubros nuevos no sirven de nada ────────────────────
--
-- Sin palabras en el diccionario, `rubros_sugeridos()` nunca los devuelve: no se
-- deducen del texto, no los propone la reclasificación, y quedan como cuatro
-- filtros vacíos. Los patrones van en minúsculas y SIN tildes: se comparan
-- contra unaccent(lower(...)). \m es inicio de palabra.
insert into rubro_palabras (rubro_slug, patron) values
  ('marroquineria', '\mvalija'),      ('marroquineria', '\mcartera'),
  ('marroquineria', '\mbilletera'),   ('marroquineria', '\mbandolera'),
  ('marroquineria', '\mmorral'),      ('marroquineria', '\mmarroquineria'),
  ('marroquineria', '\mbolso de viaje'), ('marroquineria', '\mrinonera'),
  ('marroquineria', '\mportafolio'),  ('marroquineria', '\mmaletin'),

  ('kiosco', '\mkiosco'),   ('kiosco', '\mkiosko'),    ('kiosco', '\mgolosina'),
  ('kiosco', '\mcaramelo'), ('kiosco', '\mchocolate'), ('kiosco', '\mgalletita'),
  ('kiosco', '\mchupetin'), ('kiosco', '\malfajor'),   ('kiosco', '\mchicle'),
  ('kiosco', '\msnack'),    ('kiosco', '\mpapas fritas'),

  ('lenceria', '\mlenceria'),  ('lenceria', '\mcorpino'),   ('lenceria', '\mbombacha'),
  ('lenceria', '\mboxer'),     ('lenceria', '\mmedia'),     ('lenceria', '\msoquete'),
  ('lenceria', '\mtanga'),     ('lenceria', '\mfaja'),      ('lenceria', '\msosten'),
  ('lenceria', '\mbrasier'),   ('lenceria', '\mcalzon'),    ('lenceria', '\mpanty'),
  ('lenceria', '\mcalzoncillo'), ('lenceria', '\mropa interior'), ('lenceria', '\mmusleras'),

  ('blanqueria', '\mblanqueria'), ('blanqueria', '\macolchado'), ('blanqueria', '\msabana'),
  ('blanqueria', '\mfrazada'),    ('blanqueria', '\mtoalla'),    ('blanqueria', '\mcubrecama'),
  ('blanqueria', '\malmohada'),   ('blanqueria', '\mmantel'),    ('blanqueria', '\medredon'),
  ('blanqueria', '\mcolcha'),     ('blanqueria', '\mcortina')
on conflict (rubro_slug, patron) do nothing;


-- ── Los que sobran ───────────────────────────────────────────────────────────
--
-- No son rubros: son ciudades argentinas y duplicados del modelo anterior a
-- URUKU. Ensucian el selector de categorías y el panel con opciones que nunca
-- van a tener un comercio.
--
-- Se DESACTIVAN en vez de borrarse: un delete se llevaría puesto cualquier
-- comercio colgando de ellos. Y la condición del final es la que importa —
-- sólo se apaga lo que NO tiene ni un comercio asignado. Si alguno resulta
-- estar en uso, se queda encendido y aparece en el informe para mirarlo a mano.
update rubros set activo = false
 where slug in (
   'la-quiaca', 'oran', 'jujuy', 'salta', 'perico', 'tucuman', 'cordoba',
   'buenos-aires',                        -- ciudades usadas como rubro
   'importadora', 'moda', 'tecnologia', 'gastronomia', 'servicios', 'mercado',
   'casa-de-cambio', 'hotel'              -- duplicados de rubros que ya existen
 )
   and not exists (
     select 1 from comercio_rubros cr where cr.rubro_id = rubros.id
   );
