-- 0030: Galería de fotos y videos por comercio.
--   Los ARCHIVOS viven en el disco del backend (volumen, servidos por /fotos);
--   acá quedan solo las REFERENCIAS + orden.
--   Fotos: hasta 10 por comercio, con thumb (400px) para tarjetas/mapa.
--   Videos: hasta 5 por comercio, <=60s — material crudo para producir contenido.

create table if not exists comercio_fotos (
  id           uuid primary key default gen_random_uuid(),
  comercio_id  uuid not null references comercios(id) on delete cascade,
  url          text not null,          -- imagen grande (1600px)
  thumb_url    text,                   -- miniatura (400px) para tarjetas/mapa
  orden        smallint not null default 0,
  created_at   timestamptz not null default now()
);
create index if not exists idx_comercio_fotos on comercio_fotos (comercio_id, orden);

create table if not exists comercio_videos (
  id            uuid primary key default gen_random_uuid(),
  comercio_id   uuid not null references comercios(id) on delete cascade,
  url           text not null,
  duracion_seg  smallint,              -- validado en el cliente (<=60)
  orden         smallint not null default 0,
  created_at    timestamptz not null default now()
);
create index if not exists idx_comercio_videos on comercio_videos (comercio_id, orden);

-- RLS + grants (mismo patrón que el resto): el backend (service_role) gestiona;
-- lectura pública anon/authenticated para mostrar la galería en la ficha/mapa.
alter table comercio_fotos  enable row level security;
alter table comercio_videos enable row level security;

grant all    on public.comercio_fotos  to service_role;
grant all    on public.comercio_videos to service_role;
grant select on public.comercio_fotos  to anon, authenticated;
grant select on public.comercio_videos to anon, authenticated;

drop policy if exists comercio_fotos_public_read on comercio_fotos;
create policy comercio_fotos_public_read on comercio_fotos
  for select to anon, authenticated using (true);

drop policy if exists comercio_videos_public_read on comercio_videos;
create policy comercio_videos_public_read on comercio_videos
  for select to anon, authenticated using (true);
