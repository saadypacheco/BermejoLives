-- 0142: «Talles especiales» en la ficha del comercio.
--
-- Para quien busca ropa o calzado en talles que no se consiguen en cualquier
-- lado (grandes, muy chicos): la ficha muestra el sello «Talles especiales»,
-- como el de «Tiene pasero» (0141). Sólo sí o no: el detalle se pregunta por
-- WhatsApp.
--
-- `comercios` ya tiene grant de tabla entera (0002). Idempotente.

alter table comercios
  add column if not exists talles_especiales boolean not null default false;

comment on column comercios.talles_especiales is
  'El local trabaja con talles especiales (grandes, muy chicos). La ficha muestra '
  'el sello «Talles especiales». Lo carga el comerciante en Mi comercio o el '
  'agente en Completar comercio.';

notify pgrst, 'reload schema';
