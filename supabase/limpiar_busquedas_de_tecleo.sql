-- Borra los fragmentos de tecleo que quedaron registrados como búsquedas.
--
-- POR QUÉ EXISTEN
-- ===============
--
-- El buscador registraba la búsqueda dentro del mismo debounce de 280ms que usa
-- para buscar. Está bien para buscar y es desastroso para medir: escribir
-- "surtidor" dejaba cuatro filas —"surtidr", "surtu", "sutu", "surut"— y las
-- cuatro caían en "buscado sin resultado", que es la lista que dice a qué
-- rubros salir a buscar comercios. La lista más valiosa del panel quedó llena
-- de tecleo.
--
-- Ya está arreglado en el código (se espera un segundo más y, si la persona
-- seguía escribiendo, el fragmento no se registra nunca). Esto limpia lo que
-- quedó de antes.
--
-- NO ES UNA MIGRACIÓN a propósito: borra datos de analítica y esa decisión la
-- tiene que tomar una persona mirando el resultado, no un deploy.
--
--   1) Correr la parte de ARRIBA y leer lo que propone borrar.
--   2) Si convence, descomentar el DELETE del final.

-- ── 1. Qué se borraría ───────────────────────────────────────────────────────
--
-- La regla: una fila es tecleo si su texto es prefijo ESTRICTO de otra búsqueda
-- registrada poco después.
--
-- La ventana es de 15 SEGUNDOS y no de minutos. Medido sobre los datos reales,
-- todos los pares de tecleo caen dentro de segundos: "far" → "farmacias" en dos
-- segundos, "su" → "surtidor" en el mismo tirón. Una ventana ancha empieza a
-- barrer búsquedas de verdad: "ropa" media hora antes que "ropa deportiva" son
-- dos personas distintas preguntando dos cosas distintas, y borrar la primera
-- es perder demanda medida — que es justo lo que este informe existe para
-- mostrar.
--
-- Ante la duda, esta consulta se equivoca dejando de más. Un fragmento que
-- sobrevive ensucia un poco la lista; una búsqueda real borrada no vuelve.
with tecleo as (
  select b.id, b.query as fragmento, b.created_at, s.query as termino_completo
    from busquedas b
    join busquedas s
      on s.query <> b.query
     and lower(s.query) like lower(b.query) || '%'
     and s.created_at between b.created_at and b.created_at + interval '15 seconds'
)
select fragmento, termino_completo, created_at
  from tecleo
 order by created_at desc, fragmento;

-- ── 2. Cuántas son sobre el total ────────────────────────────────────────────
select
  (select count(*) from busquedas) as total,
  (select count(distinct b.id)
     from busquedas b join busquedas s
       on s.query <> b.query
      and lower(s.query) like lower(b.query) || '%'
      and s.created_at between b.created_at and b.created_at + interval '15 seconds'
  ) as tecleo;

-- ── 3. El borrado (descomentar después de mirar lo de arriba) ────────────────
--
-- delete from busquedas b
--  where exists (
--    select 1 from busquedas s
--     where s.query <> b.query
--       and lower(s.query) like lower(b.query) || '%'
--       and s.created_at between b.created_at and b.created_at + interval '15 seconds');
