-- La Comunidad de WhatsApp de los compradores: el enlace vive en
-- `redes_sociales` (clave `comunidad`) y se carga desde /contenido, como
-- las demás redes. Hasta que tenga URL, el botón «Unite a la comunidad»
-- no aparece en el sitio y /comunidad dice que está por abrirse.
--
-- Nadie es agregado a la comunidad: entra el que toca el enlace. Es la
-- única forma que WhatsApp no castiga, y la base de compradores (0117)
-- sirve para saber a qué administradores de grupo darles el enlace.
insert into redes_sociales (clave, etiqueta, orden) values
  ('comunidad', 'Comunidad de WhatsApp', 6)
on conflict (clave) do nothing;
