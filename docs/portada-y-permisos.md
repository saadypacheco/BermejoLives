# Portada desde la galería, modal de admin y quién borra qué — spec

> **Estado: implementada el 12/10/2026.** Sale de
> `docs/analisis-edicion-comercio.md` (P1, P2, P3) y de las decisiones del dueño.

## Decisiones del dueño (11/10)

1. **El agente sólo sube.** No da de baja comercios ni borra fotos. Borrar es del admin.
2. **El publicador edita fichas** (se le suma `comercios.editar`).
3. Se hacen **P1** (portada desde la galería), **P2** (modal de admin) y **P3** (permisos).

## Quién puede qué (después de esto)

| Acción | Admin / moderador | Publicador | Agente | Comerciante |
|---|---|---|---|---|
| Editar datos de la ficha | Sí | **Sí** (nuevo) | Sí, su ciudad | Sí, el suyo |
| Subir fotos a la galería | Sí | Sí | Sí | Sí |
| **Borrar una foto** | Sí | Sí | **No** (nuevo) | Sí, las suyas |
| Al tope: «borrar la más vieja» | Sí | Sí | **No** (sólo cancelar) | Sí |
| Cambiar la portada (subir otra) | **Sí** (nuevo) | **Sí** (nuevo) | Sí | Sí |
| «Usar como portada» (de la galería) | **Sí** (nuevo) | **Sí** (nuevo) | **Sí** (nuevo) | **Sí** (nuevo) |
| Dar de baja un comercio | Sí (`comercios.editar`) | Sí | **No** (nuevo) | No |
| Reactivar un comercio | **Sí** (nuevo) | Sí | No | No |
| Bajar una oferta/novedad ya publicada | **Sí** (nuevo, `moderar`) | Sí | No | Sí, las suyas (ya existe) |

## Contrato (backend ↔ frontend)

`<base>` = `/admin/comercio/{id}` (permiso `comercios.editar`) · `/campo/mis-comercios/{id}`
(agente, misma regla de ciudad que hoy) · `/comercio` (comerciante, su comercio).

1. **Usar una foto de la galería como portada** — `PUT <base>/portada`, JSON `{"foto_id": "<id>"}`.
   - **Intercambio**: la foto elegida pasa a `portada_url`/`portada_thumb_url` y la
     portada anterior entra a la galería en su lugar (misma cantidad de fotos: no
     choca con el tope). Sin portada anterior, la galería queda con una menos.
     No se borra ningún archivo. `portada_pos = null`.
   - 200 → `{"ok": true, "portada_url", "portada_thumb_url", "fotos": [items], "limite": n}`
     (`items` con la misma forma que el listado de fotos de cada perfil).
   - 404 si la foto no es de ese comercio.
2. **Subir una portada nueva** — se mantienen las rutas de hoy:
   `POST /campo/mis-comercios/{id}/foto` y `PUT /comercio/perfil/foto` (campo
   multipart `foto`), y se agrega **`POST /admin/comercio/{id}/foto`** igual a la del
   agente (multipart `foto`, respuesta `{"ok": true, "comercio": {...}}`). En las
   tres: `portada_pos = null` y se borran del disco los archivos de la portada
   anterior si no los usa la galería.
3. **El agente no borra**:
   - `DELETE /campo/mis-comercios/{id}` se elimina (la ruta deja de existir).
   - `DELETE /campo/mis-comercios/{cid}/fotos/{id}` → **403** «Las fotos las borra URUKU. Avisale al admin.»
   - `POST /campo/mis-comercios/{cid}/fotos` con `reemplazar=` → **403** (el 409 de
     tope sigue igual; el front del agente sólo ofrece «Cancelar»).
4. **Baja y reactivación de comercios (admin)**:
   - «Rechazar» comercio (`moderacion.py` ~258, desactiva) pasa a pedir `comercios.editar`.
   - **`POST /admin/comercio/{id}/reactivar`** (`comercios.editar`) → `activo = true`, 200 `{"ok": true}`.
   - **`GET /admin/comercios/dados-de-baja?ciudad=<slug opcional>`** (`comercios.editar`)
     → `{"items": [{"id","slug","nombre","rubro_nombre","portada_thumb_url","updated_at"}]}`.
5. **Bajar una publicación ya aprobada**: `GET /moderacion/publicaciones?estado=aprobado`
   (ya existe) y `POST /moderacion/publicaciones/{id}` `{"estado":"rechazado","motivo"}`
   sobre una aprobada (ya existe; verificar que funciona y que sale del feed).
