-- Dos rubros que la ciudad tiene y la taxonomía no: salones de eventos y agro.
--
-- SALONES Y EVENTOS
-- =================
-- Hoy caían en `nocturna` (Bares, boliches y karaoke), porque su patrón incluye
-- "salon de fiesta". Es un error de bulto: quien busca un salón para un
-- casamiento o unos quince no está buscando un boliche, y quien busca dónde
-- salir de noche no quiere un salón de alquiler. Son dos búsquedas con dos
-- momentos distintos.
--
-- Y es de las cosas que se buscan UNA vez y con urgencia —hay fecha y hay
-- presupuesto—, que hoy se resuelven preguntando en un grupo de WhatsApp. Ese
-- es exactamente el hueco que este directorio llena.
--
-- `salon` solo NO va: cae dentro de "salón de belleza" y convierte cada
-- peluquería en un salón de fiestas. Todas las formas van compuestas.
--
-- AGRO Y MAQUINARIA AGRÍCOLA
-- ==========================
-- No había NADA de agro en los 56 rubros: la taxonomía es de pueblo comercial
-- —ropa, calzado, celulares, comida— y Bermejo también es zona de caña y
-- cítricos. Un repuesto de tractor caía en "Repuestos para autos" y una
-- desmalezadora en "Ferretería".
--
-- Va UNO solo y no dos (maquinaria por un lado, agroquímicos por otro). Con
-- pocos comercios, dos rubros de tres fichas cada uno se ven rotos; uno de seis
-- se ve vivo. Así aparecieron los 19 rubros vacíos que hubo que apagar en
-- agosto. Separarlo después es cambiar datos, no código.
--
-- `motosierra` y `bomba de agua` quedan AFUERA a propósito: las vende cualquier
-- ferretería —"bomba de agua" ya aparece en comercios de electrodomésticos— y
-- meterlas convertiría medio rubro de construcción en agro.
--
-- Los dos nacen posiblemente con pocos comercios. Eso se mide antes de
-- promocionarlos, con la vista previa de alcance del panel.

insert into rubros (slug, nombre, icono, orden, comercial) values
  ('salones', '🎊 Salones y eventos', '🎊', 40, true),
  ('agro',    '🚜 Agro y maquinaria agrícola', '🚜', 41, true)
on conflict (slug) do update set
  nombre = excluded.nombre,
  icono  = excluded.icono,
  activo = true;

insert into rubro_palabras (rubro_slug, patron) values
  ('salones', '\m(salon de evento|salon de eventos|salon para eventos|salon de fiesta|salon de fiestas|salon de recepciones|alquiler de salon|quincho para eventos|salon auditorio)'),
  ('agro',    '\m(maquinaria agricola|implemento agricola|insumo agricola|insumos agricolas|repuesto de tractor|tractor\M|tractores|desmalezadora|motoguadaña|motoguadana|motocultivador|fumigadora|mochila fumigadora|agroquimico|agroquimicos|herbicida|fertilizante|semilla certificada|agropecuaria|agroveterinaria)')
on conflict (rubro_slug, patron) do nothing;

-- Y sale de `nocturna`, o un salón matchearía los dos y aparecería entre los
-- boliches para siempre. Se borra el patrón viejo entero y se reescribe sin esa
-- forma: los patrones son alternancias, no filas por palabra.
delete from rubro_palabras
 where rubro_slug = 'nocturna' and patron like '%salon de fiesta%';

insert into rubro_palabras (rubro_slug, patron) values
  ('nocturna', '\m(boliche|karaoke|discoteca|restobar|resto bar|cerveceria|pub\M|bar\M|peña|pena folklorica|night club|after office)')
on conflict (rubro_slug, patron) do nothing;
