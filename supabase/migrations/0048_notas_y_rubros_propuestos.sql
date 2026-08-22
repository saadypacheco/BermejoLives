-- Dos cosas que salen de usar el análisis por fotos sobre comercios reales.
--
-- 1) `descripcion` pasa a ser 100% de la IA: se regenera de las fotos en cada
--    análisis, sin mirar lo que había. Para que eso no borre lo que escribe el
--    agente en "Algo más del negocio" —modalidad, origen de la mercadería,
--    horarios especiales— esa nota se muda a su propia columna.
--
--    Queda entonces bien separado quién es dueño de cada campo:
--      · prod_obs_human, notas → persona. No los toca nadie más.
--      · descripcion, prod_det_ia, subcategoria → IA. Reemplazables.
--
-- 2) Las categorías que el modelo propone y no existen en la taxonomía se
--    guardan. Es el modelo diciendo qué rubro o subcategoría le falta al
--    sistema, sacado de locales reales en vez de una lista inventada de
--    antemano. Con volumen, las que más se repiten son las que hay que crear.

alter table comercios add column if not exists notas text;

-- Lo que hoy está en descripcion lo escribió una persona en el recorrido: se
-- preserva ANTES de que la IA empiece a sobrescribir.
update comercios
   set notas = descripcion
 where notas is null
   and coalesce(descripcion, '') <> '';

comment on column comercios.notas is
  'Observaciones de la persona que relevó el local (modalidad, origen de la '
  'mercadería, horarios). Dato humano: la IA no lo toca.';
comment on column comercios.descripcion is
  'Generada por la IA a partir de las fotos. Se regenera en cada análisis: no '
  'guardar acá nada escrito a mano, va en notas.';


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

-- El texto se indexa en la búsqueda igual que el resto: si el modelo escribió
-- "peluches" y no hay rubro para eso, el comprador que busque "peluches" tiene
-- que encontrar igual el local por su subcategoría.
alter table comercios drop column if exists busqueda;

alter table comercios add column busqueda tsvector
  generated always as (
    to_tsvector('spanish',
      coalesce(nombre, '')         || ' ' ||
      coalesce(descripcion, '')    || ' ' ||
      coalesce(prod_obs_human, '') || ' ' ||
      coalesce(prod_det_ia, '')    || ' ' ||
      coalesce(subcategoria, '')   || ' ' ||
      coalesce(notas, '')          || ' ' ||
      coalesce(direccion, ''))
  ) stored;

create index if not exists idx_comercios_busqueda on comercios using gin (busqueda);
