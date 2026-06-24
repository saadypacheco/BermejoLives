-- ============================================================
-- Encontralo · 0018_mensajes
-- Bandeja del comercio: mensajes del ADMIN (notificaciones) y de CLIENTES
-- (consulta pública desde la ficha, por si no tienen el WhatsApp del comercio
--  o el comercio cambió de número). El comercio lee y responde por WhatsApp.
-- ============================================================

create table if not exists mensajes (
  id          uuid        primary key default gen_random_uuid(),
  comercio_id uuid        not null references comercios(id) on delete cascade,
  autor       text        not null,        -- 'admin' | 'cliente' | 'comercio'
  nombre      text,                          -- quién escribe
  contacto    text,                          -- teléfono/email del cliente para responder
  cuerpo      text        not null,
  leido       boolean     not null default false,
  created_at  timestamptz not null default now()
);

create index if not exists idx_mensajes_comercio on mensajes (comercio_id, created_at desc);
create index if not exists idx_mensajes_no_leidos on mensajes (comercio_id) where not leido;

-- RLS: solo el backend (service_role) opera; el alta pública pasa por el backend.
grant all on mensajes to service_role;
alter table mensajes enable row level security;
drop policy if exists mensajes_service_all on mensajes;
create policy mensajes_service_all on mensajes
  for all to service_role using (true) with check (true);
