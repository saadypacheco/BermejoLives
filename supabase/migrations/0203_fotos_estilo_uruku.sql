-- 0203 · Fotos con estilo URUKU (docs/fotos-estilo-uruku.md §4).
--
--  1. `comercio_fotos` suma tres columnas para el diseño de cada foto de la galería:
--       diseno_url, diseno_thumb_url  PÚBLICAS (la ficha las usa; se dan por columna)
--       diseno_propuesta_url          PRIVADA (la propuesta que el panel todavía no aprobó; sólo service_role)
--     Como `comercios` en la 0145: se le saca a anon y authenticated el `select` de tabla entera y se les da por
--     columna. Con eso, `select=*` sobre `comercio_fotos` falla con 42501 a propósito: el front pide columnas.
--     Una columna nueva de `comercio_fotos` nace PRIVADA; la comprobación final obliga a decidirla.
--  2. `photo_style_uses`: el registro de cada transformación (costo por imagen y por comercio, el tope diario de
--     Gemini). SOLO INSERT: nunca se actualiza ni se borra. Sólo el backend (service_role), con `select` + `insert`.
--  3. `cost_switches`: el check de la clave suma 'gemini_fotos' y su fila nace APAGADA (costo cero por defecto).
--  4. Comprobación: si algo quedó mal, no se aplica.
--
-- Sin borrado físico. Idempotente: se puede correr dos veces. Copia idéntica en supabase/migrations/ y
-- selfhost/postgres-init/.

begin;

-- ───────────────────────────────────────────── 1. diseño por foto de galería
alter table public.comercio_fotos add column if not exists diseno_url text;
alter table public.comercio_fotos add column if not exists diseno_thumb_url text;
alter table public.comercio_fotos add column if not exists diseno_propuesta_url text;

comment on column public.comercio_fotos.diseno_url is
  'Foto con el estilo URUKU que la ficha muestra en lugar de la original. La aprueba una persona en el panel.';
comment on column public.comercio_fotos.diseno_thumb_url is
  'Miniatura (480 x 600) del diseño. La ficha la usa en la grilla.';
comment on column public.comercio_fotos.diseno_propuesta_url is
  'Diseño propuesto, todavía sin aprobar. Privada: sólo la ve el panel.';

-- El revoke de tabla borra también los grants por columna: va ANTES del grant por columna.
revoke select on public.comercio_fotos from anon, authenticated;
grant select (id, comercio_id, url, thumb_url, orden, created_at, diseno_url, diseno_thumb_url)
  on public.comercio_fotos to anon, authenticated;
grant all on public.comercio_fotos to service_role;

-- ───────────────────────────────────────────── 2. registro de usos (sólo insert)
create table if not exists public.photo_style_uses (
  id             uuid primary key default gen_random_uuid(),
  comercio_id    uuid not null references public.comercios(id),
  foto_id        uuid,                                 -- null = portada; sin FK (comercio_fotos borra físico)
  target         text not null check (target in ('cover', 'gallery')),
  method         text not null check (method in ('free', 'gemini', 'external')),
  model          text,
  prompt_version text,
  cost_usd       numeric(8, 4) not null default 0,
  result         text not null check (result in ('ok', 'error', 'timeout')),
  error          text,                                 -- pasado por sin_secretos, <= 300 caracteres
  result_url     text,
  actor          text not null,                        -- email de quien apretó
  created_at     timestamptz not null default now()
);
comment on table public.photo_style_uses is
  'Una fila por foto transformada con el estilo URUKU (gratis, Gemini o hecha afuera). Historia de costos: sólo insert, nunca se borra. Sólo el backend.';

create index if not exists idx_photo_style_uses_dia on public.photo_style_uses (method, created_at);
create index if not exists idx_photo_style_uses_comercio on public.photo_style_uses (comercio_id, created_at);

alter table public.photo_style_uses enable row level security;
revoke all on public.photo_style_uses from public, anon, authenticated;
-- Los privilegios por defecto del esquema (0090) le dan todo a service_role: se le saca y se le da sólo lo que usa el backend.
revoke all on public.photo_style_uses from service_role;
grant select, insert on public.photo_style_uses to service_role;               -- sin update ni delete

-- ───────────────────────────────────────────── 3. interruptor de costo
alter table public.cost_switches drop constraint if exists cost_switches_key_check;
alter table public.cost_switches
  add constraint cost_switches_key_check
  check (key in ('gemini_content', 'gemini_phone_scan', 'gemini_tarjetas', 'gemini_gastronomia', 'gemini_fotos'));

insert into public.cost_switches (key, enabled, updated_by)
values ('gemini_fotos', false, 'migracion 0203')
on conflict (key) do nothing;

