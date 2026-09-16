-- Pro publica hasta 150 por mes (era 120), decidido el 16/9/2026.
--
-- Y la cuota deja de estar escrita dos veces: la página de planes ya arma
-- la línea "Hasta N publicaciones por mes · la extra, Bs X" a partir de
-- `publicaciones_mes`, así que tenerla también como viñeta en `incluye`
-- obligaba a cambiar el número en dos lugares y salía repetida en la
-- tarjeta. Se saca la viñeta; el número vive en una sola columna y se
-- cambia desde Admin › Planes.

update planes set
  publicaciones_mes = 150,
  incluye = array_remove(incluye, 'Hasta 120 publicaciones por mes')
where slug = 'pro';

update planes set incluye = array_remove(incluye, 'Hasta 60 publicaciones por mes')
where slug = 'destacado';

update planes set incluye = array_remove(incluye, 'Hasta 25 publicaciones por mes (ofertas y novedades)')
where slug = 'publica';
