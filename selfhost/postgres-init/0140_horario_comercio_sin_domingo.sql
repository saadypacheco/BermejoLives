-- El atajo «Comercio · 8-12 y 14:30-20» de Calles y horarios (admin-calles.tsx)
-- guardaba «Lun a Sáb 8-12 · 14:30-20». El sitio parte el horario en tramos por
-- «·»; el de la tarde quedaba sin días y un tramo sin días vale para TODOS: la
-- ficha decía «Abierto» el domingo de 14:30 a 20. Se reescribe al formato que
-- usa el editor de horario (los dos turnos con «y», en el mismo tramo).
--
-- Sólo el texto exacto del atajo: un horario escrito a mano no se toca.
-- Idempotente: la segunda vez no encuentra nada que cambiar.

update comercios
   set horario = 'Lun-Sáb 8:00-12:00 y 14:30-20:00'
 where horario = 'Lun a Sáb 8-12 · 14:30-20';
