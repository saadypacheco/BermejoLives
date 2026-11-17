-- 0197 · El rubro comercial `turismo` (docs/importar-turismo.md).
--
-- Guías autorizados, agencias de viajes, operadoras y complejos turísticos: el importador de la página de turismo
-- se los sugiere (`importar_turismo.RUBRO_TURISMO`) y valida contra la base; sin este rubro quedaban sin rubro.
-- Es un NEGOCIO (comercial = true): se le pide WhatsApp, a diferencia de `para-visitar` (0196).
-- El panel sólo crea rubros desde una propuesta de la cola, por eso va por migración.
-- Sin emoji: el dibujo sale del frontend (IcRubro, slug `turismo`).
--
-- Palabras: sólo las compuestas, que nombran el negocio. «turismo» suelto no va (hoteles y restaurantes lo dicen);
-- «viaje» tampoco («bolso de viaje» es marroquinería).
--
-- Sin borrado físico. Idempotente. Copia idéntica en supabase/migrations/ y selfhost/postgres-init/.

begin;

insert into public.rubros (slug, nombre, icono, orden, comercial)
values ('turismo', 'Turismo', null, 61, true)
on conflict (slug) do update set nombre = excluded.nombre, comercial = true, activo = true;

insert into public.rubro_palabras (rubro_slug, patron) values
  ('turismo', '\m(agencia de viajes|agencia de turismo|operadora de turismo|operador de turismo|guia de turismo|guia turistico)')
on conflict (rubro_slug, patron) do nothing;

do $chk$
begin
  if not exists (select 1 from public.rubros where slug = 'turismo' and comercial and activo) then
    raise exception '0197: el rubro turismo no quedó comercial y activo';
  end if;
  if not exists (select 1 from public.rubro_palabras where rubro_slug = 'turismo') then
    raise exception '0197: faltan las palabras de turismo';
  end if;
end
$chk$;

commit;
