-- 0168 · Retención de los eventos de grupo de WAHA.
--
-- Revisión de E1 (docs/grupos-por-comercio.md §10.1). Los eventos crudos
-- (`wa_group_events.raw`, `participants`) traen teléfonos y LID de terceros. Pasados
-- N días (WA_EVENTS_RETENTION_DAYS, 90 por defecto) el backend los VACÍA: la fila
-- queda (es la bitácora, sin borrado físico) y `purged_at` dice cuándo se vació.
--
-- `wa_lid_map` no necesita columna nueva: los pares inactivos viejos se vacían
-- poniendo `phone` en texto vacío.
--
-- Sólo el backend (service_role) toca estas tablas; anon y authenticated siguen sin
-- ningún permiso.

begin;

alter table public.wa_group_events add column if not exists purged_at timestamptz;

comment on column public.wa_group_events.purged_at is
  'Cuándo se vaciaron raw y participants por la retención. La fila queda.';

create index if not exists idx_wa_group_events_por_vaciar
  on public.wa_group_events (created_at) where purged_at is null;

-- ============================================================ comprobación
do $chk$
declare
  v_rol text;
  v_tabla text;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    foreach v_tabla in array array['public.wa_group_events', 'public.wa_lid_map'] loop
      if has_table_privilege(v_rol, v_tabla, 'select')
         or has_table_privilege(v_rol, v_tabla, 'insert')
         or has_table_privilege(v_rol, v_tabla, 'update')
         or has_table_privilege(v_rol, v_tabla, 'delete') then
        raise exception '0168: % tiene permisos sobre %', v_rol, v_tabla;
      end if;
    end loop;
  end loop;
  foreach v_tabla in array array['public.wa_group_events', 'public.wa_lid_map'] loop
    if not (select relrowsecurity from pg_class where oid = v_tabla::regclass) then
      raise exception '0168: % sin RLS', v_tabla;
    end if;
    if not has_table_privilege('service_role', v_tabla, 'update') then
      raise exception '0168: service_role perdió el permiso de update sobre %', v_tabla;
    end if;
  end loop;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
