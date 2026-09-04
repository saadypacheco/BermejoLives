-- Rubros duplicados, creados sin querer desde el panel.
--
-- El informe del buscador los mostró solos: entre los 64 rubros activos hay
-- cinco con el nombre en minúscula y sin emoji, mientras el resto tiene
-- "🥩 Carnicería y pollería". Ésa es la firma de un rubro creado desde
-- **Admin › Rubros** poniendo la palabra como nombre.
--
--   carniceria             14 comercios   ← el slug es el bueno (0086), el
--   funeraria               3 comercios      nombre quedó pisado
--   gimnasio                5 comercios   ← duplica a `gimnasios` (5)
--   lubricentro             4 comercios   ← duplica a `neumaticos` (70)
--   articulo de limpieza    1 comercio    ← duplica a `limpieza` (4)
--
-- POR QUÉ PASA, Y POR QUÉ NO DIO NINGÚN ERROR
-- ===========================================
-- `crear_rubro` hace `upsert ... on conflict (slug)`, y eso es correcto: el caso
-- común es reactivar uno apagado. Pero el upsert también pisa el NOMBRE. Si
-- alguien resuelve la propuesta "carniceria" creando un rubro, el slug coincide
-- con el que ya existía y le sobreescribe "🥩 Carnicería y pollería" por
-- "carniceria". No falla nada: el rubro sigue funcionando, sólo se llama peor.
--
-- Y cuando el slug NO coincide —"gimnasio" contra "gimnasios"— nace un rubro
-- nuevo que compite con el viejo. Los comercios se reparten entre los dos y
-- ninguno de los dos se ve completo: 5 y 5 en vez de 10.
--
-- Los duplicados se fusionan y el original queda apagado, no borrado: apagarlo
-- conserva la fila por si hay que mirar qué pasó, y `list_rubros` ya filtra por
-- `activo`.

create or replace function fusionar_rubro(p_origen_nombre text, p_destino_slug text)
returns int
language plpgsql
as $$
declare
  v_origen uuid;
  v_destino uuid;
  v_movidos int := 0;
begin
  select id into v_origen from rubros where nombre = p_origen_nombre limit 1;
  select id into v_destino from rubros where slug = p_destino_slug limit 1;
  -- Sin los dos no se hace nada: en QA o en una base nueva el duplicado no
  -- existe, y esta migración tiene que poder correr igual.
  if v_origen is null or v_destino is null or v_origen = v_destino then
    return 0;
  end if;

  -- 1. Los comercios pasan al destino. `on conflict do nothing` porque puede
  --    tener los dos rubros ya.
  insert into comercio_rubros (comercio_id, rubro_id)
  select cr.comercio_id, v_destino from comercio_rubros cr where cr.rubro_id = v_origen
  on conflict do nothing;
  get diagnostics v_movidos = row_count;
  delete from comercio_rubros where rubro_id = v_origen;

  -- 2. Los que lo tenían de PRINCIPAL: sin esto la ficha y el pin del mapa
  --    seguirían apuntando a un rubro apagado.
  update comercios set rubro_id = v_destino where rubro_id = v_origen;

  -- 3. El vocabulario también se muda: si no, las palabras del duplicado dejan
  --    de clasificar a nadie y el rubro bueno pierde justo lo que lo nombraba.
  insert into rubro_palabras (rubro_slug, patron)
  select p_destino_slug, rp.patron
    from rubro_palabras rp
    join rubros r on r.id = v_origen and r.slug = rp.rubro_slug
  on conflict (rubro_slug, patron) do nothing;
  delete from rubro_palabras
   where rubro_slug = (select slug from rubros where id = v_origen);

  update rubros set activo = false where id = v_origen;
  return v_movidos;
end;
$$;

select fusionar_rubro('gimnasio', 'gimnasios');
select fusionar_rubro('lubricentro', 'neumaticos');
select fusionar_rubro('articulo de limpieza', 'limpieza');

-- Los dos que sólo perdieron el nombre: el slug es el correcto, así que basta
-- con devolvérselo.
update rubros set nombre = '🥩 Carnicería y pollería', icono = '🥩'
 where slug = 'carniceria' and nombre !~ 'Carnicer';
update rubros set nombre = '🕯️ Funeraria', icono = '🕯️'
 where slug = 'funeraria' and nombre !~ 'Funeraria';

-- Y que no vuelva a pasar por el mismo camino: crear un rubro que ya existe no
-- puede pisarle el nombre al que está. El upsert sigue reactivando —que es para
-- lo que está— pero sólo escribe el nombre si el de antes estaba vacío.
--
-- No alcanza para el caso "gimnasio" vs "gimnasios", que es un slug distinto y
-- ninguna base de datos puede saber que son lo mismo. Eso lo tiene que ver una
-- persona, y para eso está la lista de rubros con su conteo al lado.
comment on function fusionar_rubro(text, text) is
  'Mueve comercios, principal y vocabulario de un rubro duplicado al bueno, y apaga el duplicado.';
