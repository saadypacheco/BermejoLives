-- «Qué hay acá» (docs/que-hay-aca.md): el interés en un plan que anota el agente y la lista de
-- la ciudad con sus fotos.
--
-- 1. `comercio_eventos.detalle jsonb`: datos de un evento (para `interes_plan`: {plan, nota}).
--    La tabla es PRIVADA desde la 0149 (revoke all + grant sólo a service_role): una columna
--    nueva hereda eso, no hace falta tocar permisos. Sin default: los eventos viejos quedan en null.
--
-- 2. `contar_fotos_comercios(uuid[])`: cuántas fotos de galería tiene cada comercio, en UNA
--    consulta agrupada (la lista de campo trae toda la ciudad: contar de a uno serían miles de
--    viajes). Devuelve UN jsonb {comercio_id: n} y no una fila por comercio, porque PostgREST
--    corta en 1000 filas sin avisar. Sólo comercios con al menos una foto (el resto es 0).
--    Sólo la ejecuta el backend.
--
-- Idempotente: se puede correr dos veces. Una transacción, con comprobación al final.

begin;

alter table public.comercio_eventos add column if not exists detalle jsonb;
comment on column public.comercio_eventos.detalle is
  'Datos del evento (privado, sólo el backend). interes_plan: {"plan": slug, "nota": texto|null}. Nunca guarda claves.';

create or replace function public.contar_fotos_comercios(p_ids uuid[])
returns jsonb
language sql
stable
set search_path = public, pg_temp
as $fn$
  select coalesce(jsonb_object_agg(t.comercio_id::text, t.n), '{}'::jsonb)
    from (
      select f.comercio_id, count(*)::int as n
        from public.comercio_fotos f
       where f.comercio_id = any(p_ids)
       group by f.comercio_id
    ) t
$fn$;

comment on function public.contar_fotos_comercios(uuid[]) is
  'Fotos de galería por comercio: {comercio_id: n}. Sólo comercios con fotos. Sólo el backend.';

revoke all on function public.contar_fotos_comercios(uuid[]) from public, anon, authenticated;
grant execute on function public.contar_fotos_comercios(uuid[]) to service_role;

do $chk$
declare
  v_rol text;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    if has_column_privilege(v_rol, 'public.comercio_eventos', 'detalle', 'select') then
      raise exception '0151: % puede leer comercio_eventos.detalle', v_rol;
    end if;
    if has_function_privilege(v_rol, 'public.contar_fotos_comercios(uuid[])', 'execute') then
      raise exception '0151: % puede ejecutar contar_fotos_comercios', v_rol;
    end if;
  end loop;
  if not has_function_privilege('service_role', 'public.contar_fotos_comercios(uuid[])', 'execute') then
    raise exception '0151: service_role no puede ejecutar contar_fotos_comercios';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
