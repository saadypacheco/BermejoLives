-- El feed público lleva la ciudad del comercio.
--
-- Con dos ciudades más por cargar (22/9/2026), el home de Santa Cruz
-- mostraba las ofertas de Bermejo: `feed_publico` no decía de qué ciudad
-- era cada publicación. Se agrega `ciudad_slug` al final de la vista (así
-- `create or replace` la acepta) y el sitio filtra por la ciudad elegida.
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
    coalesce(nullif(p.contacto_whatsapp, ''), c.whatsapp) as contacto_whatsapp,
    (nullif(p.contacto_whatsapp, '') is not null)         as contacto_es_uruku,
    ci.slug as ciudad_slug
  from publicaciones p
  join comercios c on c.id = p.comercio_id and c.activo
  left join zonas z on z.id = c.zona_id
  left join rubros r on r.id = c.rubro_id
  left join ciudades ci on ci.id = c.ciudad_id
  where p.estado = 'aprobado' and p.activo
  order by p.approved_at desc nulls last;

grant select on feed_publico to anon, authenticated;
