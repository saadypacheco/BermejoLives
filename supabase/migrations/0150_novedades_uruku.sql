-- Novedades de URUKU (docs/novedades-uruku.md): lo que URUKU mismo cuenta en la sección
-- «Novedades» del inicio, junto a las de los comercios (p. ej. «URUKU fue auspiciante del
-- Festival del Lapacho»), con portada, fotos y video.
--
-- Cómo está dado el acceso (regla de la 0145/0149: una columna nueva nace PRIVADA):
--   * anon y authenticated leen SÓLO las activas (policy) y SÓLO las columnas que lista el
--     grant (todas menos `created_by`, que es quién la cargó). Nunca un grant de tabla
--     entera: `select=*` por la API falla (42501), el sitio tiene que pedir columnas.
--   * service_role (el backend) hace todo. Es la única vía de escritura.
--   * Baja LÓGICA (`activo = false`), nunca DELETE físico (ni siquiera el backend lo usa).
--
-- `fotos` es una lista de {url, thumb_url}, de 12 como máximo (también lo exige un check).
-- Como el panel puede subir varias fotos a la vez, agregar y quitar una foto se hace en UNA
-- sentencia dentro de la base (`novedad_agregar_foto` / `novedad_quitar_foto`), no leyendo la
-- lista y reescribiéndola desde el backend: dos subidas en paralelo no se pisan. Las dos
-- funciones son sólo del backend.
--
-- Idempotente: se puede correr dos veces. Todo en una transacción con comprobación al final.

begin;

