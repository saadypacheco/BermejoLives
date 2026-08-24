-- Separar el kiosco de la comida rápida, y reconocer cómo se dice acá.
--
-- Al crear el rubro "kiosco" le puse "papas fritas" como palabra, y eso ya
-- pertenece a comida rápida. El resultado: "Sandwich dioni" entraba a kiosco por
-- las papas fritas y no por vender golosinas.
--
-- Da la casualidad de que ESE local sí es un kiosco —vende sándwiches afuera de
-- su propio kiosco— así que el resultado era correcto y la razón no. Es la peor
-- combinación posible: una regla mal puesta que no se nota porque acertó una
-- vez, y que a la próxima rotisería la manda a kiosco sin que nadie lo revise.
--
-- Un kiosco se reconoce por lo que vende un kiosco: golosinas, chocolates,
-- galletitas, cigarrillos, recargas. Las papas fritas de un sanguchero son
-- una guarnición.

delete from rubro_palabras
 where rubro_slug = 'kiosco' and patron in ('\mpapas fritas', '\msnack');

-- "sanguche" y "sanguchería" son como se dice y se escribe en la zona, y la IA
-- ya las devolvió como sinónimos al analizar las vidrieras. El patrón viejo sólo
-- tenía "sandwich", así que "Sangucheria El Paso" no clasificaba como comida.
insert into rubro_palabras (rubro_slug, patron) values
  ('comida-rapida', '\m(sanguche|sangucheria|sandwicheria|panchos|super pancho)'),
  ('comida-rapida', '\m(milanesa|papa frita|pancho)'),

  -- Lo que sí distingue a un kiosco.
  ('kiosco', '\mcigarrillo'),  ('kiosco', '\mrecarga'),
  ('kiosco', '\mgaseosa fria'), ('kiosco', '\mturron'),
  ('kiosco', '\mchupetin'),     ('kiosco', '\mgomita')
on conflict (rubro_slug, patron) do nothing;
