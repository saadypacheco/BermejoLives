-- De dónde llegó el que abrió una ficha: el QR del volante, la tarjeta de
-- mesa, el QR de la ficha misma, o un enlace compartido.
--
-- Antes de repartir tarjetas de mesa hacía falta poder decir después si
-- trajeron a alguien. La vista de la ficha ya se registra como lead de tipo
-- `vista`; ahora, cuando la URL trae `?ref=`, esa misma fila guarda el
-- origen. Nada nuevo que insertar, ninguna tabla más: un dato en la fila
-- que ya existía. El panel del admin suma las llegadas de los últimos 30
-- días por origen.
--
-- Los valores son `volante-<slug>`, `mesa-<slug>`, `ficha-<slug>` (el QR
-- de la ficha en el sitio) o lo que traiga la difusión (`fb`, `ig`).

alter table leads add column if not exists origen text;
comment on column leads.origen is
  'De dónde llegó: volante-<slug> | mesa-<slug> | ficha-<slug> | fb | ig | … (el ?ref= de la URL). NULL = sin dato.';
create index if not exists idx_leads_origen on leads (origen) where origen is not null;
