-- 0038: alta mínima de comercio — permite publicar con solo NOMBRE + UBICACIÓN.
-- Antes whatsapp era NOT NULL ("canal del producto"); ahora hay locales sin contacto
-- (el agente los marca en el mapa). El nombre sigue existiendo (el backend pone
-- 'Comercio' por defecto si el agente no lo carga). El contacto queda opcional:
-- la ficha muestra WhatsApp/teléfono solo si existen.
alter table comercios alter column whatsapp drop not null;
