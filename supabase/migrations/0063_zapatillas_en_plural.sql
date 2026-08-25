-- Ocho locales se llaman "Zapatillas Americanas" y el rubro que se llama igual
-- no los reconoce.
--
-- El rubro `calzado-usado` se muestra como "👟 Calzado usado / zapatillas
-- americanas". Su patrón, desde la 0045:
--
--     \m(zapatilla americana|calzado usado)
--
-- `zapatilla americana` en singular exige que después de "zapatilla" venga un
-- espacio. En el cartel dice "Zapatillas Americanas" — viene una `s`. El rubro
-- no matchea el nombre que lo nombra.
--
-- Es la tercera vez que aparece la misma clase de error en dos días: `calza`
-- matcheando "calzado" (0061), `toalla` matcheando "toallita" (0062), y ahora
-- el singular que no llega al plural. Las tres salen de tratar un patrón como
-- si fuera una palabra: `\m` abre la palabra y lo que sigue es una cadena
-- literal, así que "zapatilla americana" NO contiene a "zapatillas americanas".
--
-- La forma correcta es escribir el plural en el patrón, no confiar en que el
-- prefijo lo cubra: `zapatillas? americanas?` matchea las cuatro combinaciones.
--
-- POR QUÉ ACÁ Y NO EN `ropa-americana`
-- ====================================
--
-- Porque son zapatillas. Meterlas en ropa americana es el error de la 0057 otra
-- vez: quien filtra "Ropa americana" buscando una campera recibiría ocho
-- zapaterías. Los locales que venden las dos cosas quedan en los dos rubros
-- solos — para eso existe comercio_rubros — y lo decide lo que la IA vio en la
-- vidriera, no el nombre.
--
-- El buscador ya los encontraba: matchea contra el nombre del comercio, y ahí
-- dice "Zapatillas Americanas". Lo que esto arregla es el filtro por categoría,
-- que es la otra mitad — el que no escribe y toca un chip.

delete from rubro_palabras
 where rubro_slug = 'calzado-usado' and patron like '%calzado usado%';

insert into rubro_palabras (rubro_slug, patron) values
  ('calzado-usado', '\m(zapatillas? americanas?|zapatillas? usadas?|calzados? usados?|calzado americano|zapatillas? de fardo|championes? americanos?)')
on conflict (rubro_slug, patron) do nothing;

-- Y el otro lado del puente: que buscar "zapatillas americanas" devuelva la
-- CATEGORÍA además de los locales. El buscador matchea contra el nombre del
-- rubro, y ése ya la nombra ("Calzado usado / zapatillas americanas"), así que
-- acá no hace falta tocar nada — es la misma razón por la que la 0060 tuvo que
-- renombrar `bebidas` a "Bebidas y licorería". Queda anotado para que nadie lo
-- "arregle" de nuevo.
