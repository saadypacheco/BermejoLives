-- Qué pasaría si agrego esta palabra al diccionario, ANTES de agregarla.
--
-- POR QUÉ ESTO Y NO IA
-- ====================
--
-- El error que costó más horas en el diccionario no fue de criterio, fue de
-- alcance: una palabra correcta que además aparece en otro lado. "papa frita"
-- describe bien a la comida rápida y está en todos los kioscos. "bar" está
-- dentro de "barbería". "detergente" lo vende cualquier almacén. "reja" aparece
-- en la descripción de una foto tomada a través de una reja.
--
-- Eso no es una pregunta de juicio: es contable. Antes de guardar la palabra se
-- puede contar exactamente a cuántos comercios alcanza y cuáles son. Un modelo
-- puede advertirlo o no; esta consulta acierta siempre.
--
-- Usa EL MISMO texto y la misma normalización que `rubros_sugeridos`, que es la
-- función que clasifica de verdad. Una vista previa que mira otra cosa que el
-- clasificador es peor que ninguna: tranquiliza sobre algo que no se probó.

create or replace function previsualizar_patron(p_patron text, p_rubro text default null)
returns table (
  comercio_id uuid,
  codigo text,
  nombre text,
  vende text,
  ya_lo_tiene boolean,
  otros_rubros text[]
)
language sql stable
as $$
  select
    c.id,
    c.codigo,
    c.nombre,
    left(coalesce(c.prod_det_ia, ''), 90),
    -- Los que ya están en ese rubro no son ganancia: la palabra no los agrega,
    -- sólo los confirma. Separarlos es lo que muestra el alcance REAL.
    p_rubro is not null and exists (
      select 1 from comercio_rubros cr join rubros r on r.id = cr.rubro_id
       where cr.comercio_id = c.id and r.slug = p_rubro),
    -- En qué otros rubros está. Si los alcanzados son todos de un rubro
    -- distinto, la palabra está arrastrando y no clasificando.
    coalesce((
      select array_agg(r2.slug order by r2.slug)
        from comercio_rubros cr2 join rubros r2 on r2.id = cr2.rubro_id
       where cr2.comercio_id = c.id
         and (p_rubro is null or r2.slug <> p_rubro)), '{}')
  from comercios c
 where c.activo
   -- Mismo texto que arma `completar_rubros`: productos detectados por la IA,
   -- subcategoría y nombre. SIN sinónimos, igual que ahí.
   and unaccent(lower(concat_ws(' ', c.prod_det_ia, c.subcategoria, c.nombre))) ~ p_patron
 order by 5, c.nombre
 limit 200;
$$;

grant execute on function previsualizar_patron(text, text) to service_role;
