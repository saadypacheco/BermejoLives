-- El explorador: URUKU sale a fotografiar ofertas de locales que todavía no
-- publican.
--
-- El problema que resuelve: hay 813 comercios cargados y UNA publicación.
-- Esperar a que los comerciantes empiecen a mandar fotos es esperar sentado.
-- Igual que el mapa se llenó caminando, el feed se llena caminando.
--
-- La decisión que ordena todo esto: **la oferta se publica a nombre del
-- comercio REAL, no de un comercio ficticio de URUKU.** Un feed de ofertas
-- firmadas por "URUKU Ofertas" le saca al comprador lo único que esta
-- plataforma tiene y las otras no: dónde queda, si está abierto, a cuántas
-- cuadras. Y publicar la foto y el precio de un local bajo otro nombre le deja
-- el reclamo al comerciante el día que el precio cambie.
--
-- Lo que sí cambia es a quién le escribe el comprador: mientras el comercio no
-- se haya sumado, el contacto va al número explorador. Por eso `contacto_whatsapp`
-- vive en la publicación y no se calcula al vuelo.

alter table publicaciones
  add column if not exists contacto_whatsapp text;

comment on column publicaciones.contacto_whatsapp is
  'A quién le escribe el comprador por ESTA oferta. NULL = al comercio, como '
  'siempre. Con valor = a ese número (el explorador). Se guarda acá y no se '
  'deduce de una config: el día que el comercio se suma hay que poder pasar '
  'sus ofertas a su WhatsApp sin tocar las de los demás, y las publicaciones '
  'viejas tienen que seguir diciendo a dónde fueron sus consultas.';

-- 'explorador' se suma a los orígenes. La restricción se rehace entera porque
-- Postgres no sabe extender un check.
alter table publicaciones drop constraint if exists publicaciones_origen_check;
alter table publicaciones
  add constraint publicaciones_origen_check
  check (origen in ('whatsapp', 'panel', 'explorador'));

-- La vista expone el contacto ya resuelto: la pantalla no tiene por qué saber
-- que existe un explorador, sólo a qué número mandar el mensaje. `origen` va
-- también, para poder decir en la ficha de dónde salió la foto.
-- (CREATE OR REPLACE exige no reordenar columnas existentes: se agregan AL FINAL.)
create or replace view feed_publico as
  select
    p.id, p.tipo, p.titulo, p.descripcion, p.precio, p.moneda,
    p.imagen_url, p.tiktok_url, p.approved_at, p.created_at,
    c.id   as comercio_id,
    c.slug as comercio_slug,
    c.nombre as comercio_nombre,
    c.logo_url as comercio_logo,
    c.whatsapp as comercio_whatsapp,
    c.verificado as comercio_verificado,
    z.nombre as zona_nombre,
    c.modalidad as comercio_modalidad,
    r.nombre as rubro_nombre,
    r.slug as rubro_slug,
    p.descuento_pct,
    p.vence_el,
    p.origen,
    -- Si la publicación trae contacto propio manda ése; si no, el del comercio.
    coalesce(nullif(p.contacto_whatsapp, ''), c.whatsapp) as contacto_whatsapp,
    (nullif(p.contacto_whatsapp, '') is not null)         as contacto_es_uruku
  from publicaciones p
  join comercios c on c.id = p.comercio_id and c.activo
  left join zonas z on z.id = c.zona_id
  left join rubros r on r.id = c.rubro_id
  where p.estado = 'aprobado' and p.activo
  order by p.approved_at desc nulls last;

grant select on feed_publico to anon, authenticated;
