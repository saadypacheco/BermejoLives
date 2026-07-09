-- ============================================================
-- Encontralo · 0017_destacado_cobrable
-- "Destacar" un producto = una publicación en el feed con COSTO, que se
-- acumula y se cobra junto con la suscripción (facturación acumulada).
-- Al confirmar un pago, los destacados del comercio se marcan 'cobrado'.
-- ============================================================

alter table publicaciones add column if not exists costo            numeric(12,2);
alter table publicaciones add column if not exists cobrado          boolean not null default false;
alter table publicaciones add column if not exists producto_ref_id  uuid references producto_ref(id) on delete set null;

-- cargos pendientes de un comercio = publicaciones con costo aún no cobrado
create index if not exists idx_publicaciones_cargos
  on publicaciones (comercio_id) where costo is not null and not cobrado;

-- imagen del producto para mostrar el destacado en el feed (la devuelve el ecommerce)
alter table producto_ref add column if not exists foto_url text;