6. **Publicador**: migración **0146** (`0146_publicador_edita_fichas.sql`, las dos
   carpetas iguales, idempotente) suma `comercios.editar` al rol `publicador` en la
   tabla `roles`; `ROLES_BASE` igual. Descripción: «Carga la cotización, el estado
   del paso y los videos, y corrige fichas.»

## Frontend

- **Galería (`GaleriaUploader`)**, en los tres perfiles: la portada primero con la
  etiqueta «Portada»; cada foto con «Usar como portada». Prop para no mostrar
  «borrar» (agente). En el tope, el agente ve sólo «Cancelar» y «Las fotos las
  borra URUKU: avisale al admin si hay que liberar lugar».
- **Agente**: sin botón de dar de baja comercio ni de borrar foto.
- **Admin › Editar negocio (P2)**:
  - Arriba, bloque «Foto principal» (reusar `FotoPrincipal`): la foto, «Subir otra»
    y «Recorte: más arriba / más abajo» (reemplaza «Encuadre (sin ajustar)»).
  - Después los datos; la galería dentro del modal (sacar el `<Portal>` de
    `FotosComercio` si es lo que la deja afuera — verificarlo).
  - El código: «Código para publicar por WhatsApp: URUKU-XXXX [Copiar]».
  - «Clasificar desde las fotos» abajo y plegado; «Aplicar» actualiza el formulario
    sin cerrar el modal ni perder lo escrito.
- **Permisos (P3)**: sin `comercios.editar`, el modal se abre en sólo lectura (sin
  Guardar/Analizar/portada). Botón «Dar de baja» y vista «Dados de baja» con
  «Reactivar» en Negocios.
- **Publicaciones**: vista «Publicadas» además de «Pendientes», con «Bajar» (pide
  motivo) que la pasa a rechazada.

## Criterios de aceptación

1. Portada A, galería [B, C]: «Usar como portada» en B → portada B, galería [A, C], 2 fotos, ningún archivo borrado, `portada_pos` null. Igual en los tres perfiles.
2. Subir una portada nueva borra del disco la anterior (si no está en la galería) y reinicia el recorte.
3. El admin cambia la portada desde «Editar negocio».
4. El agente no puede borrar fotos, ni reemplazar la más vieja en el tope, ni dar de baja un comercio (API y pantalla).
5. El publicador guarda cambios en una ficha.
6. El admin da de baja, ve la lista de dados de baja y reactiva.
7. El admin baja una oferta publicada y deja de verse en la ficha y en /ofertas.
8. Tests verdes, `tsc` sin errores, `next build` ok, sin emoji.

## Ronda 2 — correcciones de QA y seguridad (11/10)

Decisiones (aplican la regla del dueño «el agente sólo sube» y «el publicador corrige fichas, no maneja cuentas»):

1. **Nada que haga el agente borra archivos.** Al subir una portada nueva, la anterior **pasa a la galería** (aunque supere el tope). Tampoco borra videos ni el catálogo (403, mismo texto que las fotos).
2. **Permiso nuevo `comercios.cuenta`**: cambiar el WhatsApp de la ficha (en `PUT /admin/comercio/{id}`, sólo si cambia), `confiable`, números autorizados, grupos y mensaje al comercio. Lo tienen admin (`*`) y moderador; **el publicador no**. Va al catálogo de permisos (Equipo lo muestra). Migración **0147** lo suma al rol `moderador` (si no está vaciado).
3. **Motivo de baja** `comercios.baja_motivo` (`admin` | `vencido` | `borrador`, privado para anon). «Dados de baja» lista sólo `admin` y los viejos sin motivo; «Reactivar» un `vencido` → 409 «Se reactiva al registrar el pago». Aprobar una publicación ya no reactiva un comercio dado de baja por el admin. La ingesta por grupo ignora comercios inactivos. El comerciante dado de baja por el admin no puede escribir (403).
4. **Oferta bajada**: si el comercio la edita, vuelve a `pendiente` aunque sea confiable.
5. **Publicadas**: `GET /moderacion/publicaciones?estado=aprobado&q=<texto>&offset=<n>` → `{items (máx 100), total (real)}`; `q` busca en título y nombre del comercio.
6. Defensas: 0146 no prende un rol vaciado ni pisa una descripción editada; `_ruta_en_disco` exige la carpeta del comercio; antes de borrar un archivo se mira cualquier fila de galería y cualquier portada; si falla guardar la portada nueva se borran los archivos recién subidos; Pillow con tope de 40 M píxeles y procesado fuera del event loop.
