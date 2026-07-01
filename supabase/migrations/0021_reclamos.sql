-- 0021: Reclamos públicos (usuarios que dejan un reclamo sobre un comercio o la plataforma).
-- Se responden desde el panel admin ("Reclamos"). comercio_id es opcional:
-- si es NULL, el reclamo es sobre la plataforma en general.

create table reclamos (
  id             uuid primary key default gen_random_uuid(),
  nombre         text,
  contacto       text,           -- email o whatsapp para responderle
  comercio_id    uuid references comercios(id) on delete set null,
  mensaje        text not null,
  estado         text not null default 'pendiente' check (estado in ('pendiente', 'respondido')),
  respuesta      text,
  respondido_por text,
  respondido_en  timestamptz,
  created_at     timestamptz not null default now()
);

create index idx_reclamos_estado on reclamos(estado);
create index idx_reclamos_comercio on reclamos(comercio_id);

alter table reclamos enable row level security;

-- El backend inserta con service_role (bypassa RLS); política explícita
-- para cualquier acceso futuro desde el cliente público.
create policy "Anyone can insert reclamos"
  on reclamos for insert
  with check (true);
