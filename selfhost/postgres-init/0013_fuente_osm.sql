-- 0013_fuente_osm: trazabilidad de origen por comercio
-- fuente: 'campo', 'osm', 'autoregistro', 'whatsapp', 'manual'
-- cargado_por: email del agente/usuario que lo registró
alter table comercios add column if not exists fuente      text;
alter table comercios add column if not exists cargado_por text;

create index if not exists idx_comercios_fuente      on comercios (fuente)      where activo;
create index if not exists idx_comercios_cargado_por on comercios (cargado_por) where activo;
