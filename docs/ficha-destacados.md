# Lo que suma en la ficha del comercio — spec

> **Estado: implementada el 10/10/2026.**

## El problema

La ficha (`/comercios/<slug>`) muestra nombre, rubro, horario, lo que vende y
el WhatsApp. Pero hay datos que hacen que un comprador elija ese local y que
**ya están en la base sin mostrarse**:

- `canal_wa_url` (el canal de WhatsApp del comercio, 0133) — lo carga el agente.
- `catalogo_url` (0133) — hoy es sólo un enlace que pega el agente.
- `envios_internacionales`, `tiene_factura`, `pedido_minimo` (0011).

Y falta uno que en Bermejo importa: **si el local tiene pasero** (quien le
cruza la compra al comprador). Se indica sólo como «tiene pasero», como el
cartel que ponen los locales.

El comerciante no puede cargar nada de esto desde **Mi comercio**: sólo el agente.

Las secciones **Ofertas** y **Novedades** de la ficha ya existen y aparecen
solas cuando el comercio publica (`ofertas.length > 0`, `novedades.length > 0`):
no se tocan, sólo se verifica que sigan así.

## Qué se construye

### 1. En la ficha, «Lo que suma» (todo opcional: lo que no está, no aparece)

En la tarjeta de contacto, debajo de las píldoras y antes del botón de WhatsApp,
una fila de **destacados** bien visibles:

| Dato | Cómo se ve | Al tocar |
|---|---|---|
| `canal_wa_url` | «Canal de WhatsApp» | Abre el canal (`target=_blank`) |
| `catalogo_url` | «Ver catálogo» | Abre el PDF o el enlace |
| `tiene_pasero` (nuevo) | «Tiene pasero» | — (sólo el cartel) |
| `envios_internacionales` | «Hace envíos» | — |
| `tiene_factura` | «Da factura» | — |
| `talles_especiales` (nuevo, 0142) | «Talles especiales» | — |

Y en «Información del negocio», si hay, una fila **Pedido mínimo**.

Íconos con `<Ic>` (nunca emoji). Los que abren algo se ven como botón; los que
son sólo un dato, como sello. Si no hay ninguno, la fila no existe.

### 2. El pasero

Migración **0141** (`supabase/migrations/` y `selfhost/postgres-init/`, iguales):
`comercios.tiene_pasero boolean not null default false` + comentario. Idempotente.
`comercios` tiene grant de tabla entera (0002): la ficha la lee con anon.

### 3. El catálogo como archivo, con tamaño controlado

- Se sube un **PDF de hasta 8 MB**. Se valida el tipo por contenido (que
  empiece con `%PDF-`), no sólo por la extensión. No PDF → 400; más grande →
  413, los dos con un mensaje claro en español («El catálogo puede pesar hasta 8 MB»).
- Se guarda en el disco del backend, como las fotos (`settings.fotos_dir`,
  carpeta `catalogos/<id del comercio>/<token>.pdf`: el slug cambia y se
  reutiliza), y su URL pública queda en
  `catalogo_url`. Subir uno nuevo **reemplaza y borra el anterior** (el disco no
  crece). Quitar el catálogo borra el archivo y deja `catalogo_url` en null.
- Sigue valiendo pegar un **enlace** (Drive, una tienda) en lugar de subir.
- Quién: el **comerciante** desde Mi comercio y el **agente** desde «Completar
  comercio». El panel del admin no cambia en esta tanda.

### 4. Dónde se cargan

- **Mi comercio › Editar información**: canal de WhatsApp, catálogo (subir PDF
  o enlace), tiene pasero, hace envíos, da factura, pedido mínimo.
- **Completar comercio** (agente): ya tiene canal y catálogo (enlace); suma
  subir el PDF, tiene pasero, hace envíos, da factura y pedido mínimo.

## Criterios de aceptación

1. Un comercio con canal, catálogo y pasero muestra los tres destacados; uno sin
   nada no muestra la fila.
2. Un PDF de 9 MB, o un archivo que no es PDF, se rechaza con un mensaje claro y
   el catálogo anterior queda como estaba.
3. Subir un catálogo nuevo borra el archivo del anterior.
4. El comerciante puede cargar todo desde Mi comercio, y el agente desde
   Completar comercio.
5. Ofertas y Novedades siguen apareciendo cuando hay publicaciones.
6. Sin emoji; tests del backend en verde; `tsc` sin errores.

## Agregado el 10/10

- **Talles especiales** (migración 0142): un sello más, cargado igual que el pasero.
- **Manual del comerciante**: la sección «Todo lo que podés mostrar en tu ficha» (`frontend/content/manuales/comercio.md`, publicada en `/manual/comercio`).
