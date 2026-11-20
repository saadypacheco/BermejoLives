-- 0201 · Clima por ciudad (docs/home-ciudades.md §9).
--
--  1. `clima_ciudades`: el último clima de cada ciudad activa con coordenadas (temperatura y descripción en texto,
--     sin emoji). Lo escribe el loop de clima del backend con `service_role`, una fila por ciudad, que se pisa en
--     cada vuelta; si una ciudad falla se queda el dato anterior (por eso `actualizado_en`: el front no muestra un
--     dato de más de 3 horas).
--  2. La tabla `clima` (id = 1, Bermejo, con su override manual) NO cambia.
--  3. RLS activo; lectura pública (anon y authenticated); escritura sólo de service_role. Sin DELETE: el clima de
--     una ciudad que se apaga queda como está y el front lo ignora por viejo.
--
-- Idempotente: se puede correr dos veces. Copia idéntica en supabase/migrations/ y selfhost/postgres-init/.

begin;

-- ───────────────────────────────────────────── 1. la tabla
create table if not exists public.clima_ciudades (
  ciudad_id      uuid primary key references public.ciudades(id),
  temp_c         numeric,
  descripcion    text,
  actualizado_en timestamptz not null default now()
);
comment on table public.clima_ciudades is
  'Último clima de cada ciudad (Open-Meteo, cada 30 min). Lo escribe el backend; el sitio lo lee y lo oculta si pasó de 3 horas.';
comment on column public.clima_ciudades.temp_c is 'Temperatura actual en grados Celsius.';
comment on column public.clima_ciudades.descripcion is
  'Descripción en español del código WMO (Despejado, Nublado, Lluvia…). Sin emoji: el ícono lo elige el front.';
comment on column public.clima_ciudades.actualizado_en is 'Cuándo el backend guardó este dato.';

-- ───────────────────────────────────────────── 2. RLS: lectura pública
alter table public.clima_ciudades enable row level security;

drop policy if exists clima_ciudades_lectura_publica on public.clima_ciudades;
create policy clima_ciudades_lectura_publica on public.clima_ciudades
  for select to anon, authenticated
  using (true);

-- ───────────────────────────────────────────── 3. GRANTs explícitos (sin DELETE)
-- Los privilegios por defecto del esquema (0090) le dan todo a service_role: se le saca todo y se le da sólo lo
-- que usa el backend (leer, insertar y actualizar).
revoke all on public.clima_ciudades from public, anon, authenticated, service_role;
grant select on public.clima_ciudades to anon, authenticated;
grant select, insert, update on public.clima_ciudades to service_role;

-- ───────────────────────────────────────────── 4. comprobación
do $chk$
declare
  v_rol text;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    if not has_table_privilege(v_rol, 'public.clima_ciudades', 'select') then
      raise exception '0201: % no puede leer clima_ciudades', v_rol;
    end if;
    if has_table_privilege(v_rol, 'public.clima_ciudades', 'insert')
       or has_table_privilege(v_rol, 'public.clima_ciudades', 'update')
       or has_table_privilege(v_rol, 'public.clima_ciudades', 'delete') then
      raise exception '0201: % puede escribir en clima_ciudades y es sólo lectura', v_rol;
    end if;
  end loop;
  if not has_table_privilege('service_role', 'public.clima_ciudades', 'insert')
     or not has_table_privilege('service_role', 'public.clima_ciudades', 'update') then
    raise exception '0201: service_role no puede escribir en clima_ciudades';
  end if;
  if has_table_privilege('service_role', 'public.clima_ciudades', 'delete')
     or has_table_privilege('service_role', 'public.clima_ciudades', 'truncate') then
    raise exception '0201: service_role puede borrar o vaciar clima_ciudades y no tiene que poder';
  end if;
  if not (select relrowsecurity from pg_class where oid = 'public.clima_ciudades'::regclass) then
    raise exception '0201: clima_ciudades sin RLS';
  end if;
end
$chk$;

commit;

notify pgrst, 'reload schema';
