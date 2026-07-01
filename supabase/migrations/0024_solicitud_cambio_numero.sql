-- 0024: Recuperar cuenta cuando el dueño cambió de número de WhatsApp.
-- Sin email/password (migración 0023), la única forma de "probar que sos
-- vos" hoy es el número viejo. Si lo perdiste, esto es un pedido manual:
-- subís una foto actual del local + el número nuevo, y un ADMIN aprueba o
-- rechaza (la foto del local es pública, cualquiera puede sacarla — nunca
-- se aprueba solo, la IA es apoyo visual, no un gate).

create table solicitudes_cambio_numero (
  id                 uuid primary key default gen_random_uuid(),
  comercio_id        uuid not null references comercios(id) on delete cascade,
  whatsapp_nuevo     text not null,
  foto_url           text,
  mensaje            text,
  similitud_estimada text,           -- etiqueta libre de la IA (ej. "alta", "baja", o motivo)
  estado             text not null default 'pendiente' check (estado in ('pendiente', 'aprobada', 'rechazada')),
  revisada_por       text,
  revisada_en        timestamptz,
  created_at         timestamptz not null default now()
);

create index idx_solicitudes_cambio_numero_comercio on solicitudes_cambio_numero(comercio_id);
create index idx_solicitudes_cambio_numero_estado on solicitudes_cambio_numero(estado);

alter table solicitudes_cambio_numero enable row level security;

-- El backend inserta con service_role (bypassa RLS); política explícita
-- para cualquier acceso futuro desde el cliente público.
create policy "Anyone can insert solicitudes_cambio_numero"
  on solicitudes_cambio_numero for insert
  with check (true);
