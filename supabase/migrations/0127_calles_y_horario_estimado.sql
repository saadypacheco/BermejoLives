-- LA CALLE Y EL HORARIO ESTIMADO
--
-- De 1.248 comercios activos, 1.247 no tienen dirección y 1.246 no tienen
-- horario. No es que estén mal cargados: en Bermejo un puesto no tiene altura
-- de calle y el agente no va a tipear mil direcciones. Pero los 1.248 SÍ
-- tienen GPS, así que la calle se puede deducir del punto (ver
-- backend/scripts/calles-desde-osm.py, que la saca de OpenStreetMap y deja
-- 1.247 de 1.248 sobre una calle con nombre).
--
-- Con la calle puesta, el horario deja de cargarse de a uno: la 23 de Marzo
-- son 139 comercios y la mayoría son mayoristas de ropa que abren de 6 a 16.
-- Se elige la calle, se eligen los rubros y se pone el horario a los 139.
--
-- Pero un horario puesto por lote NO es un horario confirmado, y la
-- diferencia importa: alguien que cruzó el puente y maneja veinte cuadras
-- porque URUKU dijo "abierto" no perdona. Por eso `horario_estimado`: la
-- ficha lo muestra como lo que es —"horario habitual de la calle, confirmá
-- antes de ir"— hasta que alguien lo confirme en la visita.

alter table comercios add column if not exists calle text;
comment on column comercios.calle is
  'Calle deducida del GPS contra OpenStreetMap. NO es la dirección (esa la tipea una persona y va en `direccion`): es para agrupar y para decir dónde queda cuando no hay altura.';

alter table comercios add column if not exists horario_estimado boolean not null default false;
comment on column comercios.horario_estimado is
  'true = el horario se puso por lote (el habitual de la calle o del rubro), no lo confirmó nadie en el local. La ficha lo aclara. Al confirmarlo en una visita, se apaga.';

create index if not exists idx_comercios_calle on comercios (calle);

-- ------------------------------------------------------------------
-- De paso, `zonas` sin ciudad. Hoy la tabla está VACÍA, así que no rompe
-- nada; el día que se cargue una zona de Bermejo y Santa Cruz esté andando,
-- las zonas de acá aparecerían allá. Se arregla ahora que es gratis.
alter table zonas add column if not exists ciudad_id uuid references ciudades(id) on delete cascade;
comment on column zonas.ciudad_id is 'Una zona es de una ciudad. NULL sólo por compatibilidad con filas viejas; las nuevas la llevan.';
create index if not exists idx_zonas_ciudad on zonas (ciudad_id);
