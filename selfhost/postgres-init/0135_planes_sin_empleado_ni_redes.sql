-- Los planes, sin Empleado Digital y sin prometer las redes de URUKU.
--
-- Decisión del usuario del 5/10/2026, «de momento»:
--
-- 1) EMPLEADO DIGITAL SE OCULTA. No se borra (soft-delete, regla del
--    proyecto): `visible = false` lo saca de /planes, del asistente y del
--    «pasá al plan de arriba» del aviso de cuota (`plan_siguiente` sólo mira
--    los visibles). Hoy no hay ningún comercio en ese plan. Volver a mostrarlo
--    es un tilde en Admin › Planes.
--
-- 2) LOS PLANES NO MENCIONAN LAS REDES DE URUKU. Se saca de los textos que ve
--    el comerciante. La función `redes` del plan queda como está: decide qué
--    se encola para Facebook e Instagram, y eso no sale solo (alguien aprieta
--    el botón en Difusión). Se revisa más adelante, junto con el tope de posts
--    por plan.
--
-- Sólo cambia lo que dice cada plan. Si alguien ya editó estos textos en
-- Admin › Planes, esta migración los pisa: es a propósito, son los que
-- prometían las redes.

update planes set visible = false where slug = 'empleado_ia';

update planes set
  descripcion = 'Tu negocio digitalizado y destacado en los resultados.',
  incluye = array['Todo lo de Publica', 'Lugar destacado en los resultados']
where slug = 'destacado';
