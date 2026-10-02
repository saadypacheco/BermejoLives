-- LO QUE SE CARGA EN LA SEGUNDA PASADA
--
-- El alta de la calle es rápida a propósito: foto, GPS, rubro y poco más. El
-- resto —lo que convierte un punto en el mapa en un comercio que sirve— se
-- carga en una segunda visita, con el dueño presente y con tiempo.
--
-- Para eso ya existían `whatsapp`, `telefono`, `email`, `instagram_url`,
-- `facebook_url`, `tiktok_url` y `sitio_web`. Faltaban dos cosas que los
-- comerciantes de Bermejo sí tienen y hoy no se podían anotar:

alter table comercios add column if not exists canal_wa_url text;
comment on column comercios.canal_wa_url is
  'El canal o la comunidad de WhatsApp DEL COMERCIO, donde él publica sus ofertas. No es el de URUKU: es el suyo, y es a donde se manda al comprador que quiere enterarse primero.';

alter table comercios add column if not exists catalogo_url text;
comment on column comercios.catalogo_url is
  'Dónde está su catálogo: un PDF, una carpeta de Drive, una tienda. Muchos mayoristas ya tienen uno armado y lo mandan por WhatsApp — enlazarlo cuesta nada y es lo que más mira el que compra por mayor.';
