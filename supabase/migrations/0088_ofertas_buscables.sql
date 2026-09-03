-- Una foto sin texto es una oferta que no se puede buscar.
--
-- `publicaciones.busqueda` sale de `titulo + descripcion`. Y en la ingesta,
-- cuando la oferta trae foto, el título se deja en NULL a propósito —la oferta
-- ES la foto, y un "200 bs" de título no ayuda a nadie— mientras que la
-- descripción es el texto que mandó el comerciante.
--
-- Entonces una foto mandada sin texto queda con el índice VACÍO: la oferta
-- existe, se ve en la ficha del comercio y en la tarjeta del buscador, y no
-- aparece nunca en una búsqueda. Y mandar la foto sola es exactamente lo que va
-- a hacer un comerciante apurado, que son todos.
--
-- Se agrega una columna aparte para lo que lee la IA de la imagen, y se suma al
-- índice. APARTE y no encima de `descripcion`: ese texto lo escribió una
-- persona y pisarlo sería perder lo único que el comerciante dijo con sus
-- palabras. Es la misma regla que separa `prod_obs_human` de `prod_det_ia` en
-- los comercios.

alter table publicaciones
  add column if not exists terminos_ia   text,
  add column if not exists ia_analizado_at timestamptz;

comment on column publicaciones.terminos_ia is
  'Lo que la IA leyó en la foto de la oferta: qué es y con qué palabras lo '
  'buscaría un cliente. Entra al índice de búsqueda. NO pisa `descripcion`, '
  'que es lo que escribió el comerciante.';
comment on column publicaciones.ia_analizado_at is
  'NULL = todavía no se analizó. Es el filtro de la cola de análisis.';

-- Se rehace el índice para que incluya los términos.
alter table publicaciones drop column if exists busqueda;
alter table publicaciones add column busqueda tsvector generated always as (
  to_tsvector('spanish_unaccent',
    coalesce(titulo, '') || ' ' ||
    coalesce(descripcion, '') || ' ' ||
    coalesce(terminos_ia, ''))
) stored;
create index if not exists idx_pub_busqueda on publicaciones using gin (busqueda);

-- Para listar las pendientes de analizar sin escanear la tabla entera.
create index if not exists idx_pub_sin_analizar on publicaciones (created_at)
  where ia_analizado_at is null and activo;
