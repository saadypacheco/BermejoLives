-- Que un local llamado "kiosko" quede clasificado como kiosco, se escriba como
-- se escriba.
--
-- El mapa de kioscos vale por sí solo: son los comercios más repartidos por la
-- ciudad, los que están abiertos cuando no hay nada más, y los que alguien busca
-- estando parado en la vereda. Un directorio de Bermejo sin ellos tiene un hueco
-- que se nota.
--
-- El nombre YA se clasifica —`rubros_sugeridos()` recibe nombre + subcategoría +
-- productos + sinónimos, y "kiosco"/"kiosko" ya estaban— pero sólo esas dos
-- formas. Faltan las que se ven en los carteles:
--
--   "quiosco"   la grafía del diccionario, la usa quien escribe con cuidado
--   "kiosquito" / "kioskito"   muy común en el cartel de un local chico
--   "kiosqueria"               aparece en la zona
--
-- Sin ellas, "El Kiosquito de Ana" no clasificaba como kiosco, que es
-- exactamente el caso más frecuente.
--
-- Van con \m (inicio de palabra) y no ancladas al final, así "kiosco",
-- "kioscos" y "kiosquito" entran con el mismo patrón. Y se comparan contra el
-- texto sin tildes y en minúsculas, así que "KIOSKO" también.

insert into rubro_palabras (rubro_slug, patron) values
  ('kiosco', '\m(quiosco|quiosko|kiosqu|kiosqui|kioski|kiosker|quiosqu)')
on conflict (rubro_slug, patron) do nothing;
