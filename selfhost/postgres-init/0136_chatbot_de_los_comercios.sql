-- El chatbot de los comercios (docs/chatbot-comercios.md, aprobada el 5/10/2026).
--
-- Cuatro cosas:
--
-- 1) LAS RESPUESTAS DEL LOCAL VAN EN `saber_local`, con una columna nueva
--    `comercio_id`. NULL = el saber de URUKU (lo de siempre, el que carga el
--    admin). Con valor = una respuesta que cargó el comerciante para SU chatbot
--    («¿hacen envíos?» → «Sí, a todo Bermejo por Bs 10»).
--    El asistente del sitio nunca lee las filas con `comercio_id`, y el chatbot
--    de un comercio sólo lee las suyas: eso lo filtra el backend (repository), y
--    la base lo refuerza para el público (punto 4).
--    Si se borra el comercio, se van con él (on delete cascade). El borrado de
--    una respuesta, en cambio, es soft-delete (`activo = false`), como todo.
--
-- 2) DOS FUNCIONES DE PLAN:
--      asistente_24_7  el chatbot en la ficha, con derivación a WhatsApp
--      asistente_ia    además, Gemini cuando la base no alcanza
--    Destacado: chatbot sin IA (suma `asistente_24_7`). Pro y Empleado Digital:
--    las dos (suman `asistente_ia`; Empleado Digital ya tenía `asistente_24_7`).
--    Se usa `funciones || jsonb_build_object(...)` para sumar sin pisar lo que
--    cada plan ya tiene.
--
-- 3) LO QUE DICE CADA PLAN. Sin precios y sin las redes de URUKU (decisiones
--    del 4 y 5/10/2026). Si alguien ya editó estos textos en Admin › Planes,
--    esta migración los pisa: es a propósito, son los que no hablaban del
--    chatbot.
--
-- 4) QUÉ LEE EL PÚBLICO DE `saber_local`. La 0110 le dio a anon y authenticated
--    `select` de tabla entera con la policy `using (activo)` (la guía de /guia
--    lee el saber de URUKU). Con la columna `comercio_id`, eso dejaba que
--    cualquiera con la anon key leyera las respuestas de TODOS los comercios y
--    `creado_por`. Acá se cierra:
--      - la policy pública sólo ve filas activas SIN comercio (el saber de URUKU);
--      - el `select` pasa a ser por columnas, y `creado_por` queda afuera;
--      - `comercio_id` sí va en el grant: el front filtra por él (is null).
--    Las respuestas de un local sólo las lee el backend (service_role).
--    `planes.funciones` ya está en el grant por columnas de la 0134, así que el
--    front lee las funciones nuevas sin tocar permisos.

-- ------------------------------------------------- 1. respuestas del local
alter table saber_local
  add column if not exists comercio_id uuid references comercios(id) on delete cascade;

comment on column saber_local.comercio_id is
  'NULL = saber de URUKU (el asistente del sitio). Con valor = respuesta cargada por ese comercio para su chatbot; el asistente del sitio nunca la usa.';

create index if not exists idx_saber_local_comercio
  on saber_local (comercio_id) where comercio_id is not null;

-- Garantiza el permiso que ya tenía (idempotente; no abre nada nuevo).
grant all on public.saber_local to service_role;

-- Lo que ve el público: sólo el saber de URUKU, y sin `creado_por`.
drop policy if exists saber_local_public_read on saber_local;
create policy saber_local_public_read on saber_local
  for select to anon, authenticated
  using (activo and comercio_id is null);

revoke select on public.saber_local from anon, authenticated;
grant select (id, pregunta, respuesta, etiquetas, ciudad_id, activo, created_at, updated_at, seccion, comercio_id)
  on public.saber_local to anon, authenticated;

-- ------------------------------------------------- 2. funciones de plan
update planes
   set funciones = funciones || jsonb_build_object('asistente_24_7', true)
 where slug = 'destacado';

update planes
   set funciones = funciones || jsonb_build_object('asistente_ia', true)
 where slug in ('pro', 'empleado_ia');

-- ------------------------------------------------- 3. textos de los planes
update planes set
  incluye = array[
    'Todo lo de Publica',
    'Lugar destacado en los resultados',
    'Chatbot en tu ficha: contesta horario, ofertas, qué vendés y tus respuestas',
    'Lo que no sabe, el cliente te lo pregunta por WhatsApp'
  ]
where slug = 'destacado';

update planes set
  descripcion = 'Tu chatbot con inteligencia artificial: atiende a tus clientes las 24 horas.',
  incluye = array[
    'Todo lo de Destacado',
    'El chatbot contesta con inteligencia artificial lo que no está cargado',
    'Lo que no sabe, el cliente te lo pregunta por WhatsApp'
  ]
where slug = 'pro';
