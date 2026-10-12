# Edición de un comercio por perfil — y cómo se cambia la portada

> Análisis funcional (11/10). Sólo lectura de código: no se tocó nada. Las referencias `archivo:línea` son del commit `3053888`.
> Pregunta del dueño: **«¿cómo cambio la foto principal (portada) del comercio?»**

## 0. Respuesta corta

| Perfil | ¿Puede cambiar la portada hoy? | ¿Puede usar una foto de la galería como portada? |
|---|---|---|
| **Admin** (panel `/admin`) | **No.** No hay endpoint ni botón. Sólo puede mover el *encuadre* de la que ya está. | No |
| **Publicador** | **No.** Además no puede guardar nada del modal (403). | No |
| **Agente de campo** (`/campo`) | **Sí**: subiendo una foto nueva («Cambiar foto»). | No |
| **Comerciante** (`/mi-comercio`) | **Sí**: subiendo una foto nueva («Cambiar la foto principal»). | No |

En ningún perfil se puede elegir una foto que ya está en la galería: la portada es una columna aparte (`comercios.portada_url`), no una foto de `comercio_fotos` marcada.

## 1. Paso a paso, hoy

### Admin
1. Negocios → tocar la fila o el lápiz → se abre «Editar negocio» (`frontend/app/admin/page.tsx:1836`, `:1920`).
2. Arriba de todo: «Clasificar desde las fotos / Analizar» (`page.tsx:2163`, componente en `:2504-2624`). No tiene nada que ver con la portada.
3. A la izquierda del nombre: la portada actual en 200×100 y la barra «Encuadre (sin ajustar)» (`page.tsx:2170-2195`). La barra sólo mueve el recorte vertical (`portada_pos`, 0-100) y se guarda con «Guardar cambios» (`page.tsx:2092` → `PUT /admin/comercio/{id}`, `backend/app/api/moderacion.py:304`).
4. **No hay forma de reemplazarla.** `EditarComercioBody` no acepta `portada_url` (`moderacion.py:281-305`) y no existe un `POST /admin/comercio/{id}/portada` (rutas de admin listadas en `moderacion.py:315-2450`: ninguna toca la portada).
5. La sección «Fotos del local» (`FotosComercio`, `page.tsx:2632-2721`) muestra la portada primero, sin etiqueta y sin acciones (`:2673`, `:2687`), y deja agregar o borrar fotos de la galería. **No tiene «usar como portada».**
6. **Bug probable:** `FotosComercio` devuelve su contenido envuelto en `<Portal>` (`page.tsx:2678`), y `Portal` lo monta en `document.body` (`page.tsx:2492-2497`). Queda fuera del modal y debajo del fondo oscuro fijo (`zIndex: 999`, `page.tsx:2127`). Leyendo el código, la galería del modal no se ve o no se puede tocar. **Hay que confirmarlo en el navegador.**
7. Atajo indirecto (no documentado y sin verificar en uso): un admin tiene el permiso `*`, así que pasa `require_agente` (`backend/app/core/permisos.py:105`). Si su usuario tiene una ciudad asignada, `/campo` lo deja editar los comercios de esa ciudad (`backend/app/api/campo.py:495-499`). Por ahí sí podría cambiar la portada.

### Publicador
- Por defecto tiene los permisos `contenido` y `moderar` (`permisos.py:62-66`). Ese rol se puede editar desde Equipo, así que en producción podría ser distinto.
- Ve la sección Negocios porque esa sección pide `moderar` (`frontend/components/admin/secciones.ts:42`), y puede abrir el mismo modal.
- Pero **«Guardar cambios» le devuelve 403**: el `PUT` pide `comercios.editar` (`moderacion.py:319`). «Analizar» también le da 403 (`:1584`). La portada no la puede cambiar, igual que el admin.
- Lo que sí le funciona: subir y borrar fotos de galería (`moderacion.py:1542`, `:1568`, piden `moderar`), verificar (`:245-255`) y **rechazar, que desactiva el comercio** (`:258-268`).

### Agente de campo
1. `/campo` → su comercio → «Completar comercio» → sección «Fotos y videos» (`frontend/components/completar-comercio.tsx:517`).
2. «Foto de la vidriera (portada)» → «Cambiar foto». Si ya tenía portada, pide confirmación (`:341`) y abre la cámara o la galería del teléfono (`:525-529`).
3. La foto se sube sola, sin «Guardar»: `POST /campo/mis-comercios/{id}/foto` (`campo.py:645-662`). Pisa `portada_url` y `portada_thumb_url`.
4. Puede cambiar la portada de cualquier comercio de **su ciudad**, no sólo de los que cargó él (`campo.py:484-500`).

