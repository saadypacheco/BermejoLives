-- Los planes, como quedaron el 15/9/2026.
--
-- Cambió lo que se vende: ya no hay canal de WhatsApp en ningún plan (el
-- canal no se usa), y sí hay chatbot —el asistente que atiende a los
-- clientes del local en su ficha— desde Pro. Y cada plan dice en una frase
-- qué es: el gratis sólo aparece en el mapa; Publica tiene el negocio
-- digitalizado; Destacado además sale en las redes de URUKU; Pro tiene su
-- chatbot; Empleado Digital, los agentes.
--
-- Dos columnas nuevas:
--   incluye        lo que se lista en la página de planes, editable desde el
--                  panel. Antes estaba escrito en el código, y cambiar una
--                  viñeta era un deploy.
--   publica_meses  cuántos meses desde el alta puede publicar el plan. NULL =
--                  siempre. El gratis puede publicar dos meses en esta etapa
--                  de arranque; después sigue en el mapa y nada más.

alter table planes add column if not exists incluye text[] not null default '{}';
alter table planes add column if not exists publica_meses int;

update planes set
  nombre = 'Básico', precio_mes = 0, publicaciones_mes = 50, publica_meses = 2,
  funciones = '{}'::jsonb,
  descripcion = 'Aparecé en el mapa de Bermejo. Gratis por un mes.',
  incluye = array['Tu local en el mapa, con nombre, rubro y cómo llegar', 'Te encuentran buscando lo que vendés']
where slug = 'gratis';

update planes set
  nombre = 'Publica', precio_mes = 70, publicaciones_mes = 25, publica_meses = null,
  funciones = '{"negocio_digital": true}'::jsonb,
  descripcion = 'Tu negocio digitalizado.',
  incluye = array['Todo lo del Básico', 'Ficha completa: fotos, horario, WhatsApp, qué vendés', 'Hasta 25 publicaciones por mes (ofertas y novedades)', 'Tus ofertas en la búsqueda y en tu ficha']
where slug = 'publica';

update planes set
  nombre = 'Destacado', precio_mes = 140, publicaciones_mes = 60, publica_meses = null,
  funciones = '{"negocio_digital": true, "redes": true}'::jsonb,
  descripcion = 'Tu negocio digitalizado, y tus ofertas en las redes de URUKU.',
  incluye = array['Todo lo de Publica', 'Hasta 60 publicaciones por mes', 'Tus ofertas salen en el Facebook y el Instagram de URUKU', 'Lugar destacado en los resultados']
where slug = 'destacado';

update planes set
  nombre = 'Pro', precio_mes = 400, publicaciones_mes = 120, publica_meses = null,
  funciones = '{"negocio_digital": true, "redes": true, "asistente_24_7": true}'::jsonb,
  descripcion = 'Tu chatbot: atiende a tus clientes las 24 horas.',
  incluye = array['Todo lo de Destacado', 'Hasta 120 publicaciones por mes', 'Chatbot en tu ficha: contesta horario, precios, ofertas y cómo llegar, las 24 horas', 'Lo que el chatbot no sabe te llega a vos']
where slug = 'pro';

update planes set
  nombre = 'Empleado Digital', precio_mes = 1250, publicaciones_mes = null, publica_meses = null,
  funciones = '{"negocio_digital": true, "redes": true, "asistente_24_7": true, "agente_catalogo": true, "agente_analista": true, "agente_marketing": true, "multicanal": true, "leads": true}'::jsonb,
  descripcion = 'Un empleado digital: el chatbot más los agentes que cargan tu catálogo, leen la demanda y arman tus promociones.',
  incluye = array['Todo lo de Pro', 'Publicaciones sin límite', 'Agente Catálogo: cargá productos con fotos', 'Agente Analista: qué busca la gente y qué te falta', 'Agente Marketing: promociones y contenido para tus redes', 'Tus clientes por WhatsApp, Instagram y Messenger cuando el canal esté']
where slug = 'empleado_ia';

-- El viejo Premium queda oculto, sin canal, para los que todavía lo tienen.
update planes set funciones = '{"negocio_digital": true, "redes": true}'::jsonb where slug = 'premium';
