-- 0039: "lugares" = predios con nombre propio (mercados, galerías, paseos, shoppings)
-- que adentro tienen MUCHOS puestos. En el mapa se muestran como UN punto con el
-- nombre del lugar; al tocarlo se abre el directorio de los comercios de adentro.
-- Cada puesto mantiene su PROPIO GPS (comercios.lat/lng); el vínculo es lugar_id.
-- Distinto de `zonas` (barrios/áreas): un lugar es un predio concreto.
create table if not exists lugares (
  id         uuid primary key default gen_random_uuid(),
  nombre     text not null,
  tipo       text not null default 'mercado',   -- mercado | galeria | paseo | shopping | otro
  ciudad_id  uuid references ciudades(id) on delete set null,
  lat        double precision,
  lng        double precision,
  activo     boolean not null default true,
  created_at timestamptz not null default now()
);
create index if not exists idx_lugares_ciudad on lugares (ciudad_id) where activo;

alter table comercios add column if not exists lugar_id uuid references lugares(id) on delete set null;
alter table comercios add column if not exists puesto   text;
create index if not exists idx_comercios_lugar on comercios (lugar_id) where activo;

-- Grants para el self-host (PostgREST). `lugares` es referencia pública (nombres de
-- mercados/galerías): lectura para todos; escritura sólo el backend (service_role).
grant all    on lugares to service_role;
grant select on lugares to anon, authenticated;
