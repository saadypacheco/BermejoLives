-- Texto del plan gratis (decisión del dueño, 6/11/2026): se saca «Después seguís en el
-- mapa». La línea de la cuota de publicaciones del gratis ya no la muestra /planes
-- (lib/planes-pure.lineaCuota); la cuota sigue rigiendo igual. Idempotente.

begin;

update planes set
  descripcion = 'Gratis por 2 meses: tu local en el mapa con ubicación, teléfono y foto de portada.'
where slug = 'gratis';

commit;

notify pgrst, 'reload schema';
