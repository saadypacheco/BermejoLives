-- Palabras que sólo significan algo acompañadas, y prefijos sin cerrar.
--
-- Sale de la §7 de supabase/auditar_diccionario.sql, que muestra el fragmento
-- que disparó cada propuesta AL LADO de lo que el comercio vende. Con las dos
-- columnas juntas los errores se leen solos:
--
--   Perfumería Arabia   → ferretería   por `led`           vende "aro de luz"
--   Comercio 5G57       → ferretería   por `pintura`       vende "esmalte de uñas"
--   Comercio 5G57       → juguetería   por `lapiz`         vende "labial"
--   MAREN IMPORTADORA   → ferretería   por `construccion`  vende "bloques de construcción"
--   Comercio W24Q       → motos        por `casco`         vende "máscara de soldar"
--   Farmacia popular    → blanquería   por `toalla`        vende "toallita higiénica"
--
-- SON DOS CLASES DE ERROR DISTINTAS
-- =================================
--
-- (a) La palabra es un MODIFICADOR, no un producto. `led` no nombra una
--     ferretería: es el adjetivo de "aro de luz LED", y todo local de
--     accesorios de celular tiene uno — cuatro de las nueve propuestas de
--     ferretería salían de ahí. Igual `pintura` (de uñas), `lapiz` (labial),
--     `construccion` (bloques de), `casco` (de soldar). Se reemplazan por la
--     forma acompañada, que es la que sí nombra el rubro: "foco led", "material
--     de construcción", "casco de moto".
--
-- (b) Al patrón le falta el cierre de palabra. `\mtoalla` matchea "toallita",
--     que es higiene y no blanquería. Es el mismo bug que `calza` → "calzado"
--     de la 0061: `\m` abre la palabra y sin `\M` el resto queda libre.
--
-- La regla que sale de las dos: un término de una sola palabra que también es
-- adjetivo o prefijo de otra cosa no alcanza para clasificar. O se lo acompaña,
-- o se lo cierra.

-- ── (a) Modificadores: van acompañados o no van ─────────────────────────────

-- `led`, `pintura` y `construccion` fuera; quedan en su forma que sí nombra una
-- ferretería. Se conservan `foco`, `luces`, `lampara` e `iluminacion` sueltos:
-- ninguno produjo un falso positivo en los 273 comercios.
delete from rubro_palabras
 where rubro_slug = 'ferreteria' and patron like '%griferia%';

insert into rubro_palabras (rubro_slug, patron) values
  ('ferreteria', '\m(ferreteria|herramienta|tornillo|clavo|cemento|caño|cano|electricidad|cable|foco|luces|iluminacion|lampara|taladro|martillo|alambre|griferia|pvc|artefacto sanitario|sanitarios\M|foco led|tira led|panel led|lampara led|material de construccion|materiales de construccion|pintura latex|pintura para pared|pintureria|pintura de obra)')
on conflict (rubro_slug, patron) do nothing;

-- Un casco suelto es tan de soldador como de motociclista, y el que apareció
-- era de soldador: el comercio vende taladro, amoladora y sierra circular.
delete from rubro_palabras
 where rubro_slug = 'motos' and patron like '%motocicleta%';

insert into rubro_palabras (rubro_slug, patron) values
  ('motos', '\m(moto\M|motos\M|motocicleta|casco de moto|casco para moto|cascos de moto|repuesto de moto)')
on conflict (rubro_slug, patron) do nothing;

-- `lapiz` solo es lápiz labial la mitad de las veces. Los dos casos que
-- aparecieron eran perfumerías.
delete from rubro_palabras
 where rubro_slug = 'jugueteria' and patron like '%papeleria%';

insert into rubro_palabras (rubro_slug, patron) values
  ('jugueteria', '\m(juguete|jugueteria|libreria|escolar|cuaderno|utiles|papeleria|\mtoy|lapices\M|lapiz negro|lapiz de color|lapiz escolar)')
on conflict (rubro_slug, patron) do nothing;

-- `masita` entró por "masa para moldear" (una juguetería) y por las galletitas
-- de un kiosco. A la panadería le quedan cinco términos que la nombran de
-- verdad, incluido `pan` ya cerrado con \M.
delete from rubro_palabras
 where rubro_slug = 'panaderia' and patron like '%bizcocho%';

-- `torta` NO se agrega acá aunque suene a panadería: ya es de `cafeteria`, y
-- repetir un término en dos rubros es el error que arregló la 0061.
insert into rubro_palabras (rubro_slug, patron) values
  ('panaderia', '\m(panaderia|\mpan\M|panes\M|factura|facturas|reposteria|bizcocho|medialuna|masa madre)')
on conflict (rubro_slug, patron) do nothing;

-- ── (b) Prefijos que hay que cerrar ─────────────────────────────────────────

-- "toallita higiénica" es una farmacia, no una blanquería. Con \M el patrón
-- distingue la toalla del toallón de la toallita.
delete from rubro_palabras
 where rubro_slug = 'blanqueria' and patron = '\mtoalla';

insert into rubro_palabras (rubro_slug, patron) values
  ('blanqueria', '\m(toalla\M|toallas\M|toallon|toallones|toalla de bano|toalla de baño|toalla de mano)')
on conflict (rubro_slug, patron) do nothing;

-- `media` abierta matchea "mediana", "mediados", "media docena". La media que
-- importa acá es la prenda.
delete from rubro_palabras
 where rubro_slug = 'lenceria' and patron = '\mmedia';

insert into rubro_palabras (rubro_slug, patron) values
  ('lenceria', '\m(media\M|medias\M|media de mujer|media deportiva|medias de)')
on conflict (rubro_slug, patron) do nothing;
