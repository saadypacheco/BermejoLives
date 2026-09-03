-- El sembrado de la 0079 se duplicó: 16 filas donde tenían que haber 8.
--
-- La causa es un `on conflict do nothing` sobre una tabla SIN ninguna
-- restricción única. Esa cláusula no falla, no avisa y no hace nada: como no
-- hay conflicto posible, cada corrida inserta las ocho filas de nuevo. Escrita
-- así parece que protege, y era decorativa.
--
-- Es exactamente la misma familia de error que venimos cazando toda la semana:
-- algo que se lee como una guarda y no guarda nada. Un `.limit()` que corta sin
-- avisar, un placeholder que normaliza a basura, un guard que compara unidades
-- distintas. Acá el síntoma es un panel de alertas con todo repetido, que es la
-- forma más rápida de que se deje de mirar.

-- 1. Sacar los duplicados, quedándose con el más viejo de cada nombre: es el
--    que puede tener datos cargados a mano encima.
delete from vencimientos v
 using vencimientos otro
 where v.nombre = otro.nombre
   and v.created_at > otro.created_at;

-- Empate exacto de created_at (las ocho del seed entran en la misma
-- transacción): se desempata por id para no dejar ninguna pareja en pie.
delete from vencimientos v
 using vencimientos otro
 where v.nombre = otro.nombre
   and v.created_at = otro.created_at
   and v.id > otro.id;

-- 2. Que no pueda volver a pasar. Ahora el `on conflict` de la 0079 tiene sobre
--    qué colisionar y hace lo que decía hacer.
create unique index if not exists idx_vencimientos_nombre on vencimientos (nombre);
