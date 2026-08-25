/** Comprime una imagen en el navegador antes de subirla (clave con internet
 * malo: subir 5-8MB de una foto de celular sin comprimir es lento e inestable).
 * Redimensiona a maxDim y recomprime a JPEG — mismo criterio que el backend
 * (services/imagenes.py procesar_imagen), solo que acá corre antes de la red.
 *
 * MEMORIA: por qué el `close()` y el canvas en 0 no son cosmética
 * ==============================================================
 *
 * El agente de campo carga cincuenta comercios seguidos en un Samsung de 4 GB y
 * el navegador terminaba diciendo "memoria insuficiente". Acá estaba el grueso.
 *
 * Un `ImageBitmap` NO es el archivo: son los píxeles ya decodificados, sin
 * comprimir. Una foto de 12 MP ocupa 4000 × 3000 × 4 bytes = **48 MB** de RAM.
 * El archivo JPEG que la contiene pesa 3 MB — la diferencia es toda la
 * descompresión. Y `close()` es la ÚNICA forma de soltarlos cuando uno quiere:
 * dejárselos al recolector de basura significa que se liberan cuando al motor
 * le parezca, que en un celular con la memoria justa es tarde.
 *
 * Importa además el ORDEN. El bitmap se cierra apenas se dibujó en el canvas,
 * ANTES de esperar el `toBlob` — que es lento porque codifica JPEG. Cerrarlo
 * después dejaría los 48 MB vivos justo durante la parte más cara, que es
 * exactamente el momento en que el celular se queda sin aire.
 *
 * El canvas es lo mismo en chico: 1600 × 1200 × 4 = 7,7 MB de buffer que el
 * elemento sigue reservando aunque nadie lo mire. Ponerle 0 × 0 lo suelta.
 */
export async function comprimirImagen(file: File, maxDim = 1600, quality = 0.72): Promise<File> {
  let bitmap: ImageBitmap | null = null;
  let canvas: HTMLCanvasElement | null = null;
  try {
    // imageOrientation "from-image": respeta el EXIF (foto vertical del celular
    // no sale rotada). Al recomprimir se pierde el EXIF, así que hay que
    // aplicarlo acá — si no, el backend ya no puede enderezarla.
    try {
      bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    } catch {
      bitmap = await createImageBitmap(file);
    }
    const scale = Math.min(1, maxDim / Math.max(bitmap.width, bitmap.height));
    const w = Math.round(bitmap.width * scale);
    const h = Math.round(bitmap.height * scale);

    canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.drawImage(bitmap, 0, 0, w, h);

    // Los píxeles grandes ya están copiados y escalados adentro del canvas: acá
    // se sueltan, antes del encode que es la parte lenta.
    bitmap.close();
    bitmap = null;

    const blob = await new Promise<Blob | null>((resolve) => canvas!.toBlob(resolve, "image/jpeg", quality));
    if (!blob) return file;
    return new File([blob], file.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" });
  } catch {
    return file; // si algo falla (formato raro, navegador viejo), subimos el original
  } finally {
    // Los dos caminos de salida por error también tienen que soltar: un
    // `return file` temprano dejaba 48 MB colgados por cada foto rara.
    bitmap?.close();
    if (canvas) { canvas.width = 0; canvas.height = 0; }
  }
}
