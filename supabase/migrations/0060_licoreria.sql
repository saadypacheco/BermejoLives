-- Que "licorería" se encuentre buscando esa palabra.
--
-- El término ya clasificaba: `licor` está en el diccionario desde la 0045 y el
-- patrón es por inicio de palabra, así que "licorería" cae en 🥤 Bebidas.
--
-- Lo que faltaba es lo otro: buscar "licorería" en el sitio no devolvía la
-- categoría, porque el buscador matchea también contra el NOMBRE del rubro y
-- ese nombre no dice licorería en ningún lado. Un rubro que contiene algo pero
-- no lo nombra es invisible para quien busca esa palabra.
--
-- NO se crea un rubro aparte todavía. "Bebidas" tiene 4 comercios: partir en dos
-- una categoría de cuatro deja dos que no filtran nada. Si la salida de campo
-- trae varias licorerías de verdad, se separa entonces — con el dato a la vista
-- en vez de por anticipado.
update rubros
   set nombre = '🥤 Bebidas y licorería'
 where slug = 'bebidas' and nombre <> '🥤 Bebidas y licorería';

-- Las formas que aparecen en los carteles de la zona.
insert into rubro_palabras (rubro_slug, patron) values
  ('bebidas', '\m(licoreria|licoreria|distribuidora de bebida|bebida alcoholica)'),
  ('bebidas', '\m(fernet|ron\M|vodka|singani|whiskeria|champagne|espumante)')
on conflict (rubro_slug, patron) do nothing;
