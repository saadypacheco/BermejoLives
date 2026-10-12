-- El publicador corrige fichas de comercios (docs/portada-y-permisos.md, decisión 2).
--
-- Hasta hoy el rol `publicador` tenía `contenido` y `moderar`. Veía la sección
-- Negocios, abría el modal «Editar negocio» y «Guardar cambios» le daba 403,
-- porque editar una ficha pide `comercios.editar`. Se le suma ese permiso.
--
-- Sólo toca la fila del rol `publicador` de la tabla `roles` (0126):
--   - suma `comercios.editar` a `permisos` sin duplicarlo (idempotente);
--   - si alguien ya lo había agregado desde Equipo, no cambia nada;
--   - el resto de sus permisos queda como estaba (no se pisan ajustes hechos en el panel);
--   - NO prende un rol que el admin vació a propósito: un rol sin permisos es un rol
--     apagado (`permisos_de` distingue «lista vacía» de «sin lista»), y sumarle
--     `comercios.editar` lo habría vuelto a encender con un solo permiso;
--   - la descripción sólo se cambia si sigue siendo la vieja: si alguien la editó desde
--     Equipo, no se la pisa.
-- Es un cambio de datos, no de esquema: no hace falta recargar PostgREST.

update roles
   set permisos = array_append(permisos, 'comercios.editar')
 where slug = 'publicador'
   and cardinality(permisos) > 0
   and not ('comercios.editar' = any(permisos));

update roles
   set descripcion = 'Carga la cotización, el estado del paso y los videos, y corrige fichas.'
 where slug = 'publicador'
   and descripcion = 'Carga la cotización, el estado del paso y los videos.';
