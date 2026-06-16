-- 0013_fuente_osm: columna fuente en comercios para trackear origen de importación
alter table comercios add column if not exists fuente text;
create index if not exists idx_comercios_fuente on comercios (fuente) where activo;
