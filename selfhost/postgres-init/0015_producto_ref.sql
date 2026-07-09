-- ============================================================
-- Bermejo Live Market · 0015_producto_ref
-- Puente buscadonde <-> ecommerce.
-- El comercio carga/gestiona sus productos DESDE buscadonde, pero el
-- producto vive en la base del ecommerce (reusa buscador/filtros/carrito).
-- buscadonde solo guarda la REFERENCIA + metadatos propios (quién lo cargó,
-- fechas, estado, link al destacado pago) para no tocar el ecommerce.
--   Ecommerce: tabla productos gana una columna `vendedor_id` (= comercio_id).
--   buscadonde: esta tabla `producto_ref`.
-- ============================================================

create table if not exists producto_ref (
  id                 uuid        primary key default gen_random_uuid(),
  comercio_id        uuid        not null references comercios(id) on delete cascade,
  tienda_producto_id text,                 -- id del producto en el ecommerce (null hasta sincronizar)
  url                text,                 -- link directo a la ficha en el ecommerce
  -- cache de display (la fuente de verdad del producto es el ecommerce):
  titulo             text,
  precio             numeric(12,2),
  moneda             text,
  estado             text        not null default 'borrador',  -- 'borrador'|'publicado'|'error'|'archivado'
  cargado_por        text,                 -- email/usuario que lo cargó desde buscadonde
  destacado_pub_id   uuid        references publicaciones(id) on delete set null,  -- si pagó destacar 1 foto en el feed
  notas              text,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

create index if not exists idx_producto_ref_comercio on producto_ref (comercio_id);
create unique index if not exists uq_producto_ref_tienda
  on producto_ref (tienda_producto_id) where tienda_producto_id is not null;

-- mantiene updated_at al día
create or replace function touch_producto_ref() returns trigger
language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
drop trigger if exists trg_touch_producto_ref on producto_ref;
create trigger trg_touch_producto_ref before update on producto_ref
  for each row execute function touch_producto_ref();

-- RLS: solo el backend (service_role) opera esta tabla; nunca el cliente directo.
grant all on producto_ref to service_role;
alter table producto_ref enable row level security;
drop policy if exists producto_ref_service_all on producto_ref;
create policy producto_ref_service_all on producto_ref
  for all to service_role using (true) with check (true);
