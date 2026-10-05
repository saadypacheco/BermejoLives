# Planes: cuota, extra y tope de publicaciones guardadas — spec

> **Estado: implementada el 4/10/2026, sin desplegar.** Ver «Estado» al final.

## Qué pidió el usuario

1. Los precios de los planes no se muestran: ni al público ni en los avisos al
   comerciante. Siguen en la base y se editan en Admin › Planes.
2. Cuando un comercio llega a la cuota mensual de su plan, se le avisa y cada
   publicación extra cuesta Bs 5.
3. Un comercio guarda como máximo N publicaciones (70 por defecto, editable por
   plan). Cuando entra una más, la más vieja se archiva y **su foto se borra del
   disco**, para que el disco no crezca sin control.

## Lo que ya existe y lo que falta

| | Hoy | Falta |
|---|---|---|
| Cuota mensual por plan | `planes.publicaciones_mes`, se cuenta en `services/planes.py` | — |
| Aviso + cobro de Bs 5 | Sólo en la ingesta por WhatsApp (`ingest.py`) | En `POST /comercio/publicar` (lo que publica el comercio desde su cuenta) |
| Precios a la vista | Aviso al comerciante, asistente del sitio, `/planes`, y la API pública (anon lee `planes.precio_mes`) | Sacarlos de los cuatro |
| Tope de guardadas | No existe | Todo |

## Decisiones

- **El tope es por plan**: columna nueva `planes.publicaciones_guardadas`, 70 en
  todos los planes. `NULL` = sin tope. Se edita en Admin › Planes.
- **Cuentan todas las publicaciones activas del comercio**, del estado que sean
  (pendiente, aprobada, rechazada): todas ocupan disco. Se archiva siempre la
  más vieja por `created_at`.
- **Archivar = `activo = false` + borrar el archivo de la foto.** La fila queda:
  la regla del proyecto es soft-delete, y lo que ocupa espacio es la foto, no
  la fila.
- **Sólo se borran archivos propios**: los que están bajo
  `FOTOS_PUBLIC_BASE_URL`. Una URL externa (un producto de la tienda, un link)
  no se toca. Y no se borra un archivo que otra fila activa siga usando.
- **El tope se aplica en todos los caminos que crean publicaciones**, incluido
  el explorador: el disco es el mismo. **La cuota y el cobro, sólo cuando
  publica el comercio** (WhatsApp y su cuenta). Lo que sube URUKU (explorador,
  video del alta de campo) no se le cobra.
- **Una publicación archivada no sale a las redes**: si estaba en la cola de
  difusión, se descarta con motivo.
- **Archivar nunca rompe la publicación nueva.** Si falla, se anota en el log y
  la nueva sale igual.
- **El aviso no tiene precios de planes.** Dice que llegó a la cuota, que las
  siguientes cuestan Bs 5 (el extra sí se muestra), y que existe el plan de
  arriba con su cuota, sin precio.

## Limitación conocida

Con WAHA en sólo lectura el aviso por WhatsApp no le llega al comerciante: queda
en Recepción como «AVISARLE». Desde su cuenta en el sitio sí lo ve, porque
viene en la respuesta.

## Criterios de aceptación

1. Un comercio con 70 publicaciones activas publica una más: queda con 70
   activas, la más vieja tiene `activo = false` y su archivo ya no está en el
   disco.
2. Una foto con URL externa nunca se borra, ni una que use otra fila activa.
3. Con `publicaciones_guardadas = NULL` no se archiva nada.
4. Un comercio que pasó su cuota y publica desde su cuenta: la publicación sale,
   se registra un cargo de Bs 5 y la respuesta trae el aviso. Si el plan no
   permite extras o se le venció el período, no sale y el error lo explica.
5. Ningún aviso, respuesta del asistente ni la página `/planes` muestra el
   precio de un plan. `anon` no puede leer `planes.precio_mes`.
6. Una publicación archivada que estaba en la cola de difusión no se envía.
7. Admin › Planes edita `publicaciones_guardadas`.
8. Tests del backend verdes y `tsc` sin errores.

## Estado

**Verificado:** 979 tests del backend en verde y `tsc` sin errores. Pasó QA y
revisión de código; sus hallazgos están integrados. **Sin verificar:** la
migración no se corrió contra una base real y nada se abrió en un navegador.

**Más estricto que la spec, a propósito:** sólo se borra una foto si su URL es
exactamente `<base>/<slug-del-comercio>/ofertas/<archivo>`, sin `?`, `#` ni
caracteres codificados. Con la regla de la spec, un comercio podía hacer borrar
la foto de una oferta de otro pegando su URL con un `?x=1` al final. Cualquier
otra URL archiva la publicación pero deja el archivo, y lo anota en el registro
(`planes.foto_no_se_borra`).

**Agregado en la revisión:**
- Se archivan como máximo 5 publicaciones por cada publicación nueva. Un tope
  bajado por error (7 en vez de 70) no borra todo de una.
- Los destacados de producto (`producto_ref_id`) no cuentan para el tope ni se
  archivan: llevan un costo que se cobra con la suscripción.
- El tope en Admin acepta hasta 100.000.

**Pendientes de producto:**
- Las fotos del explorador, que nadie moderó todavía, ocupan lugar en el tope y
  pueden desplazar ofertas aprobadas del comerciante.
- La cuota cuenta sólo las publicaciones aprobadas. Las de un comercio no
  confiable que esperan moderación no consumen cuota ni se cobran.
- Si el comerciante reintenta después de un timeout desde su cuenta, la
  publicación y el cargo se duplican.
- Si un comercio cambió de slug, sus fotos viejas quedan en la carpeta anterior
  y no se borran.
- La guía de venta de los agentes tiene precios escritos a mano y viajan en el
  código del navegador.

## Fuera de alcance

- Fijar precios nuevos o precios por ciudad.
- Borrar las fotos de publicaciones viejas que ya existen (hoy hay una).
- El tope de publicaciones a las redes por plan, y el chatbot con y sin IA:
  son la próxima spec.
