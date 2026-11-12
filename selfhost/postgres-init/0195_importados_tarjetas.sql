-- 0195 · Importados: tarjetas de presentación (docs/carga-tarjetas.md).
--
--  1. comercios_importados admite filas con fuente = 'tarjeta': el vendedor pasa la foto de una tarjeta de papel,
--     el backend la lee (Tesseract; Gemini sólo con el interruptor prendido), busca la ubicación con Nominatim y
--     la fila queda en la sala de espera de Importados hasta que una persona la promueve. `fuente` no tiene check
--     (la 0066 la dejó libre: 'osm' | futuras), así que no hace falta tocarla.
--     Columnas nuevas, todas PRIVADAS (la tabla sólo la lee el backend con service_role):
--       email        el correo que traía la tarjeta
--       ubicacion    'aproximada' (la puso Nominatim) | 'confirmada' (una persona movió o guardó el punto) |
--                    'no_encontrada' (la dirección no apareció: se marca a mano en el mapa)
--       foto_ref     referencia `privado:…` a la foto de la tarjeta (disco privado, nunca /fotos): puede traer
--                    datos personales (services/archivos_privados.py)
--       texto_leido  el texto crudo que devolvió el lector (sólo el panel lo ve)
--       lector       'tesseract' | 'gemini'
--  2. cost_switches: el check de la clave suma 'gemini_tarjetas' (leer la tarjeta con Gemini en vez del lector
--     gratis). Apagado por defecto: sin fila = apagado. Mismo nombre de constraint que la 0183/0184.
--  3. Un índice para el filtro nuevo del listado (fuente, estado).
--
-- PERMISOS: nada se abre a anon ni a authenticated. La tabla ya tiene RLS (0066); acá se repiten los GRANT
-- explícitos sólo para service_role. Las columnas nuevas heredan el permiso de tabla.
-- Sin borrado físico: lo descartado queda con estado 'descartado'.
-- Idempotente: se puede correr dos veces. Copia idéntica en supabase/migrations/ y selfhost/postgres-init/.

begin;

-- ───────────────────────────────────────────── 1. columnas de la tarjeta
alter table public.comercios_importados add column if not exists email       text;
alter table public.comercios_importados add column if not exists ubicacion   text;
alter table public.comercios_importados add column if not exists foto_ref    text;
alter table public.comercios_importados add column if not exists texto_leido text;
alter table public.comercios_importados add column if not exists lector      text;

alter table public.comercios_importados drop constraint if exists comercios_importados_ubicacion_check;
alter table public.comercios_importados
  add constraint comercios_importados_ubicacion_check
  check (ubicacion is null or ubicacion in ('aproximada', 'confirmada', 'no_encontrada'));

alter table public.comercios_importados drop constraint if exists comercios_importados_lector_check;
alter table public.comercios_importados
  add constraint comercios_importados_lector_check
  check (lector is null or lector in ('tesseract', 'gemini'));

comment on column public.comercios_importados.email       is 'Correo leído de la tarjeta (privado).';
comment on column public.comercios_importados.ubicacion   is 'aproximada (Nominatim) | confirmada (una persona) | no_encontrada.';
comment on column public.comercios_importados.foto_ref    is 'Referencia privado:… a la foto de la tarjeta (disco privado del backend).';
comment on column public.comercios_importados.texto_leido is 'Texto crudo que leyó el lector de la tarjeta (sólo panel).';
comment on column public.comercios_importados.lector      is 'Quién leyó la tarjeta: tesseract | gemini.';

-- ───────────────────────────────────────────── 2. interruptor de costo
alter table public.cost_switches drop constraint if exists cost_switches_key_check;
alter table public.cost_switches
  add constraint cost_switches_key_check check (key in ('gemini_content', 'gemini_phone_scan', 'gemini_tarjetas'));

-- ───────────────────────────────────────────── 3. índice del filtro por fuente
create index if not exists idx_importados_fuente_estado on public.comercios_importados (fuente, estado);

-- ───────────────────────────────────────────── 4. permisos: sólo service_role
alter table public.comercios_importados enable row level security;
revoke all on public.comercios_importados from public, anon, authenticated;
grant all on public.comercios_importados to service_role;

-- ───────────────────────────────────────────── 5. comprobación: si algo quedó mal, no se aplica
do $chk$
declare
  v_rol text;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    if has_table_privilege(v_rol, 'public.comercios_importados', 'select') then
      raise exception '0195: % puede leer comercios_importados', v_rol;
    end if;
  end loop;
  if not has_table_privilege('service_role', 'public.comercios_importados', 'insert')
     or not has_table_privilege('service_role', 'public.comercios_importados', 'update') then
    raise exception '0195: service_role no puede escribir comercios_importados';
  end if;
  if not exists (select 1 from pg_constraint
                  where conname = 'cost_switches_key_check'
                    and conrelid = 'public.cost_switches'::regclass
                    and pg_get_constraintdef(oid) like '%gemini_tarjetas%') then
    raise exception '0195: el check de cost_switches no admite gemini_tarjetas';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
