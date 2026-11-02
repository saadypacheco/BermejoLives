-- 0181 · Contenido para redes y cuidado de suscriptores (MVP).
--
-- Spec técnica: docs/contenido-redes-tecnico.md. Funcional: docs/contenido-redes-y-suscriptores.md.
--
--  1. comercio_social_consents: autorización para usar el comercio y sus fotos en las redes
--     de URUKU. Es una BITÁCORA: cada alta o retiro es una fila nueva, con fecha, vía y quién
--     la registró. La vista comercio_social_consent_current da la vigente de cada comercio.
--  2. content_assets: fotos del banco de contenido. El archivo vive en el disco PRIVADO del
--     backend (CONTENT_DIR), nunca bajo /fotos.
--  3. content_pieces y content_piece_sources: cada pieza (video 9:16) y de qué fotos sale.
--  4. content_posts: una fila por pieza y red; la publica una persona (modo B).
--  5. subscriber_profiles, subscriber_reports, subscriber_tasks: cuidado de los suscriptores.
--  6. planes.social_pieces_per_month: piezas propias por ciclo de cobro que incluye el plan.
--
-- Todo es SÓLO del backend (service_role): anon y authenticated no tienen ningún permiso.
-- `comercios` no se toca. La columna nueva de `planes` no entra en el grant por columnas de
-- la 0134 y la 0144: nace privada.
-- Sin borrado físico: todo baja con `activo`. Las FK no llevan cascade a propósito.
-- Idempotente: se puede correr dos veces.

begin;

-- ───────────────────────────────────────────── 1. autorización para redes
create table if not exists public.comercio_social_consents (
  id          uuid primary key default gen_random_uuid(),
  comercio_id uuid not null references public.comercios(id),
  granted     boolean not null,                       -- true = autorizó; false = retiró
  via         text not null check (via in ('agent_signup', 'agent_visit', 'admin',
                                           'merchant_panel', 'whatsapp_reply', 'subscription')),
  recorded_by text not null,                          -- correo del panel o del agente; 'comercio:<cuenta>'
  note        text check (note is null or length(note) <= 300),
  recorded_at timestamptz not null default now(),
  activo      boolean not null default true
);
create index if not exists idx_social_consents_comercio
  on public.comercio_social_consents (comercio_id, recorded_at desc);

comment on table public.comercio_social_consents is
  'Bitácora de la autorización para mostrar el comercio y sus fotos en las redes de URUKU. Cada cambio es una fila. Sólo el backend.';

create or replace view public.comercio_social_consent_current
  with (security_invoker = true) as
select distinct on (c.comercio_id)
       c.comercio_id, c.granted, c.via, c.recorded_by, c.note, c.recorded_at
  from public.comercio_social_consents c
 where c.activo
 order by c.comercio_id, c.recorded_at desc, c.id desc;

comment on view public.comercio_social_consent_current is
  'La autorización vigente de cada comercio (la última fila activa de la bitácora). Sólo el backend.';

-- ───────────────────────────────────────────── 2. banco de fotos
create table if not exists public.content_assets (
  id                uuid primary key default gen_random_uuid(),
  comercio_id       uuid not null references public.comercios(id),
  kind              text not null default 'photo' check (kind in ('photo')),
  source            text not null check (source in ('admin_upload', 'agent_upload')),
  file_path         text not null,                    -- RELATIVA a CONTENT_DIR
  thumb_path        text not null,                    -- RELATIVA a CONTENT_DIR
  sha256            text not null check (length(sha256) = 64),
  source_sha256     text check (source_sha256 is null or length(source_sha256) = 64),
  width             int not null check (width > 0),
  height            int not null check (height > 0),
  bytes             int not null check (bytes > 0),
  taken_at          timestamptz,                      -- lo que informa el teléfono, si lo informa
  usable_for_social boolean not null default true,    -- false = «No usar en redes»
  has_people        boolean not null default false,   -- «Hay personas que se reconocen»
  people_ok         boolean,                          -- quien aparece aceptó
  gallery_photo_id  uuid,                             -- copia en comercio_fotos (sin FK: esa tabla borra físico)
  uploaded_by       text not null,
  last_used_at      timestamptz,
  use_count         int not null default 0 check (use_count >= 0),
  activo            boolean not null default true,
  deactivated_by    text,
  deactivated_at    timestamptz,
  file_purged_at    timestamptz,                      -- se borró el archivo; la fila queda
  created_at        timestamptz not null default now()
);
create unique index if not exists uq_content_assets_sha
  on public.content_assets (comercio_id, sha256) where activo;
