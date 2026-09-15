-- Uruku Ayuda: el asistente del sitio (services/asistente.py).
--
-- Dos tablas. La primera es lo que el asistente SABE porque alguien lo
-- escribió: dónde se cambia plata, qué días hay feria, cómo se cruza a
-- Argentina, qué pasa los domingos. Es la "experiencia registrada en la
-- base": lo que un vecino le contaría a alguien que llega. La segunda es lo
-- que la gente PREGUNTA, con la respuesta que recibió y por qué nivel salió.
-- Las preguntas que quedaron sin respuesta son la cola de trabajo del admin:
-- se contestan una vez, pasan a saber_local, y el asistente las contesta
-- solo de ahí en adelante.

create table if not exists saber_local (
  id          uuid primary key default gen_random_uuid(),
  pregunta    text not null,                 -- cómo lo pregunta la gente
  respuesta   text not null,                 -- lo que se contesta, tal cual
  etiquetas   text[] not null default '{}',  -- palabras por las que se encuentra ("dolar", "cambio")
  ciudad_id   uuid references ciudades(id) on delete set null,
  activo      boolean not null default true,
  creado_por  text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists idx_saber_local_activo on saber_local (activo);

create table if not exists asistente_conversaciones (
  id            uuid primary key default gen_random_uuid(),
  sesion        text not null,                -- id del navegador (localStorage), para el tope diario
  canal         text not null default 'sitio', -- sitio | ficha
  comercio_id   uuid references comercios(id) on delete cascade,  -- null = asistente de URUKU
  pregunta      text not null,
  respuesta     text not null,
  nivel         smallint not null,            -- 0 sin modelo · 1 modelo · 3 humano
  intent        text,
  fuentes       jsonb not null default '[]',
  sin_respuesta boolean not null default false,
  util          boolean,                      -- 👍 / 👎 de la persona; null = no opinó
  resuelta_en   timestamptz,                  -- cuándo alguien la contestó desde el admin
  created_at    timestamptz not null default now()
);
create index if not exists idx_asistente_conv_sesion on asistente_conversaciones (sesion, created_at);
create index if not exists idx_asistente_conv_pendientes on asistente_conversaciones (created_at)
  where sin_respuesta and resuelta_en is null;
create index if not exists idx_asistente_conv_comercio on asistente_conversaciones (comercio_id) where comercio_id is not null;

alter table saber_local enable row level security;
alter table asistente_conversaciones enable row level security;
-- Sólo el backend: lo que la gente pregunta es de la gente, y el saber local
-- sale al público a través del asistente, no como tabla.
grant all on public.saber_local to service_role;
grant all on public.asistente_conversaciones to service_role;

-- Lo primero que el asistente sabe: lo que cualquiera en Bermejo pregunta el
-- primer día. Se edita desde el admin; esto es el arranque, no la verdad.
insert into saber_local (pregunta, respuesta, etiquetas, creado_por)
select * from (values
  ('¿Dónde cambio dólares o pesos?',
   'En Bermejo se cambia en las casas de cambio y con los cambistas de la zona del puente y el centro. Mirá la cotización del día arriba del sitio y compará antes de cambiar; los que están en URUKU: uruku.bo/buscar?rubro=cambio',
   array['dolar','dolares','pesos','cambio','cambiar','cambista','plata'], 'inicial'),
  ('¿Cómo cruzo a Argentina?',
   'Bermejo está frente a Aguas Blancas (Argentina): se cruza por el puente internacional o en chalana por el río. Llevá documento; los horarios de migraciones cambian, consultá antes de ir.',
   array['argentina','cruzar','frontera','aguas blancas','puente','chalana','migraciones'], 'inicial')
) as v(pregunta, respuesta, etiquetas, creado_por)
where not exists (select 1 from saber_local limit 1);
