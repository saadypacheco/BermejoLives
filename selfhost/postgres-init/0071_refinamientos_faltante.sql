-- `refinamientos_busqueda` sola, porque en producción quedó sin crearse.
--
-- QUÉ PASÓ
-- ========
--
-- La 0069 traía dos cosas: la nueva `buscar_comercios` y esta función. En
-- producción se corrió la 0070 (que recrea `buscar_comercios` con la columna
-- `total`) sin haber corrido antes la 0069, así que la búsqueda quedó bien y
-- los chips de refinamiento se quedaron sin su función. El frontend los pide,
-- no existe, y como está escrito para no romper devuelve vacío EN SILENCIO: no
-- se veía un error, se veía una pantalla sin chips.
--
-- POR QUÉ NO ALCANZA CON CORRER LA 0069 AHORA
-- ===========================================
--
-- Su `buscar_comercios` es anterior a la de la 0070 y no tiene `total`.
-- Postgres no permite cambiarle el tipo de retorno a una función existente, así
-- que fallaría — y si no fallara sería peor, porque devolvería el contador roto
-- que la 0070 vino a arreglar.
--
-- Esta migración toca ÚNICAMENTE la función que falta. Es segura de correr
-- aunque ya exista, y en una instalación desde cero simplemente la recrea igual.

-- Qué subcategorías hay dentro de una búsqueda, y cuántos comercios tiene cada
-- una. Es lo que dibuja los chips.
--
-- Llama a `buscar_comercios` en vez de repetir su filtro. No es elegancia: si
-- fueran dos consultas separadas podrían separarse con el tiempo, y entonces
-- los chips ofrecerían refinamientos que no coinciden con lo que se está
-- mostrando — el peor error posible acá, porque se ve como que el filtro rompe
-- la búsqueda.
--
-- Se agrupa por el texto sin tildes y en minúsculas, y se muestra la forma más
-- frecuente. NO se usa `subcategoria_norm`: ese campo reordena las palabras y
-- recorta la última sílaba ("muebl", "cepillo de dient"), que sirve para contar
-- pero no para mostrarle a una persona.
create or replace function refinamientos_busqueda(
  q text default null, p_rubro text default null, p_modalidad text default null,
  p_zona text default null, p_ciudad text default null, p_limit int default 10
)
returns table (subcategoria text, n bigint)
language sql stable
as $$
  with encontrados as (
    select b.subcategoria
      from buscar_comercios(q, p_rubro, p_modalidad, p_zona, null, null, p_ciudad, 500, 0) b
     where coalesce(b.subcategoria, '') <> ''
  ),
  agrupado as (
    select lower(unaccent(subcategoria)) as clave,
           mode() within group (order by subcategoria) as etiqueta,
           count(*) as n
      from encontrados
     group by 1
  )
  select etiqueta as subcategoria, n
    from agrupado
   -- Una subcategoría que tiene UN solo comercio no refina nada: tocarla deja
   -- ese resultado solo, que es lo mismo que hacerle clic en la lista.
   where n > 1
   order by n desc, etiqueta
   limit greatest(1, least(p_limit, 30));
$$;

grant execute on function refinamientos_busqueda(text, text, text, text, text, int)
  to anon, authenticated, service_role;
