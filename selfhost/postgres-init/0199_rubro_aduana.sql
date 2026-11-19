-- 0199 · El rubro NO comercial `aduana` (docs/vigia-fuentes.md, «Aduana: cómo se corre»).
--
-- Las oficinas de la Aduana Nacional (fronteras, aeropuertos, aduanas interiores, gerencias regionales) son un
-- SERVICIO PÚBLICO, no un negocio: viven en `comercios` con este rubro, como `banos`, `emergencias` o `para-visitar`
-- (0083, 0119, 0196). `comercial = false` es lo que las deja fuera de lo que se cuenta como comercio, del plan y del
-- pedido de WhatsApp; no hace falta nada más: todo lo que distingue lo comercial de lo no comercial lee esa columna.
-- El tipo de oficina (Frontera, Interior, Aeropuerto…) va en `comercios.subcategoria`. Sin emoji: el dibujo sale del
-- frontend (IcRubro, clave `aduana`).
--
-- Palabras: sólo las compuestas, que nombran la oficina. «aduana» suelta NO va: «despachante de aduana» o «agencia
-- de aduana» son negocios privados y la clasificación masiva los pasaría a un rubro sin WhatsApp.
--
-- Sin tabla ni columna nueva: no hay GRANT que dar (`rubros` y `rubro_palabras` ya los tienen); igual se comprueba.
-- Sin borrado físico. Idempotente. Copia idéntica en supabase/migrations/ y selfhost/postgres-init/.

begin;

insert into public.rubros (slug, nombre, icono, orden, comercial)
values ('aduana', 'Aduana', null, 63, false)
on conflict (slug) do update set nombre = excluded.nombre, comercial = false, activo = true;

insert into public.rubro_palabras (rubro_slug, patron) values
  ('aduana', '\m(aduana nacional|aduana frontera|aduana interior|aduana aeropuerto|administracion de aduana|gerencia regional de aduana)')
on conflict (rubro_slug, patron) do nothing;

do $chk$
begin
  if not exists (select 1 from public.rubros where slug = 'aduana' and comercial = false and activo) then
    raise exception '0199: el rubro aduana no quedó como no comercial y activo';
  end if;
  if not exists (select 1 from public.rubro_palabras where rubro_slug = 'aduana') then
    raise exception '0199: faltan las palabras de aduana';
  end if;
  if not has_table_privilege('anon', 'public.rubros', 'select') then
    raise exception '0199: anon no puede leer rubros';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
