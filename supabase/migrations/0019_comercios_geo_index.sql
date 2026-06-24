-- ============================================================
-- Encontralo · 0019_comercios_geo_index
-- Índice para el mapa de la Home: busca comercios activos por bounding box
-- (lat/lng) alrededor de Bermejo. Sin esto, con el import OSM (~44k filas) la
-- query hace Seq Scan (~1.9s por carga de la Home).
-- ============================================================

create index if not exists idx_comercios_geo
  on comercios (lat, lng)
  where activo and lat is not null;
