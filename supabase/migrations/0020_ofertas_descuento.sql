-- 0020: Campos de oferta para los badges del feed.
--   descuento_pct → porcentaje de descuento (1..99) para el badge "-20%"
--   vence_el      → fecha de vencimiento para "Válido hasta DD/MM"
-- Ambos opcionales: si están nulos, la UI muestra solo precio (degradación suave).

alter table publicaciones
  add column if not exists descuento_pct smallint check (descuento_pct between 1 and 99),
  add column if not exists vence_el      date;

-- Refrescar la vista pública del feed para exponer los nuevos campos.
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
    p.vence_el
  from publicaciones p
  join comercios c on c.id = p.comercio_id and c.activo
  left join zonas z on z.id = c.zona_id
  left join rubros r on r.id = c.rubro_id
  where p.estado = 'aprobado' and p.activo
  order by p.approved_at desc nulls last;