-- ───────────────────────────────────────────── 4. comprobación (si algo falla, no queda nada)
do $chk$
declare
  v_rol       text;
  v_col       text;
  v_publicas  text[] := array['id', 'comercio_id', 'url', 'thumb_url', 'orden', 'created_at', 'diseno_url', 'diseno_thumb_url'];
  v_privadas  text[] := array['diseno_propuesta_url'];
  v_esperado  bigint;
  v_visible   bigint;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    -- comercio_fotos: sin select de tabla; sí en las 8 columnas públicas; no en la privada
    if has_table_privilege(v_rol, 'public.comercio_fotos', 'select') then
      raise exception '0203: % tiene select de tabla sobre comercio_fotos', v_rol;
    end if;
    foreach v_col in array v_publicas loop
      if not has_column_privilege(v_rol, 'public.comercio_fotos', v_col, 'select') then
        raise exception '0203: % no puede leer comercio_fotos.%', v_rol, v_col;
      end if;
    end loop;
    foreach v_col in array v_privadas loop
      if has_column_privilege(v_rol, 'public.comercio_fotos', v_col, 'select') then
        raise exception '0203: % puede leer comercio_fotos.% y tiene que ser privada', v_rol, v_col;
      end if;
    end loop;
    -- photo_style_uses: nada de nada
    if has_table_privilege(v_rol, 'public.photo_style_uses', 'select')
       or has_table_privilege(v_rol, 'public.photo_style_uses', 'insert')
       or has_table_privilege(v_rol, 'public.photo_style_uses', 'update')
       or has_table_privilege(v_rol, 'public.photo_style_uses', 'delete') then
      raise exception '0203: % tiene permisos sobre photo_style_uses', v_rol;
    end if;
  end loop;

  -- toda columna de comercio_fotos está decidida (pública o privada): si aparece una nueva, la migración falla
  for v_col in
    select column_name::text from information_schema.columns
     where table_schema = 'public' and table_name = 'comercio_fotos'
  loop
    if not (v_col = any (v_publicas) or v_col = any (v_privadas)) then
      raise exception '0203: comercio_fotos.% no está decidida (¿pública o privada?)', v_col;
    end if;
  end loop;

  -- RLS prendida, y anon ve exactamente las fotos de los comercios activos
  if not (select relrowsecurity from pg_class where oid = 'public.comercio_fotos'::regclass) then
    raise exception '0203: comercio_fotos sin RLS';
  end if;
  select count(*) into v_esperado from public.comercio_fotos f
    join public.comercios c on c.id = f.comercio_id and c.activo;
  set local role anon;
  select count(id) into v_visible from public.comercio_fotos;
  reset role;
  if v_visible <> v_esperado then
    raise exception '0203: anon ve % fotos de galería y debería ver % (las de comercios activos)', v_visible, v_esperado;
  end if;

  -- photo_style_uses: RLS, y service_role sólo select + insert
  if not (select relrowsecurity from pg_class where oid = 'public.photo_style_uses'::regclass) then
    raise exception '0203: photo_style_uses sin RLS';
  end if;
  if not has_table_privilege('service_role', 'public.photo_style_uses', 'select')
     or not has_table_privilege('service_role', 'public.photo_style_uses', 'insert') then
    raise exception '0203: service_role no puede leer o insertar en photo_style_uses';
  end if;
  if has_table_privilege('service_role', 'public.photo_style_uses', 'update')
     or has_table_privilege('service_role', 'public.photo_style_uses', 'delete')
     or has_table_privilege('service_role', 'public.photo_style_uses', 'truncate') then
    raise exception '0203: service_role puede modificar o borrar photo_style_uses (es sólo insert)';
  end if;

  -- el backend sigue viendo y escribiendo la galería
  if not has_table_privilege('service_role', 'public.comercio_fotos', 'select')
     or not has_table_privilege('service_role', 'public.comercio_fotos', 'update') then
    raise exception '0203: service_role perdió acceso a comercio_fotos';
  end if;

  -- el interruptor: el check admite gemini_fotos y la fila existe
  if not exists (select 1 from pg_constraint
                  where conname = 'cost_switches_key_check'
                    and conrelid = 'public.cost_switches'::regclass
                    and pg_get_constraintdef(oid) like '%gemini_fotos%') then
    raise exception '0203: el check de cost_switches no admite gemini_fotos';
  end if;
  -- (la fila nace apagada por el insert de arriba; después el dueño puede prenderla, así que acá sólo se exige que exista)
  if not exists (select 1 from public.cost_switches where key = 'gemini_fotos') then
    raise exception '0203: falta la fila gemini_fotos de cost_switches';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
