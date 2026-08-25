# "Memoria insuficiente" en el recolector — auditoría del manejo de imágenes

> Síntoma reportado: la app recolectora muere por memoria en un Samsung de 4 GB
> durante la carga de fotos, cargando comercios seguidos. **2026-08-25.**

La app recolectora es `/publicar` (`/campo` redirige ahí). Se auditaron los
cuatro lugares que tocan imágenes: `lib/imagen.ts`, `app/publicar`,
`app/autoregistro`, `app/recuperar-negocio` y `components/galeria-uploader`.

## 1. Lo que se encontró

Cuatro fugas. **Ninguna es un bug de lógica**: en una laptop con 16 GB el
recolector anda perfecto y por eso nunca se notó. Todas comparten la misma
causa — recursos del navegador que el recolector de basura **no** libera solo.

| # | Dónde | Qué queda colgado | Por comercio |
|---|---|---|---|
| 1 | `lib/imagen.ts` — el `ImageBitmap` nunca se cerraba | Los píxeles decodificados de la foto | **~48 MB** |
| 2 | `lib/imagen.ts` — el canvas nunca se liberaba | El buffer de dibujo de 1600×1200 | ~7,7 MB |
| 3 | `publicar` / `autoregistro` / `recuperar-negocio` — `URL.createObjectURL` sin revocar | El archivo original de la cámara | ~5-8 MB |
| 4 | `galeria-uploader` — `createObjectURL` **dentro del render** | Una foto por cada redibujado | sin techo |

### 1.1 La grande: el `ImageBitmap` de 48 MB

```ts
bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
```

Un `ImageBitmap` **no es el archivo**: son los píxeles ya descomprimidos. Una
foto de 12 MP ocupa `4000 × 3000 × 4 bytes` = **48 MB** de RAM, aunque el JPEG
que la contiene pese 3 MB. Toda esa diferencia es la descompresión.

Y `close()` es la única forma de soltarlos cuando uno quiere. Dejárselos al
recolector de basura significa que se liberan cuando al motor le parezca — que
en un celular con la memoria justa es tarde.

**El orden importa tanto como el `close()`.** Ahora el bitmap se cierra apenas
se dibujó en el canvas, **antes** de esperar el `toBlob`, que es la parte lenta
porque codifica JPEG. Cerrarlo después dejaría los 48 MB vivos justo durante el
momento más caro — que es exactamente cuando el celular se queda sin aire.

También faltaba en los caminos de error: los tres `return file` tempranos
(navegador viejo, formato raro, sin contexto 2D) salían sin cerrar nada. Ahora
va en un `finally`.

### 1.2 La que crece: los object URL que nunca se revocan

```ts
setPreview(URL.createObjectURL(file));   // …y nunca URL.revokeObjectURL
```

`createObjectURL` crea un vínculo entre la página y el archivo, y ese vínculo
**ancla el archivo en memoria hasta que alguien lo suelta o se cierra la
pestaña**. No lo limpia el recolector: aunque no quede ninguna variable
apuntando al `File`, el navegador tiene que poder resolver esa URL.

Al guardar, el formulario hacía `setPreview("")` — que borra el string y **deja
la URL viva**. A los cincuenta comercios son 250-400 MB que ninguna limpieza va
a recuperar. **Ésta es la que explica que el problema aparezca "cargando
comercios seguidos" y no en el primero.**

Hay un agravante que no salta a la vista: previsualizar el archivo original
obliga al navegador a **decodificar la foto de 12 MP entera** para dibujar una
miniatura de 200 px. Son otros ~48 MB, por foto, en la caché de imágenes.

### 1.3 La peor por multiplicación: `createObjectURL` en el render

```tsx
{pendFotos.map((p) => (
  <img src={URL.createObjectURL(p.blob)} alt="" />     // ← en el JSX
))}
```

Esto crea una URL **nueva en cada redibujado** y no revoca ninguna. Y el
componente redibuja en cada tick del progreso de subida, así que una sola foto
pendiente puede generar decenas de URLs, cada una anclando el blob.

### 1.4 Lo que estaba bien

- **La cola offline** (`lib/offline-altas.ts`, `offline-media.ts`) guarda los
  `Blob` en **IndexedDB**, que es disco y no RAM. Es la decisión correcta y no
  hay que tocarla.
- **`mi-comercio`** ya usaba el patrón bueno (`useMemo` + revocar en el
  cleanup). El código sabía cómo se hacía; simplemente no estaba aplicado en los
  otros cuatro lugares.
- La compresión a 1600 px / JPEG 0.72 ya existía y coincide con la del backend.
  El problema nunca fue que faltara comprimir: era **cómo se liberaba lo que la
  compresión usa**.

## 2. Lo que se cambió

- **`lib/imagen.ts`**: `bitmap.close()` inmediatamente después del `drawImage` y
  otra vez en `finally`; el canvas se libera poniéndolo en 0 × 0.
- **`lib/object-url.ts`** (nuevo): `useObjectUrl` y `useObjectUrls`, que atan la
  URL al ciclo de vida del componente — cambia el archivo, se revoca el
  anterior; se desmonta, se revoca el último.
- **`publicar`, `autoregistro`, `recuperar-negocio`**: el estado ahora guarda el
  **File**, no la URL. Y apenas termina la compresión **se previsualiza la
  comprimida y se suelta la original**, que corta el decode de 12 MP.
- **`galeria-uploader`**: las URLs salen del render a un `useObjectUrls`.

## 3. Cómo verificar en el celular real

**No alcanza con leer el código.** El síntoma no se reproduce en una laptop, así
que la medición tiene que correr en el Samsung. Se agregó
`lib/memoria.ts`, que imprime el heap después de cada alta:

1. Abrir el recolector con **`?debugmem=1`** (queda prendido para esa pestaña).
2. Cargar **50 comercios con foto**, seguidos, sin recargar la página.
3. Leer la consola por `chrome://inspect` desde una compu con el celular por
   USB, o pegar `resumenMemoria()` en la consola.

Cada línea dice tres cosas:

```
[memoria] #12 comercio guardado — heap 148 MB · desde el arranque +18 MB · +1.6 MB por comercio
```

**El número que decide es el último.** Cerca de 0 significa que no queda nada
colgado. Si dice 5 o 10 MB por comercio, en cincuenta altas son 250-500 MB y el
celular muere — y ahí el tamaño del escalón dice exactamente cuánto se está
perdiendo por vez.

El **pico** se mira aparte: es el instante de comprimir, y es el que dispara
"memoria insuficiente" aunque el promedio esté sano.

### Lo que todavía no está medido

Los arreglos están hechos y razonados sobre el código, pero **el consumo real en
el Samsung no se midió todavía** — no hay forma de hacerlo desde acá. Hasta esa
corrida, lo honesto es decir que las cuatro fugas están cerradas, no que el
problema está resuelto.

Si después de medir sigue creciendo, el próximo sospechoso es el **pico** y no
la fuga: la foto de 12 MP hay que decodificarla entera al menos una vez para
poder escalarla, y en un equipo de 4 GB con Chrome, el sistema operativo y la
cámara compitiendo, ese pico puede alcanzar solo. La salida sería no decodificar
a resolución completa —leer las dimensiones del encabezado JPEG y pedirle a
`createImageBitmap` que decodifique ya escalado (`resizeWidth`/`resizeHeight`)—,
que es bastante más trabajo y no vale hacerlo antes de saber si hace falta.
