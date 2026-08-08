-- 0033: acepta_reservas por comercio + redes sociales del sitio (editables desde el panel).

-- Algunos comercios no quieren reservas: gatea el acceso a Reservalo desde la ficha.
alter table comercios add column if not exists acepta_reservas boolean not null default true;

-- Redes sociales de Encontralo (las carga el admin/publicador; la home las muestra).
create table if not exists redes_sociales (
  clave    text primary key,   -- 'tiktok' | 'instagram' | 'facebook' | 'youtube' | 'whatsapp_canal'
  etiqueta text not null,
  url      text,
  orden    smallint not null default 0
);
alter table redes_sociales enable row level security;
grant all    on public.redes_sociales to service_role;
grant select on public.redes_sociales to anon, authenticated;
drop policy if exists redes_public_read on redes_sociales;
create policy redes_public_read on redes_sociales for select to anon, authenticated using (true);

insert into redes_sociales (clave, etiqueta, orden) values
  ('tiktok',         'TikTok',            1),
  ('instagram',      'Instagram',         2),
  ('facebook',       'Facebook',          3),
  ('youtube',        'YouTube',           4),
  ('whatsapp_canal', 'Canal de WhatsApp', 5)
on conflict (clave) do nothing;