create unique index if not exists uq_content_assets_source_sha
  on public.content_assets (comercio_id, source_sha256) where activo and source_sha256 is not null;
create index if not exists idx_content_assets_usable
  on public.content_assets (comercio_id, last_used_at nulls first) where activo and usable_for_social;
create index if not exists idx_content_assets_purge
  on public.content_assets (deactivated_at) where not activo and file_purged_at is null;

comment on table public.content_assets is
  'Fotos del banco de contenido para redes. Archivo en el disco privado CONTENT_DIR. Sólo el backend.';

-- ───────────────────────────────────────────── 3. piezas
create table if not exists public.content_pieces (
  id                uuid primary key default gen_random_uuid(),
  week_start        date not null check (extract(isodow from week_start) = 1),
  scheduled_for     date not null,
  pillar            text not null check (pillar in ('comercio_del_dia', 'ofertas')),
  format            text not null default 'video_9x16' check (format in ('video_9x16')),
  comercio_id       uuid references public.comercios(id),          -- null en compilados
  ciudad_id         uuid references public.ciudades(id),
  counts_for_quota  boolean not null default false,
  quota_cycle_start date,                                          -- ciclo de cobro al que se imputa
  status            text not null default 'queued' check (status in
                    ('queued', 'rendering', 'ready_for_review', 'approved', 'published', 'skipped', 'failed')),
  facts             jsonb not null,                                -- lo único que ve Gemini y dibuja la plantilla
  template          text not null,                                 -- 'comercio_del_dia' | 'ofertas'
  template_version  int not null default 1,
  caption_tiktok    text check (caption_tiktok is null or length(caption_tiktok) <= 300),
  caption_ig        text check (caption_ig is null or length(caption_ig) <= 600),
  caption_channel   text check (caption_channel is null or length(caption_channel) <= 400),
  hashtags          text[] not null default '{}',
  caption_engine    text not null,                                 -- 'gemini:<modelo>' | 'template'
  caption_checks    jsonb not null default '[]'::jsonb,            -- objeciones del validador; [] = en verde
  caption_edited    boolean not null default false,
  render_attempts   int not null default 0,
  render_next_at    timestamptz not null default now(),
  render_started_at timestamptz,
  render_ms         int,
  render_error      text,
  video_path        text,                                          -- RELATIVA a CONTENT_DIR
  cover_path        text,                                          -- RELATIVA a CONTENT_DIR
  video_bytes       bigint,
  duration_s        numeric(4,1),
  files_purged_at   timestamptz,
  share_token       text unique check (share_token is null or length(share_token) >= 22),
  share_expires_at  timestamptz,
  approved_by       text,
  approved_at       timestamptz,
  skip_reason       text check (skip_reason is null or skip_reason in
                    ('bad_photos', 'merchant_asked', 'consent_revoked', 'unpaid', 'other')),
  skip_note         text check (skip_note is null or length(skip_note) <= 300),
  skipped_by        text,
  skipped_at        timestamptz,
  published_at      timestamptz,
  created_by        text not null,                                 -- 'selector' o el correo de quien armó la semana
  activo            boolean not null default true,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  check (scheduled_for between week_start and week_start + 6),
  check (pillar <> 'comercio_del_dia' or comercio_id is not null),
  check (not counts_for_quota or (comercio_id is not null and quota_cycle_start is not null))
);
-- Un lugar del calendario = una pieza viva. Es lo que hace idempotente al selector.
create unique index if not exists uq_content_pieces_slot
  on public.content_pieces (scheduled_for, pillar) where activo and status not in ('skipped', 'failed');
create index if not exists idx_content_pieces_queue
  on public.content_pieces (status, render_next_at) where activo;
create index if not exists idx_content_pieces_comercio
  on public.content_pieces (comercio_id, scheduled_for desc) where activo;
create index if not exists idx_content_pieces_purge
  on public.content_pieces (status, updated_at) where video_path is not null and files_purged_at is null;

comment on table public.content_pieces is
  'Piezas para las redes de URUKU (video 9:16). Las elige el selector semanal y las aprueba una persona. Sólo el backend.';

