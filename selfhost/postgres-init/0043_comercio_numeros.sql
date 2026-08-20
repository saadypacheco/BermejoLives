-- Números de WhatsApp autorizados a publicar en nombre de un comercio.
--
-- Por qué no alcanza comercios.whatsapp: ese es el número PÚBLICO del local, el
-- que ve el comprador. El número que MANDA los productos por WhatsApp puede ser
-- otro (el celular del empleado, el del dueño, un segundo local). Son dos cosas
-- distintas y hasta ahora estaban colapsadas en una sola columna.
--
-- Por qué no alcanza comercios.wa_jid: es único por comercio, así que sólo
-- admite un remitente. Acá pueden convivir varios.
--
-- El número es una CREDENCIAL, nunca la identidad: la identidad sigue siendo
-- comercios.id (uuid). Un comercio puede cambiar de número sin dejar de ser el
-- mismo comercio, y por eso esta tabla es una relación aparte y no una columna.

create table if not exists comercio_numeros (
  id           uuid primary key default gen_random_uuid(),
  comercio_id  uuid not null references comercios(id) on delete cascade,
  -- E.164 sin '+', normalizado por app.core.telefono.normalizar_whatsapp
  numero       text not null unique,
  etiqueta     text,                            -- 'dueño', 'vendedora del local', etc.
  -- Se da de alta en la segunda pasada, con el dueño presente: eso ES la
  -- verificación. Queda el flag para poder dar de alta números sin confirmar.
  verificado   boolean not null default true,
  activo       boolean not null default true,
  created_at   timestamptz not null default now(),
  created_by   text
);

create index if not exists idx_comercio_numeros_comercio
  on comercio_numeros (comercio_id) where activo;

alter table comercio_numeros enable row level security;

-- Sólo el backend (service_role) toca esta tabla: son credenciales.
-- Sin policy para anon/authenticated, nadie más lee ni escribe.
grant all on public.comercio_numeros to service_role;

-- Backfill: el número público que ya tiene cada comercio queda autorizado.
-- on conflict do nothing porque hoy comercios.whatsapp NO es único y puede
-- haber duplicados; en ese caso gana el primero y el resto se reporta aparte.
insert into comercio_numeros (comercio_id, numero, etiqueta, created_by)
select c.id, c.whatsapp, 'número público del comercio', 'backfill-0043'
  from comercios c
 where c.whatsapp is not null
   and length(regexp_replace(c.whatsapp, '\D', '', 'g')) >= 8
on conflict (numero) do nothing;
