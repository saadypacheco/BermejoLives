-- Un grupo de WhatsApp por comerciante, atado al comercio.
--
-- EL MODELO
-- =========
--
-- Cada comerciante tiene UN grupo con tres participantes y nada más:
--
--   1. el celular del comercio      — el único que publica
--   2. un celular de URUKU          — la cara de la marca en el grupo
--   3. el celular testigo           — el vinculado a WAHA, el que trae el
--                                     contenido a la base
--
-- POR QUÉ EL GRUPO Y NO EL NÚMERO
-- ===============================
--
-- Hasta ahora la ingesta identificaba al comercio por el teléfono de quien
-- mandaba el mensaje. Eso se rompe de dos maneras que pasan seguido: el
-- comerciante cambia de celular y pierde el vínculo, o publica el hijo desde
-- otro número y el mensaje termina creando un comercio nuevo.
--
-- El grupo no cambia. El JID de un grupo de WhatsApp es estable aunque todos
-- sus miembros cambien de teléfono, así que atar el contenido al grupo en vez
-- de al número sobrevive a las dos cosas.
--
-- Y da una segunda señal gratis: el grupo dice DE QUÉ COMERCIO es el mensaje,
-- y el remitente dice SI ES ÉL o somos nosotros. Cruzar las dos permite
-- detectar a un cuarto participante que nadie invitó — no se descarta en
-- silencio ni se publica: va a moderación.

create table if not exists comercio_wa_grupos (
  grupo_jid   text primary key,                    -- '1203630...@g.us'
  comercio_id uuid not null references comercios(id) on delete cascade,
  nombre      text,                                -- el nombre del grupo, para reconocerlo en el admin
  origen      text not null default 'codigo',      -- 'codigo' | 'admin'
  created_at  timestamptz not null default now(),
  created_by  text
);

-- Un comercio podría tener más de un grupo (se rehízo, se perdió el viejo),
-- pero un grupo pertenece a UN comercio: ésa es la clave primaria de arriba.
create index if not exists idx_wa_grupos_comercio on comercio_wa_grupos(comercio_id);

alter table comercio_wa_grupos enable row level security;
grant all on public.comercio_wa_grupos to service_role;
-- Sin grant a anon/authenticated a propósito: el mapa grupo → comercio dice
-- con qué locales estamos hablando y por dónde. No es dato público.
