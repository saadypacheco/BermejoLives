-- Una palabra con tilde en el diccionario no clasifica a nadie. Nunca.
--
-- CÓMO APARECIÓ
-- =============
-- El verificador del buscador listó las palabras que no traen ningún comercio.
-- Entre ellas, `peña` en Bares y boliches. Una peña en Bermejo no es una
-- rareza: es un rubro que existe y que la gente busca. Que no traiga NADA no
-- podía ser "no hay ninguna".
--
-- El motivo está en `rubros_sugeridos`:
--
--     unaccent(lower(p_texto)) ~ rp.patron
--
-- El TEXTO se desacentúa antes de comparar. El PATRÓN no. Así que "Peña El
-- Ceibo" llega como "pena el ceibo" y el patrón busca "peña": no coinciden, y
-- no coinciden jamás, con ningún texto, en ninguna ciudad.
--
-- Es la forma cara de fallar otra vez: no da error, no aparece en ningún log,
-- la palabra está escrita en la tabla y el panel la muestra. Todo se ve bien y
-- clasifica cero.
--
-- QUÉ SE ENCONTRÓ
-- ===============
-- Diez alternativas con tilde o ñ. Ocho vienen con su gemela sin tilde al lado
-- —`riñonera|rinonera`, `pañal|panal`, `salteña|saltena`— y ahí la acentuada
-- sobra pero no rompe: la gemela hace el trabajo. Igual se van, porque una
-- palabra que no puede funcionar en una lista de palabras que sí funcionan es
-- una trampa para el próximo que la lea.
--
-- Las dos que estaban SOLAS son las que costaban:
--
--   nocturna    peña   → `pena\M`, con los dos bordes de palabra para no
--                        agarrar "penal" ni "penado". El texto que clasifica ya
--                        no incluye descripciones libres (0091), así que el
--                        riesgo de que aparezca "pena" suelta es bajo.
--   peluqueria  uñas   → no se puede poner `unas` solo: es "unas" y matchearía
--                        media ciudad. Van las formas compuestas, que es la
--                        regla de siempre: `esmalte de unas`, `unas postizas`.
--
-- Los borrados van por un fragmento ASCII de cada patrón y no por la palabra
-- acentuada: un `like '%peña%'` dentro de este archivo depende de que el
-- encoding del cliente psql coincida, y ése es justo el tipo de detalle que
-- falla en silencio en un servidor y no en la máquina donde se escribió.
--
-- La guarda está en test_diccionario_rubros.py: ningún patrón puede llevar
-- tildes ni ñ.

-- ── las dos que estaban solas ────────────────────────────────────────────────
delete from rubro_palabras where rubro_slug = 'nocturna' and patron like '%night club%';
insert into rubro_palabras (rubro_slug, patron) values
  ('nocturna', '\m(boliche|karaoke|discoteca|restobar|resto bar|cerveceria|pub\M|bar\M|pena\M|pena folklorica|night club|after office)')
on conflict (rubro_slug, patron) do nothing;

delete from rubro_palabras where rubro_slug = 'peluqueria' and patron like '%unas esculpidas%';
insert into rubro_palabras (rubro_slug, patron) values
  ('peluqueria', '\m(peluqueria|barberia|corte de pelo|salon de belleza|manicura|pedicura|unas esculpidas|unas postizas|esmalte de unas)')
on conflict (rubro_slug, patron) do nothing;

-- ── las ocho que tenían gemela: se van las acentuadas ────────────────────────
delete from rubro_palabras where rubro_slug = 'agro' and patron like '%maquinaria agricola%';
insert into rubro_palabras (rubro_slug, patron) values
  ('agro', '\m(maquinaria agricola|implemento agricola|insumo agricola|insumos agricolas|repuesto de tractor|tractor\M|tractores|desmalezadora|motoguadana|motocultivador|fumigadora|mochila fumigadora|agroquimico|agroquimicos|herbicida|fertilizante|semilla certificada|agropecuaria|agroveterinaria)')
on conflict (rubro_slug, patron) do nothing;

delete from rubro_palabras where rubro_slug = 'bazar' and patron like '%articulo de plastico%';
insert into rubro_palabras (rubro_slug, patron) values
  ('bazar', '\m(articulo de plastico|articulos de plastico|plastiqueria)')
on conflict (rubro_slug, patron) do nothing;

delete from rubro_palabras where rubro_slug = 'bebes' and patron like '%cochecito%';
insert into rubro_palabras (rubro_slug, patron) values
  ('bebes', '\m(bebe|bebes|panal|cochecito|mamadera|chupete)')
on conflict (rubro_slug, patron) do nothing;

delete from rubro_palabras where rubro_slug = 'blanqueria' and patron like '%toallon%';
insert into rubro_palabras (rubro_slug, patron) values
  ('blanqueria', '\m(toalla\M|toallas\M|toallon|toallones|toalla de bano|toalla de mano)')
on conflict (rubro_slug, patron) do nothing;

delete from rubro_palabras where rubro_slug = 'comida-rapida' and patron like '%broaster%';
insert into rubro_palabras (rubro_slug, patron) values
  ('comida-rapida', '\m(hamburguesa|saltena|empanada|pizza|lomito|rotiseria|sandwich|choripan|papas fritas|pollo frito|broaster)')
on conflict (rubro_slug, patron) do nothing;

delete from rubro_palabras where rubro_slug = 'ferreteria' and patron like '%pintureria%';
insert into rubro_palabras (rubro_slug, patron) values
  ('ferreteria', '\m(ferreteria|herramienta|tornillo|clavo|cemento|cano|electricidad|cable|foco|luces|iluminacion|lampara|taladro|martillo|alambre|griferia|pvc|artefacto sanitario|sanitarios\M|foco led|tira led|panel led|lampara led|material de construccion|materiales de construccion|pintura latex|pintura para pared|pintureria|pintura de obra)')
on conflict (rubro_slug, patron) do nothing;

delete from rubro_palabras where rubro_slug = 'herreria' and patron like '%barandas metalicas%';
insert into rubro_palabras (rubro_slug, patron) values
  ('herreria', '\m(herreria|herrero|soldadura|soldador|metalurgica|metalmecanica|porton de hierro|portones metalicos|estructura metalica|estructuras metalicas|torneria|rejas de seguridad|barandas metalicas)')
on conflict (rubro_slug, patron) do nothing;

delete from rubro_palabras where rubro_slug = 'regaleria' and patron like '%cotillon%';
insert into rubro_palabras (rubro_slug, patron) values
  ('regaleria', '\m(regalo|regaleria|cotillon|globo|souvenir|pinata|adorno)')
on conflict (rubro_slug, patron) do nothing;
