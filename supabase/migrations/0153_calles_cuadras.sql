-- Mapa de calles por CUADRAS (docs/mapa-calles.md, sección «Importar por cuadras»).
--
-- Hasta la 0152 cada fila de `calles_tramos` era una vía entera de OpenStreetMap (213 m de promedio,
-- avenidas de más de 1 km): una avenida con 10 comercios en 2 cuadras quedaba «pendiente» entera.
-- Ahora la importación parte cada vía en sus esquinas (los nodos que comparte con otra vía) y, si una
-- cuadra pasa de 150 m, en partes iguales. Cada pedazo es un tramo; `parte` dice cuál de la vía.
--
--   · `parte` (0, 1, 2…): el orden del pedazo dentro de su vía. Las filas que ya existen quedan en 0.
--   · El único `(ciudad_id, osm_way_id)` se reemplaza por `(ciudad_id, osm_way_id, parte)`, que es
--     la clave del upsert de la importación.
--
-- Las marcas (`calles_marcas`) no se tocan. Lo que no vuelve en una reimportación se da de baja
-- LÓGICA (`activo = false`); nada de DELETE físico.
--
-- Idempotente: se puede correr dos veces. Una transacción, con comprobación al final.

begin;

alter table public.calles_tramos
  add column if not exists parte int not null default 0;

comment on column public.calles_tramos.parte is
  'Pedazo de la vía de OSM (0, 1, 2…): la importación parte cada vía en sus esquinas y en cuadras de hasta 150 m.';
comment on column public.calles_tramos.osm_way_id is
  'Id de la vía en OpenStreetMap. Único por ciudad y parte: volver a importar actualiza, no duplica.';
comment on table public.calles_tramos is
  'Tramos de calle (una cuadra de hasta 150 m) de cada ciudad, bajados de OpenStreetMap. Privada: sólo el backend (service_role). Baja lógica con activo = false.';

-- Primero el nuevo y después se suelta el viejo: nunca queda la tabla sin su único.
create unique index if not exists calles_tramos_ciudad_way_parte_uq
  on public.calles_tramos (ciudad_id, osm_way_id, parte);

drop index if exists public.calles_tramos_ciudad_way_uq;

-- ============================================================ comprobación
do $chk$
begin
  if not exists (select 1 from pg_indexes
                 where schemaname = 'public' and indexname = 'calles_tramos_ciudad_way_parte_uq') then
    raise exception '0153: falta el único (ciudad_id, osm_way_id, parte)';
  end if;
  if exists (select 1 from pg_indexes
             where schemaname = 'public' and indexname = 'calles_tramos_ciudad_way_uq') then
    raise exception '0153: sigue el único viejo (ciudad_id, osm_way_id)';
  end if;
  if not exists (select 1 from information_schema.columns
                 where table_schema = 'public' and table_name = 'calles_tramos'
                   and column_name = 'parte' and is_nullable = 'NO') then
    raise exception '0153: falta calles_tramos.parte (not null)';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema.
notify pgrst, 'reload schema';
