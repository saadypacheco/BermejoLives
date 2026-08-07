-- 0031: miniatura (400px) de la portada del comercio, para tarjetas/mapa.
-- Evita bajar la portada de 1600px en las miniaturas chicas (clave con internet malo).
-- Se llena en la próxima subida de portada; los ya cargados caen a portada_url.
alter table comercios add column if not exists portada_thumb_url text;
