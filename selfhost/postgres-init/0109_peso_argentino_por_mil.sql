-- La cotización del peso argentino se guarda POR MIL, y la fila decía "100 ARS".
--
-- En la frontera se cotiza así: "1.000 pesos = 6,8 Bs". El valor cargado
-- (7,2) siempre fue por mil, pero el detalle de la fila decía "100 ARS" y el
-- conversor le creyó: dividía por cien y decía que 1.000 pesos eran 72 Bs,
-- diez veces más de lo que dan. Se corrige la etiqueta; el valor está bien.
update cotizaciones set detalle = '1.000 ARS' where clave = 'ars_bob';
