-- La casilla «El dueño aceptó aparecer en URUKU» del alta del agente.
--
-- Hasta acá el formulario la mandaba y el backend sólo la escribía en el log:
-- si alguien preguntaba si un comercio había aceptado aparecer, no había
-- registro. Ahora se guarda con la hora. NULL = comercio cargado antes de esto
-- (o por otra vía): no se sabe.
--
-- PRIVADAS para anon/authenticated (AGENTS.md, regla 11): no se dan grants.

begin;

alter table public.comercios add column if not exists consentimiento_dueno boolean;
alter table public.comercios add column if not exists consentimiento_dueno_en timestamptz;

comment on column public.comercios.consentimiento_dueno is
  'El dueño aceptó aparecer en URUKU (casilla del alta del agente). NULL = sin dato.';
comment on column public.comercios.consentimiento_dueno_en is
  'Cuándo se registró consentimiento_dueno.';

commit;

notify pgrst, 'reload schema';
