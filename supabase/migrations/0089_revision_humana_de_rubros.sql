-- Revisar la clasificación de a uno, y que la corrección quede.
--
-- LO QUE MEDIMOS, QUE ES LO QUE CAMBIA EL PLAN
-- ============================================
-- De 1080 comercios activos, 851 tienen el rubro principal coherente con lo que
-- el diccionario diría hoy. Los que no cierran son 196, más 33 que no producen
-- ninguna sugerencia. O sea: el problema no son 1080 fichas mal clasificadas,
-- son ~229. Eso es una cola que una persona termina; 1080 no.
--
-- POR QUÉ NO SE ARREGLA SOLO CON UNA CORRIDA MASIVA
-- =================================================
-- El rubro principal (`comercios.rubro_id`) se fija en el alta y no se vuelve a
-- calcular nunca. `reparar_rubro_principal.py` saltea a los que ya tienen uno de
-- verdad, aunque esté equivocado; `completar_rubros` sólo AGREGA rubros. Así,
-- los rubros creados después —carnicería, hoja de coca, taxis, funeraria— nunca
-- llegan a los comercios cargados antes: el comercio termina teniendo el rubro
-- correcto en `comercio_rubros`, pero el panel, la ficha y el color del pin
-- siguen mostrando el viejo.
--
-- Recalcular los 229 a ciegas es tentador y es exactamente lo que no hay que
-- hacer: se llevaría puestas las +200 correcciones hechas a mano, que hoy no se
-- distinguen de las automáticas. De ahí las dos cosas que agrega esta
-- migración.
--
-- 1) LA MARCA
-- ===========
-- `rubro_revisado_at` dice que una PERSONA miró este comercio. Todo lo masivo
-- —el completado, cualquier recálculo futuro— tiene que saltear lo marcado. Sin
-- esto, el trabajo hecho se pierde en silencio: nadie se entera hasta que mira
-- una ficha suelta, semanas después.
--
-- 2) LA CORRECCIÓN GUARDADA
-- =========================
-- `rubro_correcciones` es la memoria. No hay ningún modelo que aprenda solo acá:
-- el clasificador es un diccionario de palabras (`rubro_palabras`) y "aprender"
-- significa escribir en él. Cuando alguien dice "esto no es bebidas, es hoja de
-- coca", lo que hace falta saber después es de qué texto salió el error — y esa
-- respuesta se pierde si sólo se corrige el rubro y se sigue.
--
-- Guardado, el mismo dato sirve tres veces: mide si el diccionario mejora
-- (cuántas correcciones por semana), muestra qué rubros se confunden entre sí, y
-- deja la lista de textos con los que probar una palabra nueva ANTES de
-- guardarla.

alter table comercios add column if not exists rubro_revisado_at timestamptz;
alter table comercios add column if not exists rubro_revisado_por text;

create table if not exists rubro_correcciones (
  id           uuid primary key default gen_random_uuid(),
  comercio_id  uuid not null references comercios(id) on delete cascade,
  -- 'ok' = la clasificación estaba bien. Se guardan igual: sin los aciertos, el
  -- conteo de errores no tiene contra qué medirse y siempre parece que empeora.
  veredicto    text not null check (veredicto in ('ok', 'corregido')),
  rubro_antes  text,
  rubro_nuevo  text,
  -- El texto exacto que se estaba clasificando, congelado. La descripción del
  -- comercio se edita; sin la copia, dentro de un mes no se sabe qué leyó el
  -- clasificador cuando falló.
  texto        text,
  -- Qué palabra se mandó al diccionario a partir de esta corrección, si se mandó.
  palabras     text,
  revisado_por text,
  created_at   timestamptz not null default now()
);

create index if not exists rubro_correcciones_comercio_idx on rubro_correcciones (comercio_id);
create index if not exists rubro_correcciones_fecha_idx on rubro_correcciones (created_at desc);

grant all on rubro_correcciones to service_role;
alter table rubro_correcciones enable row level security;

-- La cola: los que no cierran, sin revisar, los peores primero.
--
-- `rubros_sugeridos` se llama UNA vez por comercio, en el lateral. Llamarla en
-- el select, en el where y en el order —que es lo natural de escribir— la corre
-- tres veces por fila sobre 1080 filas, y el panel tarda lo suficiente como para
-- que nadie lo use.
--
-- `p_estado`:
--   'dudosos' → tienen sugerencia y el principal NO está entre ellas. Son los
--               196: el diccionario sabe qué son y la ficha muestra otra cosa.
--   'sin-datos' → no producen ninguna sugerencia (los 33). Son otro problema:
--                 no falta clasificarlos, falta texto o falta el rubro. Van
--                 aparte para no diluir la cola con casos que no se resuelven
--                 con un clic.
create or replace function rubros_a_revisar(p_estado text default 'dudosos',
                                            p_limite int default 100)
returns table (
  comercio_id uuid,
  codigo text,
  nombre text,
  texto text,
  principal text,
  principal_nombre text,
  sugeridos text[],
  ya_tiene text[],
  portada text
)
language sql stable
as $$
  select
    c.id, c.codigo, c.nombre,
    t.texto,
    r.slug, r.nombre,
    s.sug,
    coalesce((
      select array_agg(r2.slug order by r2.slug)
        from comercio_rubros cr join rubros r2 on r2.id = cr.rubro_id
       where cr.comercio_id = c.id), '{}'),
    c.portada_thumb_url
  from comercios c
  join rubros r on r.id = c.rubro_id
  cross join lateral (
    select concat_ws(' ', c.nombre, c.subcategoria, c.prod_det_ia) as texto) t
  cross join lateral (select rubros_sugeridos(t.texto) as sug) s
 where c.activo
   and c.rubro_revisado_at is null
   and case p_estado
         when 'sin-datos' then cardinality(s.sug) = 0
         else cardinality(s.sug) > 0 and not (r.slug = any(s.sug))
       end
 -- Primero los que más sugerencias tienen: son los que más evidencia acumulan
 -- de estar en el rubro equivocado, y los que más rápido se resuelven.
 order by cardinality(s.sug) desc, c.nombre
 limit p_limite;
$$;

grant execute on function rubros_a_revisar(text, int) to service_role;

-- El tablero de la revisión, para saber si esto avanza o no.
create or replace function rubros_revision_resumen()
returns table (total bigint, revisados bigint, dudosos bigint, sin_datos bigint)
language sql stable
as $$
  with x as (
    select c.rubro_revisado_at, r.slug as principal, s.sug
      from comercios c
      join rubros r on r.id = c.rubro_id
      cross join lateral (
        select rubros_sugeridos(concat_ws(' ', c.nombre, c.subcategoria, c.prod_det_ia)) as sug) s
     where c.activo)
  select
    count(*),
    count(*) filter (where rubro_revisado_at is not null),
    count(*) filter (where rubro_revisado_at is null
                       and cardinality(sug) > 0 and not (principal = any(sug))),
    count(*) filter (where rubro_revisado_at is null and cardinality(sug) = 0)
  from x;
$$;

grant execute on function rubros_revision_resumen() to service_role;
