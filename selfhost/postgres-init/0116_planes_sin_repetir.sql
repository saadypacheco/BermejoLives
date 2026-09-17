-- Empleado Digital decía "Publicaciones sin límite" dos veces: como viñeta
-- en `incluye` y en la línea de cuota que la página arma sola cuando
-- `publicaciones_mes` es NULL. Misma limpieza que la 0112 para los otros.
update planes set incluye = array_remove(incluye, 'Publicaciones sin límite')
where slug = 'empleado_ia';
