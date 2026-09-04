-- Los permisos que faltaban en `reclamos` y `solicitudes_cambio_numero`.
--
-- Las dos daban 500 en producción, y las dos son las ÚNICAS tablas creadas
-- después de la 0002 que no tienen un `grant ... to service_role` propio.
--
-- POR QUÉ ESTABAN ASÍ, Y POR QUÉ NO SE NOTÓ ANTES
-- ==============================================
-- La 0002 hace `grant all on all tables in schema public to service_role`, que
-- se lee como si cubriera todo y cubre sólo las tablas que EXISTÍAN en ese
-- momento. No hay `alter default privileges`, así que cada tabla nueva tiene que
-- pedir el suyo. Todas lo piden —usuarios, favoritos, comercio_fotos, lugares,
-- comercio_numeros, rubros_propuestos— menos estas dos.
--
-- El comentario que quedó en la 0021 y la 0024 dice: "el backend inserta con
-- service_role (bypassa RLS)". Ahí está el error, y es de los que no se ven:
-- saltear RLS y tener permiso sobre la tabla son dos cosas distintas. En
-- Supabase Cloud no se notaba porque su instalación trae los privilegios por
-- defecto puestos; en el Postgres propio del VPS no están, y por eso las dos
-- empezaron a fallar justo al mudarse a producción.
--
-- Un reclamo sin responder es una persona esperando, y una solicitud de cambio
-- de número sin atender es un comercio que no puede recibir reservas.

grant all on public.reclamos to service_role;
grant all on public.solicitudes_cambio_numero to service_role;

-- Y que no vuelva a pasar con la próxima tabla: desde acá, todo lo que se cree
-- en `public` nace con permiso para service_role. Es la línea que faltaba en la
-- 0002 — sin ella, la regla dependía de que nadie se olvidara, y alcanzó con
-- dos olvidos en 88 migraciones para tirar abajo dos pantallas del panel.
alter default privileges in schema public grant all on tables to service_role;
alter default privileges in schema public grant all on sequences to service_role;
