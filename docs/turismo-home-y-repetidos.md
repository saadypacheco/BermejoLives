# Turismo en la home, repetidos y negocios sin punto (spec corta, 13/11/2026)

Sigue a `docs/importar-turismo.md` y `docs/lugares-turismo.md`. Tres pedidos del dueño después de ver la carga de
Tarija en QA:

1. **Repetidos que se complementan.** Lo que ya está en URUKU lo cargó una persona en la calle (punto exacto y foto);
   la página de turismo trae más datos (teléfonos, web, dirección escrita, horario). No se elige uno: se **completa
   el existente**, uno por uno, mirando los dos.
2. **Guías y radio móviles no tienen dirección** (22 guías autorizados, 19 radio móviles). No van al mapa, pero
   tienen que estar en el sitio.
3. **Tarija es una ciudad turística**: la home de la ciudad tiene que tener algo distinto y llamativo para el que la
   visita (extranjeros, argentinos, gente de otras ciudades de Bolivia).

## 1. Completar el existente (backend + panel)

Un importado de turismo o tarjeta con `duplicado_de` ya no se promueve como comercio nuevo por defecto: la ficha
muestra **los dos lado a lado** y la persona elige.

### Contrato (permiso `datos`)

| Método y ruta | Entrada | Salida |
|---|---|---|
| `GET /admin/importados/{id}/comparar?comercio_id=` | `comercio_id` opcional (por defecto `duplicado_de`) | `{ comercio: ComercioComparado, campos: [Campo], rubro_sugerido: str \| null, rubros_actuales: [str] }` |
| `POST /admin/importados/{id}/completar` | `{ comercio_id: uuid, usar: { <campo>: "nuevo" }, sumar_rubro: bool }` | `{ ok, comercio, cambiados: [campo] }` |
| `POST /admin/importados/{id}/no-es-repetido` | — | el Importado con `duplicado_de = null` (queda para promover como nuevo) |
| `POST /admin/importados/{id}/promover` | el de siempre + `sin_ubicacion: bool` (ver §2) | el de siempre |

`ComercioComparado = { id, nombre, slug, direccion, telefono, whatsapp, sitio_web, email, horario, lat, lng,
tiene_foto, fuente_url, subcategoria, verificado }` (sólo panel).

`Campo = { campo, actual, nuevo, sugerido: "completar" | "conservar" | "igual" }` para los campos `nombre`,
`direccion`, `telefono`, `whatsapp`, `sitio_web`, `email`, `horario`, `fuente_url`, `subcategoria`, `punto`
(`actual`/`nuevo` = `{lat,lng}` o null).

### Reglas de `completar`

- **Vacío en el existente y con dato en el importado → se completa solo** (sin que venga en `usar`).
- **Los dos con dato y distintos → se conserva el del existente**, salvo que el campo venga en `usar` con `"nuevo"`.
- **Nunca** se toca: foto, `verificado`, `confiable`, `cargado_por`, `codigo`, slug. El nombre sólo si viene en `usar`.
- **Punto:** el del existente gana siempre (lo marcó alguien parado ahí); sólo se copia si el existente no tiene.
- **Teléfono distinto:** si el existente ya tiene `telefono` y el importado trae otro número, con `usar.telefono =
  "nuevo"` se reemplaza; si el existente no tiene `telefono`, se completa. El `whatsapp` sólo se completa si el del
  importado es celular (misma regla que promover) y el existente no tiene.
- **Rubro:** con `sumar_rubro`, el sugerido se **agrega** a los rubros del comercio (tope 6, el existente
  `set_comercio_rubros`); si el único rubro actual es `otros`, lo **reemplaza**. Un rubro no comercial
  (`para-visitar`) además marca el rubro como revisado (`marcar_rubro_revisado`).
- El importado queda `estado = 'promovido'`, `comercio_id` = el existente, `motivo = 'completó el existente'`,
  `revisado_por/at`. Sin migración: el `check` de `estado` ya admite `promovido`.
- `calles_mapa.invalidar` si cambió el punto. Log `importado.completado` con los campos cambiados.
- 404 si el importado o el comercio no existen o el comercio está inactivo; 409 si el importado no está `nuevo`.

## 2. Promover sin punto

- `PromoverBody.sin_ubicacion: bool = False`. Con `true`, y **sólo** para `fuente in ('tarjeta','turismo')`, se
  promueve sin `lat/lng`: el comercio existe (ficha, búsqueda, listas) pero no aparece en el mapa. Sin el flag sigue
  el 400 de siempre.
