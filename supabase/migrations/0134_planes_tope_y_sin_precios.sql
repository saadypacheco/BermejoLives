-- Planes: tope de publicaciones guardadas y precios que el público no lee.
--
-- DOS DECISIONES DEL 4/10/2026 (docs/planes-tope-publicaciones.md)
-- ================================================================
--
-- 1) CUÁNTAS PUBLICACIONES GUARDA UN COMERCIO
--    Cada oferta que entra por WhatsApp deja una foto en el disco del VPS. Sin
--    tope, el disco crece mientras haya comercios publicando, y se llena un día
--    cualquiera sin que nada lo avise. El tope vive en el plan —no en el
--    código— por la misma razón que la cuota mensual: lo cambia quien vende.
--
--    NULL = sin tope (distinto de 0, que no tiene sentido: un plan que guarda
--    cero publicaciones no publica nada). Por eso el CHECK pide > 0.
--
-- 2) LOS PRECIOS DE LOS PLANES NO SE MUESTRAN
--    Siguen en la base y se editan en Admin › Planes, pero `anon` y
--    `authenticated` (el sitio público y los comercios logueados) ya no pueden
--    leer `precio_mes`. No alcanza con que el front no lo pinte: la API de
--    Supabase es pública, y cualquiera con la anon key (que va en el navegador)
--    puede pedir `planes?select=precio_mes`. La única forma de que no se vea es
--    que la base no lo entregue.

-- `default 70` hace dos cosas: los planes que ya existen quedan en 70 (Postgres
-- rellena la columna nueva con el default), y un plan nuevo creado desde Admin ›
-- Planes sin decir nada también guarda 70 en vez de quedar sin tope. NULL hay
-- que pedirlo a propósito. No hay un UPDATE aparte: correr esta migración de
-- nuevo no puede pisar un NULL que alguien puso a mano.
alter table planes add column if not exists publicaciones_guardadas int default 70;

-- Idempotente: se agrega el CHECK sólo si no está. Se busca por nombre porque
-- esta migración es la que lo crea (a diferencia del de 0101, que venía de
-- antes y había que buscar por columna).
do $$
begin
  if not exists (select 1 from pg_constraint
                  where conname = 'planes_publicaciones_guardadas_check'
                    and conrelid = 'public.planes'::regclass) then
    alter table planes
      add constraint planes_publicaciones_guardadas_check
      check (publicaciones_guardadas is null or publicaciones_guardadas > 0);
  end if;
end $$;

comment on column planes.publicaciones_guardadas is
  'Cuántas publicaciones activas guarda un comercio de este plan. Al entrar una más, la más vieja se archiva (activo=false) y se borra su foto del disco. NULL = sin tope.';

-- ── `precio_mes` deja de ser público ────────────────────────────────────────
--
-- Postgres no permite "todas las columnas menos una" con un GRANT de tabla: se
-- quita el SELECT de la tabla entera y se da por columna, listando cada una.
-- Es a propósito que quede explícito. Una columna nueva en `planes` NO queda
-- pública sola: hay que sumarla acá a mano, que es el comportamiento seguro.
--
-- `precio_publicacion_extra` SÍ se muestra (los Bs 5 de cada publicación extra
-- están en el aviso y en la página de planes).
--
-- Columnas de `planes`, de 0101 + 0108 + esta migración:
--   slug, nombre, orden, precio_mes, moneda, publicaciones_mes,
--   precio_publicacion_extra, permite_extras, funciones, descripcion, activo,
--   visible, created_at, updated_at, incluye, publica_meses,
--   publicaciones_guardadas
-- (todas menos `precio_mes`)
--
-- OJO PARA EL FRONT: con esto `select=*` contra `planes` falla con 42501
-- (permission denied) para anon/authenticated. Hay que pedir las columnas por
-- nombre.
revoke select on public.planes from anon, authenticated;
grant select (
  slug, nombre, orden, moneda, publicaciones_mes, precio_publicacion_extra,
  permite_extras, funciones, descripcion, activo, visible, created_at,
  updated_at, incluye, publica_meses, publicaciones_guardadas
) on public.planes to anon, authenticated;

-- El backend usa service_role: sigue leyendo y escribiendo todo, `precio_mes`
-- incluido (Admin › Planes lo edita desde ahí).
grant all on public.planes to service_role;

-- La política de 0101 (`planes_public_read`, sólo los activos) sigue igual: la
-- RLS decide qué FILAS se ven; el GRANT de columnas decide cuáles COLUMNAS.
alter table planes enable row level security;
