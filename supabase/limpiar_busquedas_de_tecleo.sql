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
-- registrada poco después. "surtu" antes de "surtidor" es tecleo; "ropa" antes
-- de "ropa deportiva" media hora más tarde son dos búsquedas distintas, por eso
-- la ventana de tiempo.
with tecleo as (
  select b.id, b.query as fragmento, b.created_at, s.query as termino_completo
    from busquedas b
    join busquedas s
      on s.query <> b.query
     and lower(s.query) like lower(b.query) || '%'
     and s.created_at between b.created_at and b.created_at + interval '2 minutes'
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
      and s.created_at between b.created_at and b.created_at + interval '2 minutes'
  ) as tecleo;

-- ── 3. El borrado (descomentar después de mirar lo de arriba) ────────────────
--
-- delete from busquedas b
--  where exists (
--    select 1 from busquedas s
--     where s.query <> b.query
--       and lower(s.query) like lower(b.query) || '%'
--       and s.created_at between b.created_at and b.created_at + interval '2 minutes');
