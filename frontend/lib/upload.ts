/** Sube un archivo con barra de progreso (XHR — fetch no da progreso de upload).
 * Clave con internet malo: el agente ve avanzar la subida en vez de esperar a ciegas. */
export function subirConProgreso<T = any>(
  url: string,
  field: string,
  file: File,
  token: string | null,
  extra: Record<string, string> = {},
  onProgress?: (pct: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const fd = new FormData();
    fd.append(field, file);
    for (const [k, v] of Object.entries(extra)) fd.append(k, v);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try { resolve(JSON.parse(xhr.responseText)); } catch { resolve({} as T); }
      } else {
        let msg = "No se pudo subir";
        try { msg = JSON.parse(xhr.responseText).detail || msg; } catch {}
        reject(new Error(msg));
      }
    };
    xhr.onerror = () => reject(new Error("Error de red al subir"));
    xhr.send(fd);
  });
}

/** Duración de un video en segundos (para validar <=60s antes de subir). */
export function duracionVideo(file: File): Promise<number> {
  return new Promise((resolve) => {
    const v = document.createElement("video");
    v.preload = "metadata";
    v.onloadedmetadata = () => { URL.revokeObjectURL(v.src); resolve(Math.round(v.duration) || 0); };
    v.onerror = () => resolve(0);
    v.src = URL.createObjectURL(file);
  });
}
