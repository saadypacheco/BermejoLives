-- 0041: polígono de la manzana/predio del lugar (Fase 2). Array JSON de puntos
-- [lat, lng] que dibujan el contorno del mercado/galería, para sombrearlo en el mapa.
alter table lugares add column if not exists poligono jsonb;