### Comerciante
1. `/mi-comercio` → «Fotos y videos» → recuadro «Foto principal» → «Cambiar la foto principal» (`frontend/app/mi-comercio/page.tsx:512`, componente en `frontend/components/foto-principal.tsx:20-76`).
2. Hay un segundo camino: la miniatura de 58 px en «Editar mi negocio» (`mi-comercio/page.tsx:763`, `:707-717`).
3. Los dos van a `PUT /comercio/perfil/foto` (`backend/app/api/comercio.py:673-693`).

### Qué pasa con la portada vieja (agente y comerciante)
- **El archivo no se borra nunca.** Los dos endpoints sólo pisan las columnas (`comercio.py:691`, `campo.py:660`). El JPG viejo y su miniatura quedan huérfanos en el disco. La limpieza de la galería no los alcanza: no están en `comercio_fotos`, y además `borrar_archivos` protege a propósito la portada vigente (`backend/app/services/fotos_galeria.py:272`).
- **El encuadre (`portada_pos`) no se reinicia.** La foto nueva hereda el recorte que alguien eligió para la anterior (`comercio.py:691`, `campo.py:660`: no tocan `portada_pos`).
- Sin portada, la ficha pública usa la primera foto de la galería (`frontend/components/ficha-galeria.tsx:27`). Los resultados y el mapa, en cambio, **no** tienen ese respaldo: sólo leen `portada_thumb_url` (`supabase/migrations/0078_miniatura_en_resultados.sql:78`).

## 2. Matriz campo × perfil

Leyenda: **S** = puede · **N** = no puede · **B** = el backend lo acepta pero no hay pantalla · **403** = ve el botón pero falla.

| Campo | Admin | Publicador | Agente | Comerciante |
|---|---|---|---|---|
| Nombre / «sin cartel» | S `moderacion.py:282-285` · UI `page.tsx:2196-2223` | 403 | S `campo.py:530` · UI `completar-comercio.tsx:599` | S `comercio.py:53` |
| Rubros + principal | S `moderacion.py:305` · UI `page.tsx:2255-2291` | 403 | S `campo.py:538` | S `comercio.py:573` |
| WhatsApp | S, lo cambia y anula las claves `moderacion.py:337-353` | 403 | Sólo si está vacío `campo.py:581-597` | N (va por «Cambié de número») `comercio.py:617-618` |
| Teléfono, email | S `moderacion.py:287,292` | 403 | S `campo.py:533-534` | S `comercio.py:53` |
| Productos observados | S `moderacion.py:289` | 403 | S `campo.py:537` | S `comercio.py:53` |
| Descripción | S `moderacion.py:288` | 403 | N (no está en `campo.py:529-562`) | S `comercio.py:53` |
| Modalidad | S `moderacion.py:290` | 403 | S `campo.py:535` | S `comercio.py:55` |
| Horario | S `moderacion.py:297`, y en lote `:383` | 403 | S `campo.py:562` | S `comercio.py:55` |
| Dirección / referencia | S `moderacion.py:291` | 403 | S `campo.py:536` | S `comercio.py:55` |
| Ubicación GPS (lat/lng) | **N** (no está en `moderacion.py:281-305`) | N | N | S `comercio.py:56` |
| Mercado / puesto | **N** | N | S `campo.py:541-542` | N |
| Redes y sitio web | S `moderacion.py:293-296` | 403 | S `campo.py:543-546` | S `comercio.py:54` |
| Lo que suma: pedido mínimo, factura, envíos | **B** `moderacion.py:298-300` (no están en el modal) | N | S `campo.py:554-558` | S `comercio.py:58` |
| Lo que suma: pasero, talles, canal WA, catálogo | **N** | N | S `campo.py:548-557`, PDF `:619` | S `comercio.py:58`, PDF `:647` |
| **Portada (reemplazar)** | **N** | **N** | S `campo.py:645` | S `comercio.py:673` |
| **Portada desde la galería** | N | N | N | N |
| Encuadre de la portada | S `moderacion.py:304` · UI `page.tsx:2184` | 403 | N | N |
| Galería: subir / borrar | S `moderacion.py:1536-1576` (UI con el bug de §1) | S (mismo endpoint, permiso `moderar`) | S `campo.py:830-872` | S `comercio.py:1149-1182`, puede pagar extra |
| Analizar con IA | S `moderacion.py:1580` | 403 | N | N |
| Verificado | S, sólo marcar `moderacion.py:245` (desmarcar: no encontrado) | S | N | N |
| Confiable | S `moderacion.py:1007` (UI en Suscripciones `page.tsx:2816`) | N | N | N |
| Plan / cortesía | S `moderacion.py:836` (`pagos`) | N | N | N |
| Suspender / reactivar | S `moderacion.py:862-883` (`pagos`) | N | N | N |
| Activo (baja lógica) | S vía «Rechazar» `moderacion.py:258` (reactivar: no encontrado) | **S** (`moderar`) | **S, cualquiera de su ciudad** `campo.py:665-674` | N |
| Números y grupos de WhatsApp | S `moderacion.py:1041-1239` | N | N | N |

