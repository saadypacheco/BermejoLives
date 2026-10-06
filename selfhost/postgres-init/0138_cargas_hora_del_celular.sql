-- Cargas del día (docs/cargas-del-dia.md, aprobada el 6/10/2026).
--
-- Idempotente: se puede correr dos veces.
--
-- 1) La hora del celular. `created_at` es la hora a la que la carga LLEGÓ al
--    servidor; lo cargado sin señal queda en la cola del celular y llega todo
--    junto cuando vuelve la señal. `capturado_en` es la hora real en que el
--    agente tocó «Guardar». Null en lo viejo y en lo que no es de campo: ahí la
--    hora de la carga sigue siendo `created_at`.
--
-- 2) Índices para «qué se cargó tal día»: el panel lee por rango de hora.
--    Parciales: los comercios importados no tienen agente.
--
-- Sin grants nuevos: `comercios` ya tiene el grant de tabla entera (0002) y el
-- RLS no cambia, así que la columna nueva queda con los mismos permisos.

alter table comercios add column if not exists capturado_en timestamptz;

comment on column comercios.capturado_en is
  'Hora real en que el agente de campo guardó la carga, según el reloj del celular. Distinta de created_at (hora de llegada al servidor) cuando se cargó sin señal. Null en lo anterior al 6/10/2026 y en lo que no es de campo. El backend la descarta si está fuera de [hace 7 días, dentro de 5 minutos].';

-- La consulta del panel filtra por RANGO de hora (capturado_en o created_at),
-- sin igualdad sobre el agente: un índice (cargado_por, created_at) no la
-- ayuda. Van uno por cada rama del `or`.
create index if not exists idx_comercios_campo_capturado
  on comercios (capturado_en)
  where cargado_por is not null;
create index if not exists idx_comercios_campo_created
  on comercios (created_at)
  where cargado_por is not null;
