-- El plan del Empleado Digital (Uruku AI), a Bs 1.250.
--
-- Va como fila y no como código justamente por lo que motiva su precio: un
-- agente 24/7 tiene costos de implementación y mantenimiento que todavía no
-- están medidos, así que el precio va a moverse. Que se mueva desde el panel.
--
-- POR QUÉ `asistente_24_7` SE MUEVE ACÁ Y SALE DE `pro`
-- ====================================================
-- Estaba declarado en Pro (Bs 400) de una conversación anterior. Si el plan de
-- 1.250 no suma NINGUNA función sobre el de 400, no hay nada que vender: el
-- comerciante mira los dos y elige el barato, con razón. Un plan que cuesta
-- tres veces más tiene que poder decir qué trae.
--
-- Si la intención era que Pro también lo tuviera, se le vuelve a poner desde el
-- panel en un clic — para eso están las funciones en jsonb.

insert into planes (slug, nombre, orden, precio_mes, publicaciones_mes,
                    precio_publicacion_extra, permite_extras, funciones,
                    descripcion, visible)
values ('empleado_ia', 'Empleado Digital', 4, 1250, null, 5, true,
        '{"canal_wa": true,
          "asistente_24_7": true,
          "agente_catalogo": true,
          "agente_analista": true,
          "agente_marketing": true,
          "multicanal": true,
          "leads": true}'::jsonb,
        'Un agente que atiende tu WhatsApp, tus redes y tu ficha las 24 horas: '
        'responde, recomienda, toma pedidos y te avisa qué está buscando la gente.',
        true)
on conflict (slug) do nothing;

-- Publicaciones sin límite (`null`): a este precio, contarlas sería mezquino y
-- además el agente publica solo. El tope del canal sigue aplicando igual — ése
-- protege a los seguidores, no al negocio.

update planes
   set funciones = funciones - 'asistente_24_7'
 where slug = 'pro';
