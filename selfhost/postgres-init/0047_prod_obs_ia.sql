-- Separar lo que observó un HUMANO de lo que detectó la IA.
--
-- El modelo de carga cambia: en el recorrido se sacan 1-2 fotos, se toma la
-- ubicación y, si se puede, el celular. La descripción, el rubro, la
-- subcategoría y los productos se calculan DESPUÉS, a partir de las fotos.
--
-- La regla que ordena todo esto: **el dato humano no se toca nunca**.
--   · prod_obs_human → lo que vio una persona. Se carga a mano y es la fuente de
--     verdad para corregir a la IA. Si mañana el análisis detecta mal algo, se
--     escribe acá para que se reevalúe — pero lo que ya estaba no se pisa.
--   · prod_det_ia    → lo que detectó el modelo. Es reemplazable: se puede
--     volver a correr el análisis sin miedo.
--   · descripcion    → pasa a generarse de las fotos, así que dejaría de ser
--     dato humano. Por eso el backfill de abajo.

-- `productos` se creó hace un día y está vacío en los 92 comercios: el rename es
-- seguro y evita terminar con dos campos que significan lo mismo.
alter table comercios rename column productos to prod_obs_human;

alter table comercios add column if not exists prod_det_ia text;
alter table comercios add column if not exists subcategoria text;
-- Cuándo se corrió el análisis. NULL = nunca analizado, que es el filtro para
-- saber sobre cuáles hay que correrlo.
alter table comercios add column if not exists ia_analizado_at timestamptz;

-- Backfill: todo lo que hoy está en `descripcion` fue escrito por el agente en
-- el recorrido — es observación humana. Se preserva antes de que la IA empiece
-- a sobrescribir `descripcion`.
update comercios
   set prod_obs_human = descripcion
 where prod_obs_human is null
   and coalesce(descripcion, '') <> '';

-- La búsqueda mira los cuatro campos: da igual si la palabra la escribió el
-- agente o la detectó el modelo, el comprador tiene que encontrar el local.
alter table comercios drop column if exists busqueda;

alter table comercios add column busqueda tsvector
  generated always as (
    to_tsvector('spanish',
      coalesce(nombre, '')         || ' ' ||
      coalesce(descripcion, '')    || ' ' ||
      coalesce(prod_obs_human, '') || ' ' ||
      coalesce(prod_det_ia, '')    || ' ' ||
      coalesce(subcategoria, '')   || ' ' ||
      coalesce(direccion, ''))
  ) stored;

create index if not exists idx_comercios_busqueda on comercios using gin (busqueda);
-- Para listar los pendientes de analizar sin escanear la tabla entera.
create index if not exists idx_comercios_sin_analizar
  on comercios (created_at) where ia_analizado_at is null and activo;

comment on column comercios.prod_obs_human is
  'Productos observados por una persona. Dato humano: NO se sobrescribe nunca, '
  'ni por la IA ni por un reproceso. Sirve para corregir al modelo.';
comment on column comercios.prod_det_ia is
  'Productos detectados por la IA a partir de las fotos. Reemplazable: se puede '
  'volver a generar.';
comment on column comercios.subcategoria is
  'Subcategoría propuesta por la IA (ej. Juguetería → "peluches"). Texto libre '
  'por ahora: la taxonomía cerrada se va a derivar de lo que el modelo devuelva '
  'sobre comercios reales, no de una lista inventada de antemano.';
