-- 0141: «Tiene pasero» en la ficha del comercio.
--
-- En Bermejo, el pasero es quien le cruza la compra al comprador. Los locales lo
-- avisan con un cartel; la ficha lo muestra igual, como un dato más de «Lo que
-- suma». Se indica sólo si el local lo tiene: no se dice quién es ni cuánto cobra.
--
-- `comercios` ya tiene grant de tabla entera (0002): la ficha lo lee con anon
-- sin tocar permisos. Idempotente: se puede correr dos veces.

alter table comercios
  add column if not exists tiene_pasero boolean not null default false;

comment on column comercios.tiene_pasero is
  'El local tiene pasero (quien le cruza la compra al comprador). La ficha muestra '
  'el sello «Tiene pasero»; no se guarda quién es. Lo carga el comerciante en Mi '
  'comercio o el agente en Completar comercio.';

notify pgrst, 'reload schema';
