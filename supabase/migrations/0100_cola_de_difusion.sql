-- La cola de difusión: qué oferta salió a qué red, y qué pasó.
--
-- POR QUÉ UNA COLA Y NO MANDAR EN EL MOMENTO
-- ==========================================
-- Publicar en una red es una llamada a un servidor ajeno que puede fallar por
-- razones que no son culpa nuestra: el token venció, Meta está caído, la imagen
-- tardó. Si eso se hace dentro del pedido que aprueba la publicación, el
-- moderador ve un error rojo por algo que ya se aprobó bien — o peor, se traga
-- el error y la oferta nunca sale sin que nadie se entere.
--
-- Con la cola, aprobar siempre funciona y el envío es un estado que se puede
-- mirar, reintentar y contar.
--
-- LA CLAVE ÚNICA ES LA PARTE IMPORTANTE
-- =====================================
-- (publicacion_id, destino) único es lo que impide que la misma oferta salga
-- dos veces a la misma red. Sin eso, un reintento después de un error que en
-- realidad había salido —el caso clásico: la llamada se cortó DESPUÉS de que el
-- otro lado publicó— duplica el posteo en el muro de la marca. Y un feed con la
-- misma oferta dos veces es exactamente lo que hace que la gente deje de
-- seguir.

create table if not exists difusion_cola (
  id             uuid primary key default gen_random_uuid(),
  publicacion_id uuid not null references publicaciones(id) on delete cascade,
  destino        text not null check (destino in ('wa_canal','facebook','instagram')),
  estado         text not null default 'pendiente'
                   check (estado in ('pendiente','enviado','error','omitido')),
  intentos       int  not null default 0,
  motivo         text,                    -- por qué falló, o por qué se omitió
  url_publicada  text,                    -- el posteo, cuando la red lo devuelve
  created_at     timestamptz not null default now(),
  enviado_at     timestamptz,
  unique (publicacion_id, destino)
);

create index if not exists idx_difusion_pendientes
  on difusion_cola(estado, created_at) where estado = 'pendiente';

alter table difusion_cola enable row level security;
grant all on public.difusion_cola to service_role;
-- Sin grant a anon/authenticated: dice qué se publicó, cuándo y qué falló. Es
-- operación interna, no dato del sitio.