create table if not exists public.content_piece_sources (
  id           uuid primary key default gen_random_uuid(),
  piece_id     uuid not null references public.content_pieces(id),
  position     smallint not null check (position >= 0),
  source_type  text not null check (source_type in ('asset', 'gallery', 'cover', 'offer')),
  source_id    uuid,                                   -- content_assets / comercio_fotos / publicaciones; null = portada
  comercio_id  uuid not null references public.comercios(id),
  file_ref     text not null,                          -- ruta relativa (asset) o URL pública /fotos (resto)
  caption_fact text check (caption_fact is null or length(caption_fact) <= 80),  -- «Nombre · Bs 180» en compilados
  activo       boolean not null default true,
  created_at   timestamptz not null default now(),
  unique (piece_id, position)
);
create index if not exists idx_content_piece_sources_source
  on public.content_piece_sources (source_type, source_id) where activo;
create index if not exists idx_content_piece_sources_comercio
  on public.content_piece_sources (comercio_id, created_at desc) where activo;

-- ───────────────────────────────────────────── 4. publicación por red
create table if not exists public.content_posts (
  id                  uuid primary key default gen_random_uuid(),
  piece_id            uuid not null references public.content_pieces(id),
  network             text not null check (network in ('tiktok', 'instagram', 'facebook', 'wa_channel')),
  status              text not null default 'pending' check (status in ('pending', 'claimed', 'posted', 'skipped')),
  ref_tag             text not null check (length(ref_tag) between 2 and 64),   -- el ?ref= de esta pieza en esta red
  claimed_by          text,
  claimed_at          timestamptz,
  posted_by           text,
  posted_at           timestamptz,
  post_url            text check (post_url is null or post_url ~ '^https://'),
  posted_without_link boolean not null default false,
  skip_reason         text check (skip_reason is null or length(skip_reason) <= 200),
  views               int check (views is null or views >= 0),                  -- carga manual (etapa 2)
  metrics_at          timestamptz,
  activo              boolean not null default true,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  unique (piece_id, network),
  check (status <> 'claimed' or (claimed_by is not null and claimed_at is not null)),
  check (status <> 'posted' or (posted_at is not null and (post_url is not null or posted_without_link)))
);
create index if not exists idx_content_posts_open
  on public.content_posts (piece_id) where activo and status in ('pending', 'claimed');

comment on table public.content_posts is
  'Una fila por pieza y red. Una persona la reclama, la publica a mano y pega el link. Sólo el backend.';

