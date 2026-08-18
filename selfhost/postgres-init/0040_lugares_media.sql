-- 0040: portada + video de recorrido para los lugares (mercados/galerías/plazas).
-- El agente, parado en el lugar, saca la foto de portada y graba un video de recorrido.
alter table lugares add column if not exists portada_url       text;
alter table lugares add column if not exists portada_thumb_url text;
alter table lugares add column if not exists video_url         text;
