-- Fotos del local según el plan (docs/fotos-por-plan.md, parte A).
--
-- Hasta ahora la galería tenía un tope fijo de 10 fotos en el código. Ahora el
-- tope vive en el plan —lo cambia quien vende, desde Admin › Planes— y el
-- comercio puede comprar fotos extra.
--
-- 1. `planes.fotos_max`: cuántas fotos de galería admite un comercio de ese plan
--    con el pago al día (o de cortesía). Vencido o suspendido: el del plan
--    gratis. NULL = «no lo definieron»: el backend usa el del plan gratis (un
--    plan nuevo creado en Admin sin este dato no queda sin tope ni en cero).
--    Valores iniciales: gratis 50 · publica 100 · destacado, premium, pro y
--    empleado_ia 300. Sólo se completan las filas que lo tienen en NULL: correr
--    la migración de nuevo no pisa un valor que alguien editó.
--
-- 2. `comercios.fotos_extra`: las fotos extra que el comercio compró (Bs 5 c/u,
--    el mismo `precio_publicacion_extra` del plan). Se suman al tope del plan.
--    Cada una deja además una fila en `cargos_extra` con concepto 'foto_extra'
--    (esa tabla ya tenía la columna `concepto`; no hace falta tocarla: el
--    `unique (publicacion_id)` no molesta porque estos cargos van sin
--    publicación, y NULL no choca con NULL).
--
-- GRANTS (migración 0134: el público no lee precios)
-- ==================================================
-- `fotos_max` no es un precio ni un secreto: se puede leer, y se suma a la lista
-- de columnas que anon/authenticated ya tienen sobre `planes`. `precio_mes`
-- sigue sin entregarse. El GRANT por columna es aditivo: no se revoca nada.
-- `comercios.fotos_extra` queda cubierto por el grant de tabla vigente; si la
-- 0145 pasa a columnas, no hace falta incluirla (el sitio público no la usa).
--
-- Idempotente: se puede correr dos veces.

alter table planes add column if not exists fotos_max int;

do $$
begin
  if not exists (select 1 from pg_constraint
                  where conname = 'planes_fotos_max_check'
                    and conrelid = 'public.planes'::regclass) then
    alter table planes
      add constraint planes_fotos_max_check
      check (fotos_max is null or (fotos_max >= 0 and fotos_max <= 1000));
  end if;
end $$;

comment on column planes.fotos_max is
  'Cuántas fotos de galería admite un comercio de este plan con el pago al día (o de cortesía). Vencido o suspendido usa el del plan gratis. NULL = usa el del plan gratis. Editable en Admin › Planes.';

update planes set fotos_max = 50  where fotos_max is null and slug = 'gratis';
update planes set fotos_max = 100 where fotos_max is null and slug = 'publica';
update planes set fotos_max = 300 where fotos_max is null
   and slug in ('destacado', 'premium', 'pro', 'empleado_ia');

alter table comercios add column if not exists fotos_extra int not null default 0;

do $$
begin
  if not exists (select 1 from pg_constraint
                  where conname = 'comercios_fotos_extra_check'
                    and conrelid = 'public.comercios'::regclass) then
    alter table comercios
      add constraint comercios_fotos_extra_check check (fotos_extra >= 0);
  end if;
end $$;

comment on column comercios.fotos_extra is
  'Fotos extra de galería que el comercio compró (Bs 5 c/u). Se suman al tope de su plan. Las sube el backend al registrar el cargo (cargos_extra.concepto = foto_extra).';

-- Visible para el público junto con el resto de las columnas no sensibles.
grant select (fotos_max) on public.planes to anon, authenticated;
grant all on public.planes to service_role;

notify pgrst, 'reload schema';
