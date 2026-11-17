-- 0196 · Lugares para visitar desde la página de turismo (docs/lugares-turismo.md).
--
--  1. El rubro NO comercial `para-visitar` (como `banos`, `emergencias`: 0083, 0113, 0119). Plazas, parques,
--     miradores, museos, iglesias, centros culturales, excursiones y áreas protegidas viven en `comercios` con
--     este rubro; el tipo va en `comercios.subcategoria`. Sin emoji: el dibujo sale del frontend (IcRubro).
--  2. Las palabras del diccionario: sólo las inequívocas. «plaza», «parque» e «iglesia» NO van: clasificarían mal a
--     «Comercial Plaza» o «Parque Industrial». El nombre igual se encuentra por texto.
--  3. `comercios.fuente_url`: el enlace a la página de origen de los datos. Es PÚBLICA (el sitio la usa en la ficha):
--     regla 11 de AGENTS.md, una columna nueva de `comercios` nace privada para anon y se da a mano por columna.
--  4. `comercios_importados.subcategoria` y `.fuente_url`: la sala de espera. Privada como siempre (sólo
--     service_role); las columnas nuevas heredan el permiso de tabla.
--  5. Comprobación: si algo quedó mal, no se aplica.
--
-- Sin borrado físico. Idempotente: se puede correr dos veces. Copia idéntica en supabase/migrations/ y
-- selfhost/postgres-init/.

begin;

-- ───────────────────────────────────────────── 1. el rubro no comercial
insert into public.rubros (slug, nombre, icono, orden, comercial)
values ('para-visitar', 'Para visitar', null, 62, false)
on conflict (slug) do update set nombre = excluded.nombre, comercial = false, activo = true;

-- ───────────────────────────────────────────── 2. palabras (sin acentos, minúsculas)
-- «museo», «mirador» y «centro cultural» NO van: hay hoteles, restaurantes y peñas que se llaman así
-- («Hotel El Mirador») y la clasificación masiva los pasaría a para-visitar. El nombre igual se encuentra por texto.
insert into public.rubro_palabras (rubro_slug, patron) values
  ('para-visitar', '\m(area protegida|reserva biologica|parque nacional|lugares turisticos|que visitar)')
on conflict (rubro_slug, patron) do nothing;

-- ───────────────────────────────────────────── 3. el enlace de origen, público por columna
alter table public.comercios add column if not exists fuente_url text;
comment on column public.comercios.fuente_url is
  'Página de origen de los datos (p. ej. la ficha en tarijaturismo.com). Sólo el enlace: su texto y sus fotos no se copian.';
grant select (fuente_url) on public.comercios to anon, authenticated;

-- ───────────────────────────────────────────── 4. la sala de espera: privada
alter table public.comercios_importados add column if not exists subcategoria text;
alter table public.comercios_importados add column if not exists fuente_url   text;
comment on column public.comercios_importados.subcategoria is
  'Tipo de lugar (Plaza, Parque, Mirador, Museo, Biblioteca o archivo, Iglesia, Patrimonio, Centro cultural, Excursión, Área protegida).';
comment on column public.comercios_importados.fuente_url is
  'Página de origen de los datos (privado hasta que se promueve; allá pasa a comercios.fuente_url).';
alter table public.comercios_importados enable row level security;
revoke all on public.comercios_importados from public, anon, authenticated;
grant all on public.comercios_importados to service_role;

-- ───────────────────────────────────────────── 5. comprobación
do $chk$
declare
  v_rol text;
begin
  if not exists (select 1 from public.rubros where slug = 'para-visitar' and comercial = false and activo) then
    raise exception '0196: el rubro para-visitar no quedó como no comercial y activo';
  end if;
  if not exists (select 1 from public.rubro_palabras where rubro_slug = 'para-visitar') then
    raise exception '0196: faltan las palabras de para-visitar';
  end if;
  foreach v_rol in array array['anon', 'authenticated'] loop
    if not has_column_privilege(v_rol, 'public.comercios', 'fuente_url', 'select') then
      raise exception '0196: % no puede leer comercios.fuente_url', v_rol;
    end if;
    if has_any_column_privilege(v_rol, 'public.comercios_importados', 'select') then
      raise exception '0196: % puede leer comercios_importados', v_rol;
    end if;
  end loop;
  if not has_table_privilege('service_role', 'public.comercios_importados', 'insert')
     or not has_table_privilege('service_role', 'public.comercios_importados', 'update') then
    raise exception '0196: service_role no puede escribir comercios_importados';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
