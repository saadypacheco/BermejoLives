-- Fotos por plan, versión 2 (decisión del dueño, 6/11/2026; docs/fotos-por-plan.md «Cambio del 6/11/2026»).
--
-- La galería tiene 10 fotos DEL LOCAL más fotos que el comerciante puede cambiar todos los
-- días. `fotos_max` es el TOTAL (la portada va aparte y no cuenta):
--
--   gratis       0   el comerciante sólo carga la portada (el equipo de URUKU puede subir
--                    hasta 10 del local: fotos_galeria.FOTOS_DEL_LOCAL)
--   publica     60   10 del local + 50
--   destacado  130   10 del local + 120
--   pro        310   10 del local + 300
--   empleado_ia 510  10 del local + 500
--   premium (viejo): no se toca.
--
-- A diferencia de la 0144, acá SÍ se pisa el valor: es una decisión explícita.
-- La línea de fotos de /planes la arma la página con `fotos_max` (como la de la cuota),
-- así que se sacan de `incluye` las líneas que hablaban de fotos de galería.
-- Lo que ya tiene cada comercio no se borra: con menos tope, sólo no puede subir más.
-- No toca precios. Idempotente.

begin;

update planes set fotos_max = 0   where slug = 'gratis';
update planes set fotos_max = 60  where slug = 'publica';
update planes set fotos_max = 130 where slug = 'destacado';
update planes set fotos_max = 310 where slug = 'pro';
update planes set fotos_max = 510 where slug = 'empleado_ia';

update planes set
  descripcion = 'Gratis por 2 meses: tu local en el mapa con ubicación, teléfono y foto de portada. Después seguís en el mapa.',
  incluye = array[
    'Tu local en el mapa, con nombre, rubro y cómo llegar',
    'Tu teléfono para que te escriban',
    'Una foto de portada',
    'Te encuentran buscando lo que vendés'
  ]
where slug = 'gratis';

-- En los pagos, «Ficha completa: fotos, …» pasa a no prometer fotos sin número: la
-- cantidad la dice la línea que arma la página.
update planes set incluye = array_replace(incluye,
    'Ficha completa: fotos, horario, WhatsApp, qué vendés',
    'Ficha completa: horario, WhatsApp, qué vendés')
where slug in ('publica', 'destacado', 'pro', 'empleado_ia');

do $$
declare
  v record;
begin
  for v in select * from (values ('gratis', 0), ('publica', 60), ('destacado', 130), ('pro', 310), ('empleado_ia', 510)) as t(slug, n)
  loop
    if exists (select 1 from planes where slug = v.slug and fotos_max is distinct from v.n) then
      raise exception 'planes.%: fotos_max no quedó en %', v.slug, v.n;
    end if;
  end loop;
end $$;

commit;

notify pgrst, 'reload schema';