create table if not exists public.novedades_uruku (
  id                uuid primary key default gen_random_uuid(),
  ciudad_id         uuid references public.ciudades(id),          -- null = todas las ciudades
  titulo            text not null check (char_length(btrim(titulo)) between 1 and 120),
  texto             text check (texto is null or char_length(texto) <= 2000),
  fecha             date not null default ((now() at time zone 'America/La_Paz')::date),
  portada_url       text,
  portada_thumb_url text,
  fotos             jsonb not null default '[]'::jsonb
                    check (jsonb_typeof(fotos) = 'array' and jsonb_array_length(fotos) <= 12),
  video_url         text,
  video_poster_url  text,
  enlace_url        text,
  destacada         boolean not null default false,
  activo            boolean not null default true,
  created_by        text,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

comment on table public.novedades_uruku is
  'Novedades que publica URUKU mismo (sección «Novedades» del inicio). Las carga el publicador desde el panel; baja lógica con activo = false.';
comment on column public.novedades_uruku.ciudad_id is
  'Ciudad a la que va la novedad. null = se muestra en todas las ciudades.';
comment on column public.novedades_uruku.titulo is 'Título (1 a 120 caracteres).';
comment on column public.novedades_uruku.texto is 'Texto largo opcional (hasta 2000 caracteres).';
comment on column public.novedades_uruku.fecha is
  'Fecha de la novedad (por defecto, hoy en hora de La Paz). Ordena la lista después de «destacada».';
comment on column public.novedades_uruku.portada_url is 'Portada (JPG que sirve el backend); portada_thumb_url es su miniatura.';
comment on column public.novedades_uruku.fotos is
  'Fotos de la novedad: lista de {url, thumb_url}, máximo 12. Se agregan y se sacan con novedad_agregar_foto / novedad_quitar_foto.';
comment on column public.novedades_uruku.video_url is
  'Video subido al disco del backend (mp4/webm/mov). URUKU no lo hostea en otro lado.';
comment on column public.novedades_uruku.video_poster_url is 'Imagen de póster del video (opcional).';
comment on column public.novedades_uruku.enlace_url is 'Enlace opcional, siempre http(s) (lo valida el backend).';
comment on column public.novedades_uruku.destacada is 'Las destacadas van primero.';
comment on column public.novedades_uruku.activo is 'Baja lógica: false = no se ve en el sitio.';
comment on column public.novedades_uruku.created_by is
  'Email de quien la cargó (PRIVADA: anon no la lee, regla 11 de AGENTS.md).';

create index if not exists idx_novedades_uruku_vigentes
  on public.novedades_uruku (ciudad_id, destacada desc, fecha desc) where activo;

-- ============================================================ permisos + RLS
alter table public.novedades_uruku enable row level security;

drop policy if exists novedades_uruku_public_read on public.novedades_uruku;
create policy novedades_uruku_public_read on public.novedades_uruku
  for select to anon, authenticated using (activo);

-- Se parte de cero (por si un default privilege le dio la tabla entera a anon) y se da por columnas.
revoke all on public.novedades_uruku from public, anon, authenticated;

grant select (
  id, ciudad_id, titulo, texto, fecha, portada_url, portada_thumb_url, fotos,
  video_url, video_poster_url, enlace_url, destacada, activo, created_at, updated_at
) on public.novedades_uruku to anon, authenticated;

grant all on public.novedades_uruku to service_role;

-- ============================================================ fotos, atómico
-- Agrega una foto al final. Devuelve la lista nueva, o null si la novedad no existe o ya
-- tiene `p_max` fotos (el backend distingue los dos casos).
create or replace function public.novedad_agregar_foto(p_id uuid, p_foto jsonb, p_max int default 12)
returns jsonb
language sql
as $fn$
  update public.novedades_uruku n
     set fotos = n.fotos || jsonb_build_array(p_foto),
         updated_at = now()
   where n.id = p_id
     and jsonb_array_length(n.fotos) < least(p_max, 12)
  returning n.fotos;
$fn$;

-- Saca la foto cuya `url` es `p_url`. Devuelve ESA foto ({url, thumb_url}) para que el
-- backend borre sus archivos, o null si no estaba.
create or replace function public.novedad_quitar_foto(p_id uuid, p_url text)
returns jsonb
language plpgsql
as $fn$
declare
  v_foto jsonb;
begin
  select e into v_foto
    from public.novedades_uruku n, jsonb_array_elements(n.fotos) e
   where n.id = p_id and e->>'url' = p_url
   limit 1
     for update of n;
  if v_foto is null then
    return null;
  end if;
  update public.novedades_uruku n
     set fotos = coalesce((select jsonb_agg(x.e order by x.ord)
                             from jsonb_array_elements(n.fotos) with ordinality as x(e, ord)
                            where x.e->>'url' is distinct from p_url), '[]'::jsonb),
         updated_at = now()
   where n.id = p_id;
  return v_foto;
end
$fn$;

comment on function public.novedad_agregar_foto(uuid, jsonb, int) is
  'Agrega una foto a una novedad sin pisar subidas en paralelo. Sólo el backend.';
comment on function public.novedad_quitar_foto(uuid, text) is
  'Saca una foto de una novedad y devuelve la foto sacada. Sólo el backend.';

-- Las funciones nacen ejecutables por PUBLIC: se les quita; sólo el backend.
revoke all on function public.novedad_agregar_foto(uuid, jsonb, int) from public, anon, authenticated;
revoke all on function public.novedad_quitar_foto(uuid, text) from public, anon, authenticated;
grant execute on function public.novedad_agregar_foto(uuid, jsonb, int) to service_role;
grant execute on function public.novedad_quitar_foto(uuid, text) to service_role;

-- ============================================================ comprobación
-- Si algo no quedó como debe, se revierte todo.
do $chk$
declare
  v_rol text;
  v_col text;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    if has_column_privilege(v_rol, 'public.novedades_uruku', 'created_by', 'select') then
      raise exception '0150: % puede leer novedades_uruku.created_by', v_rol;
    end if;
    foreach v_col in array array['id', 'ciudad_id', 'titulo', 'texto', 'fecha', 'portada_url',
                                 'portada_thumb_url', 'fotos', 'video_url', 'video_poster_url',
                                 'enlace_url', 'destacada', 'activo', 'created_at', 'updated_at'] loop
      if not has_column_privilege(v_rol, 'public.novedades_uruku', v_col, 'select') then
        raise exception '0150: % no puede leer novedades_uruku.%', v_rol, v_col;
      end if;
    end loop;
    if has_table_privilege(v_rol, 'public.novedades_uruku', 'insert')
       or has_table_privilege(v_rol, 'public.novedades_uruku', 'update')
       or has_table_privilege(v_rol, 'public.novedades_uruku', 'delete') then
      raise exception '0150: % puede escribir novedades_uruku', v_rol;
    end if;
    if has_function_privilege(v_rol, 'public.novedad_agregar_foto(uuid, jsonb, int)', 'execute')
       or has_function_privilege(v_rol, 'public.novedad_quitar_foto(uuid, text)', 'execute') then
      raise exception '0150: % puede ejecutar una función de novedades', v_rol;
    end if;
  end loop;
  if not (select relrowsecurity from pg_class where oid = 'public.novedades_uruku'::regclass) then
    raise exception '0150: novedades_uruku sin RLS';
  end if;
  if not has_table_privilege('service_role', 'public.novedades_uruku', 'insert')
     or not has_table_privilege('service_role', 'public.novedades_uruku', 'update')
     or not has_function_privilege('service_role', 'public.novedad_agregar_foto(uuid, jsonb, int)', 'execute')
     or not has_function_privilege('service_role', 'public.novedad_quitar_foto(uuid, text)', 'execute') then
    raise exception '0150: service_role perdió un permiso';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
