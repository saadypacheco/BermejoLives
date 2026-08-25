-- "Usame Moda Americana" no deducía ningún rubro desde el nombre.
--
-- El diccionario tiene `ropa americana`, `fardo` y `ropa usada`, pero no la
-- forma que usa ese cartel. En la zona el mismo negocio se anuncia de tres
-- maneras —"ropa americana", "moda americana", "feria americana"— y sólo una
-- estaba escrita.
--
-- `moda` a secas NO se agrega: era uno de los 19 rubros apagados en la 0057 por
-- duplicar a `ropa`, y como palabra suelta entra en cualquier boutique. Va la
-- forma completa, que es la que nombra el negocio de ropa usada de frontera.

delete from rubro_palabras
 where rubro_slug = 'ropa-americana' and patron like '%fardo%';

insert into rubro_palabras (rubro_slug, patron) values
  ('ropa-americana', '\m(ropa americana|moda americana|feria americana|ropas? de fardo|fardo|ropa usada|indumentaria americana|ropa de segunda mano)')
on conflict (rubro_slug, patron) do nothing;