-- ───────────────────────────────────────────── 5. cuidado de suscriptores
create table if not exists public.subscriber_profiles (
  comercio_id           uuid primary key references public.comercios(id),
  contact_person        text check (contact_person is null or length(contact_person) <= 80),
  onboarding_started_at timestamptz,
  onboarding_started_by text,                          -- correo, o 'auto:pago:<id del pago>'
  notes                 text check (notes is null or length(notes) <= 1000),
  activo                boolean not null default true,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create table if not exists public.subscriber_reports (
  id           uuid primary key default gen_random_uuid(),
  comercio_id  uuid not null references public.comercios(id),
  period_start date not null,
  period_end   date not null check (period_end >= period_start),
  data         jsonb not null,                         -- visitas, whatsapp, cómo llegar, palabras, piezas, ofertas
  activo       boolean not null default true,
  created_at   timestamptz not null default now(),
  unique (comercio_id, period_start)
);

create table if not exists public.subscriber_tasks (
  id          uuid primary key default gen_random_uuid(),
  comercio_id uuid not null references public.comercios(id),
  kind        text not null check (kind in ('welcome', 'profile_check', 'first_offer', 'photo_session',
                'first_piece', 'week1_checkin', 'piece_delivery', 'photo_refresh', 'monthly_report',
                'renewal_before', 'renewal_overdue', 'churn_call')),
  due_on      date not null,
  status      text not null default 'open' check (status in ('open', 'done', 'skipped')),
  piece_id    uuid references public.content_pieces(id),
  report_id   uuid references public.subscriber_reports(id),
  sent_text   text,                                    -- lo que se mandó, guardado al marcar «enviado»
  outcome     text check (outcome is null or length(outcome) <= 500),
  done_by     text,
  done_at     timestamptz,
  auto_closed boolean not null default false,          -- la cerró el sistema (la condición se cumplió)
  note        text check (note is null or length(note) <= 300),
  activo      boolean not null default true,
  created_at  timestamptz not null default now(),
  unique (comercio_id, kind, due_on)
);
create index if not exists idx_subscriber_tasks_open
  on public.subscriber_tasks (due_on) where activo and status = 'open';
create index if not exists idx_subscriber_tasks_comercio
  on public.subscriber_tasks (comercio_id, due_on desc);

comment on table public.subscriber_tasks is
  'Tareas de cuidado de los suscriptores (bienvenida, piezas, reporte, renovación). Los mensajes salen por wa.me, a mano. Sólo el backend.';

-- ───────────────────────────────────────────── 6. piezas por plan
alter table public.planes add column if not exists social_pieces_per_month int;

do $$
begin
  if not exists (select 1 from pg_constraint
                  where conname = 'planes_social_pieces_per_month_check'
                    and conrelid = 'public.planes'::regclass) then
    alter table public.planes
      add constraint planes_social_pieces_per_month_check
      check (social_pieces_per_month is null or social_pieces_per_month between 0 and 31);
  end if;
end $$;

comment on column public.planes.social_pieces_per_month is
  'Piezas propias para redes por ciclo de cobro (D-01). NULL = 0. Editable en Admin › Planes. No es pública.';

update public.planes set social_pieces_per_month = 0 where social_pieces_per_month is null and slug = 'gratis';
update public.planes set social_pieces_per_month = 2 where social_pieces_per_month is null and slug = 'publica';
update public.planes set social_pieces_per_month = 4 where social_pieces_per_month is null
   and slug in ('destacado', 'pro', 'premium', 'empleado_ia');

-- ───────────────────────────────────────────── updated_at
drop trigger if exists trg_content_pieces_updated on public.content_pieces;
create trigger trg_content_pieces_updated before update on public.content_pieces
  for each row execute function set_updated_at();
drop trigger if exists trg_content_posts_updated on public.content_posts;
create trigger trg_content_posts_updated before update on public.content_posts
  for each row execute function set_updated_at();
drop trigger if exists trg_subscriber_profiles_updated on public.subscriber_profiles;
create trigger trg_subscriber_profiles_updated before update on public.subscriber_profiles
  for each row execute function set_updated_at();

-- ───────────────────────────────────────────── RLS y permisos
alter table public.comercio_social_consents enable row level security;
alter table public.content_assets           enable row level security;
alter table public.content_pieces           enable row level security;
alter table public.content_piece_sources    enable row level security;
alter table public.content_posts            enable row level security;
alter table public.subscriber_profiles      enable row level security;
alter table public.subscriber_reports       enable row level security;
alter table public.subscriber_tasks         enable row level security;

revoke all on public.comercio_social_consents, public.comercio_social_consent_current,
              public.content_assets, public.content_pieces, public.content_piece_sources,
              public.content_posts, public.subscriber_profiles, public.subscriber_reports,
              public.subscriber_tasks
  from public, anon, authenticated;

grant all on public.comercio_social_consents, public.content_assets, public.content_pieces,
             public.content_piece_sources, public.content_posts, public.subscriber_profiles,
             public.subscriber_reports, public.subscriber_tasks
  to service_role;
grant select on public.comercio_social_consent_current to service_role;

-- ───────────────────────────────────────────── comprobación (si algo falla, no queda nada)
do $chk$
declare
  v_rol   text;
  v_tabla text;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    foreach v_tabla in array array['public.comercio_social_consents', 'public.comercio_social_consent_current',
                                   'public.content_assets', 'public.content_pieces',
                                   'public.content_piece_sources', 'public.content_posts',
                                   'public.subscriber_profiles', 'public.subscriber_reports',
                                   'public.subscriber_tasks'] loop
      if has_table_privilege(v_rol, v_tabla, 'select')
         or has_table_privilege(v_rol, v_tabla, 'insert')
         or has_table_privilege(v_rol, v_tabla, 'update')
         or has_table_privilege(v_rol, v_tabla, 'delete') then
        raise exception '0181: % tiene permisos sobre %', v_rol, v_tabla;
      end if;
    end loop;
    if has_column_privilege(v_rol, 'public.planes', 'social_pieces_per_month', 'select') then
      raise exception '0181: % puede leer planes.social_pieces_per_month', v_rol;
    end if;
  end loop;
  foreach v_tabla in array array['public.comercio_social_consents', 'public.content_assets',
                                 'public.content_pieces', 'public.content_piece_sources',
                                 'public.content_posts', 'public.subscriber_profiles',
                                 'public.subscriber_reports', 'public.subscriber_tasks'] loop
    if not (select relrowsecurity from pg_class where oid = v_tabla::regclass) then
      raise exception '0181: % sin RLS', v_tabla;
    end if;
    if not has_table_privilege('service_role', v_tabla, 'insert')
       or not has_table_privilege('service_role', v_tabla, 'update') then
      raise exception '0181: service_role sin permiso de escritura sobre %', v_tabla;
    end if;
  end loop;
  if not has_table_privilege('service_role', 'public.comercio_social_consent_current', 'select') then
    raise exception '0181: service_role no puede leer comercio_social_consent_current';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
