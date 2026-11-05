-- 0187 · Cierre de la semana de la revisión de seguridad de noviembre.
--
-- Cinco cosas chicas de base de datos que acompañan al código de ese lote:
--
--  1. `clave_fallos.tabla` acepta 'usuarios_panel': el bloqueo por cuenta del panel (5 fallos en 15
--     minutos) usa el mismo contador atómico que Mi comercio (`registrar_intento_clave`, 0137). El
--     `numero` de esa fila es un hash del correo, no el correo.
--
--  2. `leads.respondio_por`: quién votó el «¿te contestó?», como un hash (HMAC con una clave del
--     backend) de la IP y la sesión: no guarda ni la IP ni la sesión. Sirve para que el sello
--     «no responde» exija «no» de al menos 3 votantes distintos en 30 días y para que nadie vote dos
--     veces sobre el mismo comercio. PRIVADA: `leads` ya está cerrada para anon y authenticated (0186).
--
--  3. `comercios.baja_motivo` suma 'sin_verificar': un comercio que se registró solo nace OCULTO
--     (`activo = false`) hasta que el dueño confirma su número por WhatsApp (CONFIRMAR) o alguien del
--     equipo lo reactiva. No hace falta columna nueva: `activo` ya oculta al público en el buscador,
--     el mapa, la ficha y el feed, y `baja_motivo` ya distingue por qué. La columna sigue privada
--     para anon (0145 da `select` por columnas; acá no se le da `grant`).
--
--  4. RLS por comercio ACTIVO en `comercio_fotos` y `comercio_videos` (antes `using (true)`): la
--     galería de un comercio dado de baja ya no se ve con la clave pública.
--
--  5. RLS en `lugares` (no tenía): el público sólo ve los lugares con `activo`.
--
-- Idempotente: se puede correr dos veces. Todo en una transacción y con comprobación: si algo no quedó
-- como se espera, no se aplica nada. Copia idéntica en supabase/migrations/ y selfhost/postgres-init/.

begin;

-- ── 1. clave_fallos: el panel también cuenta intentos ────────────────────────
do $$
declare
  c text;
begin
  for c in
    select conname from pg_constraint
     where conrelid = 'public.clave_fallos'::regclass
       and contype = 'c'
       and pg_get_constraintdef(oid) like '%comercio_usuarios%'
  loop
    execute format('alter table public.clave_fallos drop constraint %I', c);
  end loop;
end
$$;

alter table public.clave_fallos
  add constraint clave_fallos_tabla_check
  check (tabla in ('comercio_usuarios', 'usuarios', 'usuarios_panel'));

-- ── 2. leads: quién votó ─────────────────────────────────────────────────────
alter table public.leads add column if not exists respondio_por text;
comment on column public.leads.respondio_por is
  'Hash (HMAC con clave del backend) de la IP y la sesión de quien votó el «¿te contestó?». No guarda la IP ni la sesión. Privada: leads está cerrada para anon.';
create index if not exists idx_leads_comercio_votante
  on public.leads (comercio_id, respondio_por) where respondio_por is not null;

-- ── 3. comercios.baja_motivo: 'sin_verificar' ────────────────────────────────
do $$
declare
  c text;
begin
  for c in
    select conname from pg_constraint
     where conrelid = 'public.comercios'::regclass
       and contype = 'c'
       and pg_get_constraintdef(oid) like '%baja_motivo%'
  loop
    execute format('alter table public.comercios drop constraint %I', c);
  end loop;
end
$$;

alter table public.comercios
  add constraint comercios_baja_motivo_check
  check (baja_motivo in ('admin', 'vencido', 'borrador', 'sin_verificar'));

comment on column public.comercios.baja_motivo is
  'Por qué está dado de baja (activo = false): admin (lo bajó una persona), vencido (lo ocultó el job de vencimientos; se reactiva al pagar), borrador (nació apagado de un WhatsApp desconocido), sin_verificar (se registró solo y todavía no confirmó su número ni lo aprobó el equipo; se enciende al confirmar por WhatsApp o con «Reactivar»). Null si está activo o es una baja vieja sin clasificar. Privada para anon.';

-- ── 4. Galería: sólo de comercios activos ────────────────────────────────────
alter table public.comercio_fotos  enable row level security;
alter table public.comercio_videos enable row level security;

drop policy if exists comercio_fotos_public_read on public.comercio_fotos;
create policy comercio_fotos_public_read on public.comercio_fotos
  for select to anon, authenticated
  using (exists (select 1 from public.comercios c where c.id = comercio_fotos.comercio_id and c.activo));

