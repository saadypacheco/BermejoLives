/** Comprime una imagen en el navegador antes de subirla (clave con internet
 * malo: subir 5-8MB de una foto de celular sin comprimir es lento e inestable).
 * Redimensiona a maxDim y recomprime a JPEG — mismo criterio que el backend
 * (services/imagenes.py procesar_imagen), solo que acá corre antes de la red. */
export async function comprimirImagen(file: File, maxDim = 1600, quality = 0.72): Promise<File> {
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, maxDim / Math.max(bitmap.width, bitmap.height));
    const w = Math.round(bitmap.width * scale);
    const h = Math.round(bitmap.height * scale);

    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.drawImage(bitmap, 0, 0, w, h);

    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
    if (!blob) return file;
    return new File([blob], file.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" });
  } catch {
    return file; // si algo falla (formato raro, navegador viejo), subimos el original
  }
}
