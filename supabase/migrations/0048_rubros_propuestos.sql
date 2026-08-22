-- Categorías que la IA propone y no existen en la taxonomía.
--
-- Es el modelo diciendo qué rubro o subcategoría le falta al sistema, sacado de
-- locales reales en vez de una lista inventada de antemano. Con volumen, las que
-- más se repiten son las que hay que crear.
--
-- Se guardan aunque la propuesta no se aplique: que el modelo haya pedido una
-- categoría inexistente es información válida por sí sola.

create table if not exists rubros_propuestos (
  id          uuid primary key default gen_random_uuid(),
  texto       text not null,                  -- lo que devolvió el modelo, tal cual
  normalizado text not null,                  -- para agrupar variantes
  comercio_id uuid references comercios(id) on delete set null,
  created_at  timestamptz not null default now()
);

create index if not exists idx_rubros_propuestos_norm on rubros_propuestos (normalizado);

alter table rubros_propuestos enable row level security;
grant all on public.rubros_propuestos to service_role;

comment on table rubros_propuestos is
  'Categorías que la IA propuso y no existen en `rubros`. Alimentan la decisión '
  'de qué rubros o subcategorías crear, con evidencia de comercios reales.';

-- `descripcion` pasa a ser 100% de la IA: se regenera de las fotos en cada
-- análisis. Lo que había escrito el agente ya quedó preservado en
-- prod_obs_human por la migración 0047, así que no se pierde nada.
comment on column comercios.descripcion is
  'Generada por la IA a partir de las fotos. Se regenera en cada análisis: no '
  'guardar acá nada escrito a mano.';
