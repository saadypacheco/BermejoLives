-- Mapa de calles recorridas (docs/mapa-calles.md): el trazado de las calles de cada ciudad
-- (bajado de OpenStreetMap) y las marcas que dejan los agentes y el admin sobre cada tramo.
--
-- 1. `calles_tramos`: un tramo = una vía de OSM (`osm_way_id`) con su línea. La geometría es una
--    lista [[lat,lng],...] con 5 decimales (~1 m). El estado «recorrida / parcial / pendiente»
--    NO se guarda acá: lo calcula el backend cruzando el trazado con los comercios de la ciudad.
-- 2. `calles_marcas`: lo que una persona dijo de un tramo («recorrida», «sin comercios» o
--    «pendiente» para volver a abrirlo). Es un registro: nunca se pisa ni se borra, y vale la
--    ÚLTIMA marca de cada tramo.
--
-- Las dos tablas son PRIVADAS: RLS activo, sin policy y sin grant a anon ni authenticated. Las
-- lee y escribe sólo el backend con service_role (el sitio no las toca). Baja LÓGICA con
-- `activo`; nada de DELETE físico.
--
-- Idempotente: se puede correr dos veces. Una transacción, con comprobación al final.

begin;

create table if not exists public.calles_tramos (
  id          uuid primary key default gen_random_uuid(),
  ciudad_id   uuid not null references public.ciudades(id),
  osm_way_id  bigint,
  nombre      text,
  tipo        text,
  geom        jsonb not null
              check (jsonb_typeof(geom) = 'array' and jsonb_array_length(geom) >= 2),
  longitud_m  int,
  activo      boolean not null default true,
  created_at  timestamptz not null default now()
);

comment on table public.calles_tramos is
  'Tramos de calle de cada ciudad, bajados de OpenStreetMap. Privada: sólo el backend (service_role). Baja lógica con activo = false.';
comment on column public.calles_tramos.osm_way_id is
  'Id de la vía en OpenStreetMap. Único por ciudad: volver a importar actualiza, no duplica.';
comment on column public.calles_tramos.nombre is 'Nombre de la calle según OSM; null = la vía no tiene nombre.';
comment on column public.calles_tramos.tipo is 'Clase de OSM (highway): primary, secondary, tertiary, residential, unclassified, living_street, pedestrian y sus _link.';
comment on column public.calles_tramos.geom is 'Línea del tramo: lista [[lat,lng],...] con 5 decimales.';
comment on column public.calles_tramos.longitud_m is 'Largo del tramo en metros.';
comment on column public.calles_tramos.activo is 'Baja lógica: false = el tramo no entra al mapa.';

create unique index if not exists calles_tramos_ciudad_way_uq
  on public.calles_tramos (ciudad_id, osm_way_id);

create table if not exists public.calles_marcas (
  id          uuid primary key default gen_random_uuid(),
  tramo_id    uuid not null references public.calles_tramos(id),
  estado      text not null check (estado in ('recorrida', 'sin_comercios', 'pendiente')),
  nota        text check (nota is null or char_length(nota) <= 200),
  actor       text,
  created_at  timestamptz not null default now()
);

comment on table public.calles_marcas is
  'Marcas manuales sobre un tramo de calle. Registro que sólo crece: vale la última de cada tramo. Privada: sólo el backend.';
comment on column public.calles_marcas.estado is
  'recorrida = ya se pasó · sin_comercios = calle de casas o baldío · pendiente = volver a abrirla.';
comment on column public.calles_marcas.nota is 'Comentario libre, hasta 200 caracteres.';
comment on column public.calles_marcas.actor is 'Email de quien marcó (privado: al agente se le muestra sólo la parte antes de la @).';

create index if not exists idx_calles_marcas_tramo
  on public.calles_marcas (tramo_id, created_at desc);

-- ============================================================ permisos + RLS
-- RLS activo y SIN policies: aunque alguien diera un grant por error, anon no vería filas.
alter table public.calles_tramos enable row level security;
alter table public.calles_marcas enable row level security;

-- Se parte de cero (por si un default privilege le dio la tabla a anon) y sólo se da a service_role.
revoke all on public.calles_tramos from public, anon, authenticated;
revoke all on public.calles_marcas from public, anon, authenticated;
grant all on public.calles_tramos to service_role;
grant all on public.calles_marcas to service_role;

-- ============================================================ comprobación
-- Si algo no quedó como debe, se revierte todo.
do $chk$
declare
  v_rol text;
  v_tabla text;
begin
  foreach v_tabla in array array['calles_tramos', 'calles_marcas'] loop
    if not (select relrowsecurity from pg_class where oid = ('public.' || v_tabla)::regclass) then
      raise exception '0152: % sin RLS', v_tabla;
    end if;
    foreach v_rol in array array['anon', 'authenticated'] loop
      if has_table_privilege(v_rol, 'public.' || v_tabla, 'select')
         or has_table_privilege(v_rol, 'public.' || v_tabla, 'insert')
         or has_table_privilege(v_rol, 'public.' || v_tabla, 'update')
         or has_table_privilege(v_rol, 'public.' || v_tabla, 'delete') then
        raise exception '0152: % tiene permisos sobre %', v_rol, v_tabla;
      end if;
    end loop;
    if not has_table_privilege('service_role', 'public.' || v_tabla, 'select')
       or not has_table_privilege('service_role', 'public.' || v_tabla, 'insert')
       or not has_table_privilege('service_role', 'public.' || v_tabla, 'update') then
      raise exception '0152: service_role perdió un permiso sobre %', v_tabla;
    end if;
  end loop;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
