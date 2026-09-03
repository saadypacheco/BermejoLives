-- URUKU deja de ser un directorio de COMERCIOS y pasa a ser uno de la CIUDAD.
--
-- La diferencia no es de nombre. Un baño público, una parada de taxis o la
-- oficina de migración no tienen WhatsApp, ni productos, ni dueño a quien
-- venderle un plan. Cargados como están hoy los comercios, quedarían marcados
-- "sin contacto · sin productos" para siempre —ensuciando la cola que sirve
-- para saber qué falta— y su tarjeta ofrecería "Ver ofertas" a un baño.
--
-- Por eso la bandera va en el RUBRO y no en cada ficha: lo que decide si algo
-- es comercial no es el local, es qué clase de cosa es. Puesta acá, alcanza con
-- clasificar bien para que todo lo demás se acomode.

alter table rubros add column if not exists comercial boolean not null default true;

comment on column rubros.comercial is
  'false = punto de la ciudad, no negocio (baños, taxis, trámites). No entra a '
  'la cola de incompletos por no tener WhatsApp ni productos, no aparece en '
  'suscripciones, y su ficha muestra "Cómo llegar" en vez de "Ver ofertas". '
  'Sí aparece en el mapa y en el buscador, que es todo el punto.';

insert into rubros (slug, nombre, icono, orden, comercial) values
  ('taller-mecanico', '🔧 Taller mecánico',  '🔧', 45, true),
  ('taxis',           '🚕 Taxis y movilidad', '🚕', 46, true),
  ('banos',           '🚻 Baños públicos',    '🚻', 47, false)
on conflict (slug) do update set
  nombre = excluded.nombre, icono = excluded.icono,
  orden = excluded.orden, comercial = excluded.comercial, activo = true;

-- El taller es un SERVICIO y `repuestos-autos` es una tienda: hoy caían juntos
-- porque comparten vocabulario ("filtro", "batería"). Las palabras de acá son
-- las del trabajo, no las de la mercadería.
insert into rubro_palabras (rubro_slug, patron) values
  ('taller-mecanico', '\m(taller mecanico|mecanica|mecanico|chapa y pintura|chapista|alineacion|balanceo|scanner automotor|electricidad del automotor|service del auto|cambio de aceite)'),
  ('taxis',           '\m(taxi|radio taxi|radiotaxi|movilidad|trufi|remis|parada de taxi)'),
  -- "baño" a secas NO va: aparece en cualquier ferretería o bazar (artefactos
  -- de baño, toallas de baño, alfombra de baño). Sólo las formas que nombran
  -- el servicio.
  ('banos',           '\m(bano publico|banos publicos|sanitario publico|servicio higienico|toilette publico)')
on conflict (rubro_slug, patron) do nothing;