- **Subcategoría legible** al promover cualquier importado de turismo (no sólo los no comerciales): la categoría de
  la página (`importados.categoria`, p. ej. `guias`, `radio-moviles`, `agencias-de-viajes`) pasa a
  `comercios.subcategoria` con una etiqueta en castellano (`Guía de turismo`, `Radio móvil`, `Agencia de viajes`,
  `Operadora de turismo`, `Transporte a los alrededores`, `Bodega`, `Complejo turístico`, `Balneario`…). Una tabla
  fija en el backend; lo que no está en la tabla queda como venía. Es lo que permite a la home separar guías de
  agencias dentro del rubro `turismo` y radio móviles dentro de `taxis`.
- En el panel: si no hay punto y la fuente es tarjeta o turismo, además del aviso aparece **«Promover sin
  ubicación»** (secundario), que explica en una línea que no va a estar en el mapa.

## 3. «Visitá Tarija»: turismo en la home (frontend público)

**Cuándo aparece:** en la home (`app/page.tsx`) de una ciudad que tiene lugares para visitar
(`hayParaVisitar(paresCiudad, ciudad.slug)`, ya existe). Hoy: Tarija. Nada hardcodeado a Tarija: cualquier ciudad
que cargue lugares la tiene.

**Dónde:** inmediatamente debajo del hero, antes de farmacias de turno. Es la sección más vistosa de la home de esa
ciudad: banda ancha a todo el ancho, con fondo propio (no la tarjeta gris de las demás secciones), título grande.

**Qué tiene** (textos propios de URUKU, nunca copiados de la página de turismo):

- Título: «Visitá {ciudad}» y una bajada corta para el que llega por primera vez.
- **Lugares para visitar**: carrusel con los lugares (`rubro = para-visitar`) de la ciudad: nombre, tipo
  (`subcategoria`: Plaza, Mirador, Museo, Excursión…) con su ícono, y enlace a la ficha. Sin fotos de la página de
  turismo (no se copian); si el lugar tiene foto propia de URUKU, se usa. «Ver todos» → la lista de para visitar.
- **Accesos grandes** (tarjetas con ícono): Guías de turismo autorizados · Agencias y operadoras · Dónde dormir
  (`hospedaje`) · Dónde comer (`restaurantes`) · Bodegas y vinos · Cómo moverse (radio móviles y transporte).
- **Sin números** (regla de siempre): ni «22 guías» ni «49 hoteles».

**Página nueva `/{ciudad}/turismo`** («{Ciudad} para el que la visita»): ISR como `/{ciudad}` (`revalidate`, sin
`generateStaticParams`, `force-static`), 404 si la ciudad no existe o no tiene lugares para visitar. Secciones con
ancla, cada una una lista simple (no mapa), porque acá están los que **no tienen punto**:

- `#guias` Guías de turismo autorizados (`rubro turismo`, `subcategoria = 'Guía de turismo'`): nombre, botón de
  WhatsApp si tiene, llamar si tiene teléfono, enlace a la ficha.
- `#agencias` Agencias y operadoras (`rubro turismo`, el resto).
- `#moverse` Cómo moverse: radio móviles y transporte a los alrededores (`rubro taxis`, con esas subcategorías),
  con botón de llamar.
- `#visitar`, `#dormir`, `#comer`, `#vinos`: enlaces a las listas por rubro que ya existen
  (`/{ciudad}/{rubro}` o `/buscar?rubro=…`), no se repiten acá.
- JSON-LD `CollectionPage` + `BreadcrumbList`; `TouristDestination` para la ciudad. Al sitemap si la ciudad tiene
  lugares.

Lecturas por PostgREST con anon, con `COLUMNAS_COMERCIO` (nunca `select("*")`), filtrando `activo`. Íconos de
`components/ic.tsx` (sin emojis; clave nueva → `npm run iconos`). Una ficha de comercio **sin punto** tiene que
verse bien (sin mapa roto, sin «cómo llegar»).

## Fuera de alcance

- Versión en inglés de la sección (se puede sumar después: es el siguiente paso natural para extranjeros).
- Fotos de los lugares desde Wikimedia Commons (pendiente aparte).
- Mercados municipales (se cargan a mano en Lugares).

## Criterios de terminado

1. Un repetido de turismo muestra los dos comercios lado a lado; «Completar» llena sólo lo vacío salvo lo que la
   persona marcó, no toca la foto ni el punto existente, y el importado queda promovido apuntando al existente.
2. «No es el mismo» saca el aviso y deja promoverlo como nuevo.
3. Un guía sin dirección se promueve «sin ubicación»: tiene ficha, sale en `/tarija/turismo#guias` y no en el mapa.
4. Al promover, guías y radio móviles quedan con su subcategoría legible.
5. La home con Tarija elegida muestra «Visitá Tarija» debajo del hero, con el carrusel de lugares y los accesos; con
   Bermejo (sin lugares) no aparece.
6. Ningún número de comercios en la sección ni en la página nueva. Sin emojis.
7. Tests: backend (completar, no-es-repetido, sin_ubicacion, subcategoría) y frontend (`npm test`: cuándo aparece
   la sección, armado de listas, reglas puras del comparador).
