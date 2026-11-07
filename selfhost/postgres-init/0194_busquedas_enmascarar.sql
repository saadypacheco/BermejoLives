-- 0194 · Búsquedas: enmascarar lo que ya se guardó + «sesiones» en comercio_origins.
--
--  1. `busquedas.query` guardaba lo que la gente escribe en el buscador. Desde la medición v2 el backend enmascara mails y
--     teléfonos ANTES de guardar (services/site_metrics.enmascarar_busqueda), pero el enmascarado de entonces dejaba pasar
--     «+591 712-34567», «71 23 45 67» (dígitos con separadores) y «juan (at) gmail (dot) com». El backend ya los
--     enmascara; esta migración aplica LA MISMA regla a las filas viejas, UNA vez. Es un UPDATE, nunca un DELETE:
--     `busquedas` es historia del negocio (AGENTS.md §7).
--
--     Las dos expresiones regulares son copia exacta de `PATRON_MAIL` y `PATRON_DIGITOS` de backend/app/core/text.py
--     (dialecto común de Python y de Postgres: tests/test_enmascarar_busquedas.py compara los textos y corre la
--     misma secuencia en Python). Orden: juntar espacios → mails → dígitos → recortar y tope de 100 caracteres.
--     Sólo toca las filas que cambian (`is distinct from`), así que volver a correrla no hace nada.
--
--  2. `comercio_origins` (el «de dónde llegaron» de «Mi comercio») ahora devuelve también `sesiones`: las sesiones DISTINTAS
--     de cada (origen, referido). La regla «un sitio desconocido sólo se nombra con 3 o más sesiones» no puede apoyarse
--     en `n` (páginas vistas): una sola sesión mandando `first=true` tres veces la saltearía. Mismo contrato de antes
--     más una clave; los permisos no cambian (CREATE OR REPLACE conserva los grants; se repiten por claridad).
--
-- PERMISOS (regla 11 de AGENTS.md): ninguna columna nueva. Idempotente. Todo en una transacción.
-- Copia idéntica en supabase/migrations/ y selfhost/postgres-init/.

begin;

-- ───────────────────────────────────────────── 1. búsquedas ya guardadas
update public.busquedas b
   set query = m.nuevo
  from (select id,
               left(btrim(
                 regexp_replace(
                   regexp_replace(
                     regexp_replace(query, '\s+', ' ', 'g'),
                     '\w[\w.+-]*\s?(?:@|\(\s?at\s?\)|\[\s?at\s?\])\s?\w[\w-]*(?:\s?(?:\.|\(\s?dot\s?\)|\[\s?dot\s?\])\s?\w[\w-]*)+', '[mail]', 'gi'),
                   '\+?\d(?:[ .()-]*\d){5,}', '#', 'g')
               ), 100) as nuevo
          from public.busquedas
         where query is not null) m
 where m.id = b.id
   and m.nuevo is distinct from b.query;

-- ───────────────────────────────────────────── 2. comercio_origins con «sesiones»
create or replace function public.comercio_origins(p_comercio uuid, p_from date)
returns jsonb
language sql
stable
set search_path = public, pg_temp
as $$
  select coalesce(jsonb_agg(jsonb_build_object('origen', t.origen, 'referido', t.referido, 'n', t.n, 'sesiones', t.sesiones)
                            order by t.n desc), '[]'::jsonb)
    from (select v.origen, v.referido, count(*) as n, count(distinct v.sesion) as sesiones
            from public.comercios c
            join public.visitas v on v.ruta = '/comercios/' || c.slug
           where c.id = p_comercio
             and v.primera
             and v.dia >= p_from
           group by v.origen, v.referido
           order by n desc
           limit 100) t;
$$;

revoke execute on function public.comercio_origins(uuid, date) from public, anon, authenticated;
grant  execute on function public.comercio_origins(uuid, date) to service_role;

-- ───────────────────────────────────────────── comprobación
do $chk$
begin
  if has_function_privilege('anon', 'public.comercio_origins(uuid, date)', 'execute')
     or has_function_privilege('authenticated', 'public.comercio_origins(uuid, date)', 'execute') then
    raise exception '0194: comercio_origins no puede ser ejecutable por anon ni authenticated';
  end if;
  if not has_function_privilege('service_role', 'public.comercio_origins(uuid, date)', 'execute') then
    raise exception '0194: service_role no puede ejecutar comercio_origins';
  end if;
  if pg_get_functiondef('public.comercio_origins(uuid, date)'::regprocedure) not like '%count(distinct v.sesion)%' then
    raise exception '0194: comercio_origins no devuelve las sesiones distintas';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
