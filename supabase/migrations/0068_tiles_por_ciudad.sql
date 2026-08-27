-- De dónde saca el mapa base cada ciudad.
--
-- POR QUÉ ES UN DATO Y NO UNA CONSTANTE
-- =====================================
--
-- El 2026-08-27 CARTO empezó a exigir API key y estampó "API key required"
-- sobre el mapa de producción. Como el proveedor estaba escrito en el código,
-- arreglarlo fue tocar ocho archivos y reconstruir el frontend. Siendo un dato,
-- habría sido un `update` de dos minutos.
--
-- Y hace falta de verdad al abrir ciudades: si mañana entra Sucre y todavía no
-- se generó su mapa propio, arranca apuntando a OpenStreetMap y funciona desde
-- el primer día; cuando el archivo esté, se cambia el dato. También permite
-- comparar en serio — una ciudad con un proveedor y otra con otro, al mismo
-- tiempo, mirando cuál carga más rápido en el celular de un agente.
--
-- NULL = la que trae el código por defecto. Es a propósito: una ciudad nueva no
-- tiene que acordarse de configurar esto para tener mapa.

alter table ciudades add column if not exists tiles_url         text;
alter table ciudades add column if not exists tiles_atribucion  text;

-- 'raster' son las imágenes ya dibujadas de siempre. 'pmtiles' es un archivo
-- único servido desde el VPS propio, que se dibuja en el navegador — la opción
-- que se va a probar en QA. Se deja preparado ahora para no volver a migrar.
alter table ciudades add column if not exists tiles_tipo text not null default 'raster'
  check (tiles_tipo in ('raster', 'pmtiles'));

comment on column ciudades.tiles_url is
  'Plantilla del mapa base para esta ciudad ({z}/{x}/{y}). NULL = la del código. '
  'Cambiarla NO requiere deploy: es el arreglo que faltó cuando CARTO cortó.';
comment on column ciudades.tiles_atribucion is
  'HTML de atribución del proveedor. Obligatorio si la licencia lo pide — '
  'OpenStreetMap lo pide.';
