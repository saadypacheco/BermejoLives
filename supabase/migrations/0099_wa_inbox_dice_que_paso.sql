-- Qué pasó con cada mensaje que entró por WhatsApp.
--
-- EL CANAL ESTÁ CONSTRUIDO Y ES CIEGO
-- ===================================
-- La ingesta funciona: identifica al comercio por el grupo, por el número o por
-- el código, baja la foto, publica o manda a moderación. Y cuando NO publica
-- —el grupo no está atado, el mensaje vino sin código, el plan no alcanza— el
-- crudo queda guardado en `wa_inbox` y el motivo se va en una línea de log.
--
-- Eso alcanza mientras el canal esté apagado. El día que se encienda, la
-- primera pregunta va a ser "le dije al comerciante que mande la foto, ¿llegó?"
-- y la única forma de contestarla sería entrar por SSH a leer logs. En la
-- práctica eso significa que nadie la contesta: se le pide al comerciante que
-- mande de nuevo, y la segunda vez tampoco se publica por la misma razón que la
-- primera.
--
-- El resultado se guarda en la MISMA fila que el mensaje crudo. Una tabla
-- aparte obligaría a cruzarlas para contestar la única pregunta que importa, y
-- abre la posibilidad de que un mensaje quede sin resultado y nadie lo note.
--
-- `resultado` es corto y estable, para poder filtrar y contar:
--
--   publicada        salió a la cola o al feed
--   ignorada         no era para nosotros (mensaje propio, evento que no es
--                    mensaje, confirmación de código)
--   sin_comercio     llegó bien pero no se supo de quién es
--   sin_permiso      el comercio existe pero su plan no incluye publicar
--   error            algo se rompió procesándolo
--
-- `motivo` es la frase que ya devolvía la ingesta, en castellano y para leer.
-- Los dos: el primero para agrupar, el segundo para entender. Guardar sólo la
-- frase obliga a hacer `like` sobre texto libre para contar, y eso se rompe el
-- día que alguien la reescribe.

alter table wa_inbox add column if not exists resultado text;
alter table wa_inbox add column if not exists motivo text;
-- De qué comercio se trataba, cuando se supo. Es lo que permite contestar
-- "¿llegó lo de la ferretería?" sin buscar por número.
alter table wa_inbox add column if not exists comercio_id uuid references comercios(id) on delete set null;

-- La bandeja se mira por fecha y filtrando por resultado. Sin el índice, cada
-- apertura del panel es un scan completo de una tabla que sólo crece.
create index if not exists idx_wa_inbox_created on wa_inbox (created_at desc);
create index if not exists idx_wa_inbox_resultado on wa_inbox (resultado, created_at desc);

comment on column wa_inbox.resultado is
  'publicada | ignorada | sin_comercio | sin_permiso | error. NULL = llegó antes de que se registrara el resultado.';
