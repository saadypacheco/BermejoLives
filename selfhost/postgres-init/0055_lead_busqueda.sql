-- Atar el click a la búsqueda que lo produjo.
--
-- Hoy se guardan las dos mitades por separado y ninguna alcanza sola:
--
--   `busquedas` + `busqueda_comercios`  →  qué se buscó y qué se MOSTRÓ
--   `leads`                             →  a qué comercio se contactó
--
-- Falta el puente. Sin él se puede decir "20 personas buscaron ferretería" y
-- "hubo 3 clicks a WhatsApp", pero no si esos clicks salieron de esa búsqueda ni
-- en qué posición estaba el comercio elegido.
--
-- Ese puente es lo que permite contestar la pregunta que importa —¿el buscador
-- trae lo correcto?— con el comportamiento real en vez de con nuestra opinión:
--
--   · Búsquedas que mostraron resultados y nadie tocó ninguno → la lista tenía
--     algo, pero no lo que la persona buscaba. Es peor que cero resultados,
--     porque desde los números se ve como un éxito.
--   · Posición promedio del elegido → si la gente elige seguido el sexto, el
--     ranking está ordenando mal aunque encuentre bien.
--   · Términos que llevan a contacto → los que de verdad venden.
--
-- Es nullable a propósito: un click desde el mapa, desde la home o desde un link
-- compartido no viene de ninguna búsqueda, y eso no es un dato faltante sino
-- otro camino igual de válido.

alter table leads add column if not exists busqueda_id uuid
  references busquedas(id) on delete set null;

comment on column leads.busqueda_id is
  'Búsqueda que originó este contacto, si vino de una. NULL = llegó por el mapa, '
  'la home o un link directo. Permite medir si el buscador acierta: qué se '
  'mostró contra qué se eligió.';

create index if not exists idx_leads_busqueda on leads (busqueda_id)
  where busqueda_id is not null;

-- El front lo manda al registrar el contacto, así que anon necesita poder
-- escribir la columna (ya tenía insert sobre la tabla).
grant select, insert on leads to anon, authenticated;
