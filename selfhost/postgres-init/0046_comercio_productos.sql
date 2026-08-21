-- Campo `productos`: qué vende el local, en palabras del cliente.
--
-- Hasta ahora todo iba en `descripcion`, mezclando dos cosas distintas:
--   · descripcion → qué ES el negocio, para que lo lea una persona.
--   · productos   → QUÉ VENDE, una lista para que lo lea el buscador.
-- Separarlos permite pedirle al agente una lista de productos sin arruinar el
-- texto de la ficha, y le da al clasificador de rubros una señal mucho más
-- limpia (una lista de sustantivos, sin frases de marketing en el medio).
--
-- Va indexado en la búsqueda: es el campo que hace que un local con neumáticos,
-- zapatillas y televisores aparezca en las tres búsquedas.

alter table comercios add column if not exists productos text;

-- La columna `busqueda` es GENERATED, así que para sumarle un campo hay que
-- rehacerla. Se recrea también el índice GIN, que cae con la columna.
alter table comercios drop column if exists busqueda;

alter table comercios add column busqueda tsvector
  generated always as (
    to_tsvector('spanish',
      coalesce(nombre, '')      || ' ' ||
      coalesce(descripcion, '') || ' ' ||
      coalesce(productos, '')   || ' ' ||
      coalesce(direccion, ''))
  ) stored;

create index if not exists idx_comercios_busqueda on comercios using gin (busqueda);

comment on column comercios.productos is
  'Lista de productos que vende, separados por coma. Alimenta la búsqueda y la '
  'sugerencia de rubros. Se carga en el recorrido: 4-5 productos concretos.';