## 3. Problemas, ordenados por impacto

1. **El admin no tiene forma de cambiar la portada** (§1 Admin, paso 4). Es justo lo que pregunta el dueño, y la parte del sistema que más edita es la única que no puede hacerlo.
2. **La galería del modal de admin está fuera del modal** (`page.tsx:2678`, `Portal`). Lo más probable es que no se vea o no responda. Si se confirma, el admin tampoco puede ver ni agregar fotos desde «Editar negocio».
3. **Nadie puede elegir una foto existente como portada.** Hay que volver a subir la misma foto, y así queda duplicada: una vez como portada y otra en la galería, y la segunda cuenta para el tope del plan.
4. **El publicador ve un editor que no puede guardar.** El front no mira el permiso `comercios.editar`: el modal entero, «Analizar» y «Guardar» terminan en «Tu cuenta no tiene permiso para esto» (`backend/app/core/auth.py:117`) después de haber escrito todo.
5. **Permisos de más:** el publicador puede *rechazar*, que desactiva el comercio (`moderacion.py:258-268`), y el agente puede dar de baja cualquier comercio de su ciudad (`campo.py:665-674` + `:484-500`). Las dos son bajas lógicas, pero ningún perfil tiene un botón para deshacerlas.
6. **La portada vieja queda en el disco para siempre** y **el encuadre viejo se aplica a la foto nueva** (§1, «Qué pasa con la portada vieja»).
7. **Modal de admin confuso** (lo que se ve en la captura del dueño):
   - «Clasificar desde las fotos / Analizar» ocupa el primer lugar (`page.tsx:2161-2163`). Es una herramienta de clasificación por IA, pero parece la acción principal sobre las fotos.
   - Al aplicarla se cierra el modal y **se pierde lo que se había escrito y no se guardó** (`onAplicado={onDone}`, `page.tsx:2163`, `:2522`).
   - `URUKU-XXXX` aparece suelto debajo del nombre, sin decir qué es ni cómo se usa (`page.tsx:2224-2228`).
   - «Encuadre (sin ajustar)» con la ayuda «Izquierda = el cartel · derecha = la vereda» (`page.tsx:2185-2193`): es una barra horizontal que mueve el recorte en vertical, y «sin ajustar» suena a falla. Además no hay nada que diga «esta es la portada».
8. **Faltan campos en el admin** que el agente y el comerciante sí tienen: ubicación GPS, mercado/puesto, todo «Lo que suma», canal y catálogo (matriz §2). Y en el sentido contrario: el backend acepta `pedido_minimo`, `tiene_factura`, `envios_internacionales` y `tiene_stock`, pero el modal no los muestra.
9. **Tres pantallas distintas para la misma acción:** `FotoPrincipal` (comerciante), el bloque propio de `completar-comercio.tsx:519-537` (agente) y nada en el admin. Cada perfil aprende un gesto diferente.
10. Menor, para `security-reviewer`: el comerciante puede escribir `logo_url` como texto libre (`comercio.py:54`). No pasa por `validar_redes` y no tiene pantalla.

## 4. Propuesta (no implementada)

### P1 — «Usar como portada» en la galería, igual para los tres perfiles (núcleo)
- **Backend**: un servicio `app/services/portada.py` con dos operaciones, y un endpoint por perfil que lo llame:
  - `elegir_de_galeria(comercio, foto_id)`: **intercambio**. La foto elegida sale de `comercio_fotos` y pasa a `portada_url`/`portada_thumb_url`, y la portada anterior entra a la galería en su lugar. La cantidad de fotos no cambia, así que no choca con el tope. No se borra ningún archivo (S-01).
  - `subir_nueva(comercio, archivo)`: la lógica de hoy, más dos cosas: borrar del disco la portada anterior si nadie más la usa (reusar `borrar_archivos`, `fotos_galeria.py:258`) y poner `portada_pos = null`.
  - Rutas: `POST /admin/comercio/{id}/portada` (permiso `comercios.editar`), `POST /campo/mis-comercios/{id}/portada` y `POST /comercio/portada`. Las tres con body `{foto_id}` o multipart.
- **Frontend**: en `GaleriaUploader`, la portada va primero con la etiqueta «Portada», y cada foto suma el botón **«Usar como portada»** (función opcional `api.usarComoPortada`). El admin pasa a usar `FotoPrincipal` + `GaleriaUploader` en lugar de su `FotosComercio` propio.
- Archivos: `backend/app/services/portada.py` (nuevo), `backend/app/api/moderacion.py`, `campo.py`, `comercio.py`, `frontend/components/galeria-uploader.tsx`, `frontend/components/foto-principal.tsx`, `frontend/lib/api.ts`, `frontend/lib/campo.ts`, `frontend/app/admin/page.tsx`, más tests en `backend/tests/`.
- **Tamaño: mediano.**

