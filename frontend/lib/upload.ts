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


/**
 * Manda un FormData ya armado, por XHR.
 *
 * POR QUÉ NO `fetch`
 * ==================
 *
 * En Safari de iOS, con un service worker registrado, `fetch` con un `FormData`
 * **manda el pedido sin cuerpo**: el navegador arma el multipart con su
 * delimitador y el servidor recibe `Content-Length: 0`. Es una falla conocida de
 * WebKit y no hay forma de esquivarla desde el lado del pedido.
 *
 * Costó encontrarla porque no se parece a un error: el celular tiene los datos
 * —los muestra en pantalla— y el servidor contesta que falta la ubicación,
 * porque con el formulario vacío el primer control que se cruza es ése. Dieciocho
 * altas de campo quedaron trabadas señalando el dato equivocado.
 *
 * XHR no está afectado. Ya se usaba para subir fotos con progreso —por eso la
 * galería funcionaba en el mismo teléfono, el mismo día— y ahora lo usa también
 * el alta.
 */
export function postFormData<T = any>(
  url: string, fd: FormData, token: string | null,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    // NO se setea Content-Type: lo pone el navegador con su delimitador. Ponerlo
    // a mano rompe el multipart, que es la otra forma de llegar a un cuerpo
    // ilegible del lado del servidor.
    xhr.onload = () => {
      let cuerpo: any = {};
      try { cuerpo = JSON.parse(xhr.responseText); } catch { /* respuesta vacía */ }
      if (xhr.status >= 200 && xhr.status < 300) return resolve(cuerpo as T);

      // El `detail` de FastAPI es un texto en los 400 y una LISTA de objetos en
      // los 422. Sin distinguirlos, un 422 llegaba a la pantalla como
      // "[object Object]" y no se podía saber qué campo estaba mal.
      const detalle = Array.isArray(cuerpo.detail)
        ? cuerpo.detail.map((e: { loc?: unknown[]; msg?: string }) =>
            `${(e.loc ?? []).slice(1).join(".")}: ${e.msg ?? "inválido"}`).join(", ")
        : (typeof cuerpo.detail === "string" ? cuerpo.detail : "");
      const err = new Error(detalle || `No se pudo guardar (HTTP ${xhr.status})`);
      (err as Error & { status?: number }).status = xhr.status;
      reject(err);
    };
    xhr.onerror = () => reject(new Error("Sin conexión"));
    xhr.ontimeout = () => reject(new Error("La subida tardó demasiado"));
    xhr.send(fd);
  });
}
