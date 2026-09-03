-- "otros" es el descarte, no un rubro: no puede convivir con uno de verdad.
--
-- Apareció al revisar lo que dejó `completar_rubros.py`: Kathy GOLOSINAS quedó
-- con `kiosco, otros`. El script sólo SUMA rubros y descarta `otros` de sus
-- propuestas, así que no lo puso él — estaba de antes, de cuando el comercio no
-- tenía ninguno.
--
-- Por qué molesta, y no es cosmético:
--
--   · `incompletoDe` marca "sin clasificar" mirando el rubro PRINCIPAL. Un
--     comercio con `otros` de principal figura como incompleto para siempre
--     aunque ya tenga kiosco, y ensucia la cola de trabajo que sirve para saber
--     qué falta.
--   · El chip "Otros (a clasificar)" del buscador muestra comercios que sí
--     están clasificados, así que el número deja de significar lo que dice.
--   · Y el día que alguien limpie los comercios que quedaron en `otros`, estos
--     van a aparecer en esa lista sin tener nada que arreglar.
--
-- Se saca `otros` de todo comercio que tenga al menos otro rubro. A los que
-- SÓLO tienen `otros` no se los toca: ahí el descarte es la verdad y sacarlo
-- los dejaría sin ningún rubro, que es peor — desaparecerían de la cola en vez
-- de arreglarse.

delete from comercio_rubros cr
 using rubros r
 where r.id = cr.rubro_id
   and r.slug = 'otros'
   and exists (
     select 1 from comercio_rubros cr2
       join rubros r2 on r2.id = cr2.rubro_id
      where cr2.comercio_id = cr.comercio_id
        and r2.slug <> 'otros');

-- Y el rubro PRINCIPAL, que vive en `comercios.rubro_id` y es el que se muestra
-- en la tarjeta: si quedó apuntando a `otros` teniendo rubros de verdad, pasa a
-- ser uno de ésos. Sin esto, la ficha seguiría diciendo "Otros (a clasificar)"
-- aunque la relación ya esté limpia.
update comercios c
   set rubro_id = (
     select cr.rubro_id from comercio_rubros cr
       join rubros r on r.id = cr.rubro_id
      where cr.comercio_id = c.id and r.slug <> 'otros'
      order by r.orden
      limit 1)
 where c.activo
   and exists (select 1 from rubros r where r.id = c.rubro_id and r.slug = 'otros')
   and exists (
     select 1 from comercio_rubros cr join rubros r on r.id = cr.rubro_id
      where cr.comercio_id = c.id and r.slug <> 'otros');