### P2 — Arreglo inmediato del modal de admin (se puede hacer antes que P1)
- Sacar el `<Portal>` que envuelve `FotosComercio` (`page.tsx:2678`); dejarlo sólo en el visor. **Chico.**
- Reordenar el modal: arriba el bloque «Foto principal» (foto + «Cambiar» + «Recorte: más arriba / más abajo»), después los datos, y abajo de todo, plegado, «Sugerir rubros con IA». **Chico.**
- Código: «Código para publicar por WhatsApp: **URUKU-K7M2** [Copiar]». **Chico.**
- «Aplicar» de la IA: que actualice el formulario en lugar de cerrar el modal, o que pregunte si hay cambios sin guardar. **Chico.**
- Archivo: `frontend/app/admin/page.tsx`.

### P3 — Permisos coherentes por perfil
- En el front, ocultar «Editar», «Analizar» y «Guardar» cuando falta `puedo("comercios.editar")`. Para el publicador, la ficha se abre en modo lectura, con verificar y la galería. **Chico** (`page.tsx`, `frontend/lib/api.ts:1497`).
- «Rechazar» (desactivar) pasa a pedir `comercios.editar` (`moderacion.py:261`), y la baja del agente se limita a lo que cargó él (`campo.py:665-674`). **Chico** + tests.
- Agregar «Reactivar» para un comercio dado de baja (admin). **Chico/mediano.**

### P4 — Completar el editor de admin
- Agregar al body y al modal: lat/lng (mover el pin en el mapa), `lugar_id`/`puesto`, y «Lo que suma» reusando `TildesSuma`, canal y catálogo. **Mediano** (`moderacion.py:281-305`, `page.tsx`, reusar `components/tildes-suma.tsx` y `components/catalogo-pdf.tsx`).

### Wireframe — bloque de fotos (igual en los tres perfiles)
```
┌ Foto principal ──────────────────────────────────────────┐
│ [ FOTO 4:3 ]  Es la primera que ve el comprador          │
│  PORTADA      [Subir otra]  Recorte: [▲ más arriba] [▼]  │
└──────────────────────────────────────────────────────────┘
Fotos del local (12/50)                    [+ Agregar foto]
[img]      [img]      [img]      [img]
 Usar como  Usar como  Usar como  Usar como      × borrar
 portada    portada    portada    portada
Vacío: «Todavía no hay fotos. La primera que subas queda como portada.»
Error: «No se pudo cambiar la portada. Probá de nuevo.» (la anterior sigue igual)
```

### Criterios de aceptación de P1
- Dado un comercio con portada A y galería [B, C], cuando el admin toca «Usar como portada» en B, entonces la portada es B, la galería es [A, C], el total de fotos sigue siendo 2 y no se borró ningún archivo.
- Dado un encuadre del 30 %, cuando cambia la portada por cualquier camino, entonces `portada_pos` vuelve a `null`.
- Dada una portada subida que no está en la galería, cuando alguien sube otra nueva, entonces el archivo viejo y su miniatura se borran del disco.
- Un publicador sin `comercios.editar` no ve el botón y, si llama a la API, recibe 403. El agente sólo puede hacerlo sobre comercios de su ciudad.

### Supuestos
- **S-01** Elegir una foto de la galería como portada **intercambia** las dos fotos (la vieja no se pierde). Es el default porque no gasta lugar del tope y se puede deshacer con otro toque.
- **S-02** Subir una portada nueva **descarta** la anterior y borra sus archivos, con confirmación si ya había una (el agente ya la pide: `completar-comercio.tsx:341`).
- **S-03** El publicador **no** edita fichas: verifica y suma fotos. Así lo dice su descripción («Carga la cotización, el estado del paso y los videos», `permisos.py:64`).
- **S-04** El agente no puede dar de baja comercios que no cargó él.
- **S-05** El comerciante también puede elegir la portada de su galería (misma regla que S-01).

## 5. Preguntas que bloquean
1. **¿El publicador tiene que poder editar fichas de comercios?** Si la respuesta es sí, en lugar de P3 se le suma `comercios.editar` a su rol desde Equipo y queda resuelto sin tocar código. Si es no, se aplica S-03.
2. **¿Las portadas viejas que ya están huérfanas en el disco se limpian una vez** con un script (que requiere backup previo, porque es irreversible) **o se dejan?** No cambia el producto, pero decide si P1 incluye la limpieza retroactiva.