drop policy if exists comercio_videos_public_read on public.comercio_videos;
create policy comercio_videos_public_read on public.comercio_videos
  for select to anon, authenticated
  using (exists (select 1 from public.comercios c where c.id = comercio_videos.comercio_id and c.activo));

-- ── 5. Lugares: RLS, y el público sólo ve los activos ────────────────────────
alter table public.lugares enable row level security;

drop policy if exists lugares_public_read on public.lugares;
create policy lugares_public_read on public.lugares
  for select to anon, authenticated using (activo);

-- Los permisos de tabla no cambian (la lectura pública y el acceso total del backend vienen de las
-- migraciones de origen); se repite el del backend por explícito. service_role se salta la RLS.
grant all on public.lugares         to service_role;
grant all on public.comercio_fotos  to service_role;
grant all on public.comercio_videos to service_role;

-- ── Comprobación ─────────────────────────────────────────────────────────────
do $chk$
declare
  v_def       text;
  v_esperado  bigint;
  v_visible   bigint;
  v_tabla     text;
begin
  -- 1. el panel cabe en clave_fallos
  select pg_get_constraintdef(oid) into v_def from pg_constraint
   where conrelid = 'public.clave_fallos'::regclass and conname = 'clave_fallos_tabla_check';
  if v_def is null or v_def not like '%usuarios_panel%' then
    raise exception '0187: clave_fallos no acepta usuarios_panel';
  end if;

  -- 2. leads.respondio_por existe y el navegador no la lee
  if not exists (select 1 from information_schema.columns
                  where table_schema = 'public' and table_name = 'leads' and column_name = 'respondio_por') then
    raise exception '0187: falta leads.respondio_por';
  end if;
  if has_column_privilege('anon', 'public.leads', 'respondio_por', 'select')
     or has_column_privilege('authenticated', 'public.leads', 'respondio_por', 'select') then
    raise exception '0187: anon o authenticated pueden leer leads.respondio_por';
  end if;

  -- 3. sin_verificar es un motivo válido y la columna sigue privada para anon
  select pg_get_constraintdef(oid) into v_def from pg_constraint
   where conrelid = 'public.comercios'::regclass and conname = 'comercios_baja_motivo_check';
  if v_def is null or v_def not like '%sin_verificar%' then
    raise exception '0187: comercios.baja_motivo no acepta sin_verificar';
  end if;
  if has_column_privilege('anon', 'public.comercios', 'baja_motivo', 'select')
     or has_column_privilege('authenticated', 'public.comercios', 'baja_motivo', 'select') then
    raise exception '0187: anon o authenticated pueden leer comercios.baja_motivo';
  end if;

  -- 4 y 5. RLS prendida en las tres tablas
  foreach v_tabla in array array['comercio_fotos', 'comercio_videos', 'lugares'] loop
    if not (select relrowsecurity from pg_class where oid = ('public.' || v_tabla)::regclass) then
      raise exception '0187: % no tiene RLS', v_tabla;
    end if;
  end loop;

  -- 4. lo que ve anon de la galería es EXACTAMENTE lo de los comercios activos (no más, no menos)
  select count(*) into v_esperado from public.comercio_fotos f
    join public.comercios c on c.id = f.comercio_id and c.activo;
  set local role anon;
  select count(*) into v_visible from public.comercio_fotos;
  reset role;
  if v_visible <> v_esperado then
    raise exception '0187: anon ve % fotos de galería y debería ver % (las de comercios activos)', v_visible, v_esperado;
  end if;

  select count(*) into v_esperado from public.comercio_videos f
    join public.comercios c on c.id = f.comercio_id and c.activo;
  set local role anon;
  select count(*) into v_visible from public.comercio_videos;
  reset role;
  if v_visible <> v_esperado then
    raise exception '0187: anon ve % videos de galería y debería ver % (los de comercios activos)', v_visible, v_esperado;
  end if;

  -- 5. lugares: anon sólo ve los activos
  select count(*) into v_esperado from public.lugares where activo;
  set local role anon;
  select count(*) into v_visible from public.lugares;
  reset role;
  if v_visible <> v_esperado then
    raise exception '0187: anon ve % lugares y debería ver % (los activos)', v_visible, v_esperado;
  end if;

  -- el backend sigue viendo todo
  if not has_table_privilege('service_role', 'public.lugares', 'select')
     or not has_table_privilege('service_role', 'public.comercio_fotos', 'select')
     or not has_table_privilege('service_role', 'public.leads', 'update') then
    raise exception '0187: service_role perdió acceso';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
