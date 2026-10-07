# Manuales de uso desde el admin — spec

> **Estado: implementada el 7/10/2026.**

## El problema

- El único manual que existe es el **instructivo del agente**, y sale de un
  script (`scripts/instructivo.mjs`) que se corre en la máquina de desarrollo con
  un navegador prestado de otro repo. El dueño no sabía que existía ni cómo
  generarlo.
- Está **desactualizado**: es anterior a «Ya cargados acá cerca», «Completar
  comercio», el filtro «Sin horario» y la clave de 6 números del comerciante.
- **No hay manual del admin** (recién rediseñado) **ni del comerciante** (Mi
  comercio: entrar con celular + clave, publicar, el chatbot).

## Qué se construye

### 1. El contenido, en Markdown

Tres archivos en `frontend/content/manuales/`, escritos desde el código de hoy:

| Archivo | Para quién | Personalizado |
|---|---|---|
| `agente.md` | El agente de campo | Sí: `{{NOMBRE}}`, `{{CIUDAD}}`, `{{MAIL}}` |
| `admin.md` | Quien usa el panel | No |
| `comercio.md` | El comerciante | No |

Markdown **acotado** (lo único que el sitio sabe dibujar):
`#`, `##`, `###`, párrafos, listas `-` y `1.`, `**negrita**`, `*cursiva*`,
`` `código` ``, tablas con `|`, `> nota` (recuadro destacado), y una línea
`---` sola = **salto de página** al imprimir. Sin HTML, sin imágenes, sin emoji
(los dibuja cada teléfono distinto). Nada de géneros: «parado/parada» se evita
con otra redacción.

### 2. Las páginas

- `/manual/agente`, `/manual/admin`, `/manual/comercio`: el manual con la
  identidad de URUKU, legible en el celular y **prolijo al imprimir en A4**
  (`@media print`: sin barra ni botones, saltos de página en `---`, la portada
  con el nombre). Arriba, un botón **«Guardar como PDF»** (`window.print()`) y
  la explicación de una línea («elegí "Guardar como PDF" como impresora»).
- `/manual/agente?nombre=&ciudad=&mail=` completa las marcas; sin parámetros
  queda una versión genérica («tu ciudad», «tu correo»).
- `noindex`. El contenido no es secreto (el del comerciante incluso se enlaza
  desde Mi comercio), pero no es para buscadores.
- El Markdown se lee en el servidor (componente de servidor, `fs`) y se dibuja
  con un renderizador propio del subconjunto de arriba. **Sin dependencias
  nuevas.**

### 3. La sección «Manuales» del admin

Ítem nuevo en el menú (grupo Equipo, ícono de documento, sin permiso especial):

- **Manual del agente**: lista de los agentes del equipo (de `/admin/equipo`, los
  que tienen rol de agente) con su ciudad y correo. Al lado de cada uno,
  «Abrir manual» → `/manual/agente?...` con sus datos, en otra pestaña, listo
  para «Guardar como PDF» y mandarlo por WhatsApp. También la versión genérica.
- **Manual del admin** y **Manual del comerciante**: «Abrir» y «Copiar enlace»
  (el del comerciante se le puede mandar por WhatsApp).

### 4. Enlaces desde donde se usa

- **Mi comercio**: «¿Cómo se usa?» → `/manual/comercio`.
- **App del agente** (`/publicar`): «Manual» → `/manual/agente` con sus datos del
  token si los hay.

### 5. El script viejo

`scripts/instructivo.mjs` + `docs/instructivo-agente-fuente/` quedan hasta que el
dueño confirme que el manual nuevo lo reemplaza; después se borran (dos fuentes
del mismo instructivo es cómo se llegó a cuatro versiones distintas).

## Criterios de aceptación

1. Los tres manuales describen la app de HOY (cada pantalla y botón que nombran
   existe con ese nombre).
2. Desde admin › Manuales, un agente de la lista → su manual con nombre, ciudad y
   correo, en dos toques.
3. «Guardar como PDF» da un A4 prolijo: sin barra ni botones, sin páginas en
   blanco, cortes donde marca `---`.
4. Se lee bien en un celular de 360 px.
5. Sin emoji, sin dependencias nuevas; `tsc` sin errores.
