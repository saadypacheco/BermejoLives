-- Carpintería y herrería: oficios, no tiendas.
--
-- `muebles` es una mueblería —vende lo que ya está hecho— y `ferreteria` vende
-- el material. Un carpintero y un herrero hacen algo a pedido, que es otra
-- intención: no se busca igual "comprar un ropero" que "que me hagan un
-- placard a medida".
--
-- Van separados y no en un "oficios" genérico porque en Bermejo son dos
-- talleres distintos, con locales distintos, y quien busca uno no quiere el
-- otro. Un rubro que junta todos los oficios no filtra nada.

insert into rubros (slug, nombre, icono, orden, comercial) values
  ('carpinteria', '🪵 Carpintería y muebles a medida', '🪵', 49, true),
  ('herreria',    '⚒️ Herrería y metalúrgica',         '⚒️', 50, true)
on conflict (slug) do update set
  nombre = excluded.nombre, icono = excluded.icono,
  orden = excluded.orden, comercial = excluded.comercial, activo = true;

insert into rubro_palabras (rubro_slug, patron) values
  -- "madera" a secas NO va: las ferreterías y las barracas la venden, y una
  -- barraca no es una carpintería. Van el oficio y lo que sale del taller.
  ('carpinteria', '\m(carpinteria|carpintero|mueble a medida|muebles a medida|placard a medida|amoblamiento a medida|machimbre|melamina|aberturas de madera|puerta de madera|ebanisteria|aserradero)'),
  -- "hierro" tampoco: la ferretería vende hierro de construcción. Y "reja" va
  -- en plural o con contexto, porque "reja" suelto aparece en descripciones de
  -- fotos ("visto a través de una reja") — ya hay un comercio así en la base.
  ('herreria',    '\m(herreria|herrero|soldadura|soldador|metalurgica|metalmecanica|porton de hierro|portones metalicos|estructura metalica|estructuras metalicas|tornería|torneria|rejas de seguridad|barandas metalicas)')
on conflict (rubro_slug, patron) do nothing;
