// ---- Tope de fotos de la galería (409 del backend) ----

/** Lo que el backend contesta (HTTP 409, `detail`) cuando la galería ya está en
 *  el tope de fotos del plan. `mas_vieja` es la que se borraría si el comercio
 *  elige reemplazar. */
export type TopeFotos = {
  mensaje: string;
  codigo: "tope_fotos";
  limite: number;
  precio_extra: number;
  moneda: string;
  mas_vieja: { id: string; url: string } | null;
};

/** Cómo reintentar la subida que chocó con el tope: `reemplazar=<id>` borra esa
 *  foto después de guardar la nueva; `extra=pagar` (sólo el comerciante) cobra
 *  una foto extra y suma una. */
export type OpcionesFoto = { reemplazar?: string; extra?: "pagar" };

/** Lista de fotos de una galería + el tope actual de su plan (`null` si el
 *  backend todavía no lo manda: la pantalla usa un respaldo). */
export type ListaFotos<F> = { items: F[]; limite: number | null };

export function listaFotos<F>(d: { items?: F[]; limite?: unknown } | null | undefined): ListaFotos<F> {
  const l = d?.limite;
  return { items: d?.items ?? [], limite: typeof l === "number" && l > 0 ? l : null };
}

/** Lo que contesta «Usar como portada» (`PUT <base>/portada`): la portada nueva y
 *  la galería ya reacomodada (la portada anterior entró en lugar de la elegida). */
export type RespuestaPortada<F> = {
  portada_url: string | null;
  portada_thumb_url: string | null;
  fotos: F[];
  limite: number | null;
};

export function respuestaPortada<F>(
  d: { portada_url?: unknown; portada_thumb_url?: unknown; fotos?: F[]; limite?: unknown } | null | undefined,
): RespuestaPortada<F> {
  const txt = (x: unknown) => (typeof x === "string" && x ? x : null);
  const l = d?.limite;
  return {
    portada_url: txt(d?.portada_url),
    portada_thumb_url: txt(d?.portada_thumb_url),
    fotos: d?.fotos ?? [],
    limite: typeof l === "number" && l > 0 ? l : null,
  };
}

export function camposOpcionesFoto(o?: OpcionesFoto): Record<string, string> {
  const c: Record<string, string> = {};
  if (o?.reemplazar) c.reemplazar = o.reemplazar;
  if (o?.extra) c.extra = o.extra;
  return c;
}

/** Error de subida que conserva el HTTP status y el `detail` crudo cuando no es
 *  un texto (el 409 del tope trae un objeto). */
export type ErrorSubida = Error & { status?: number; datos?: unknown };

/** Arma el Error de una respuesta fallida. El `detail` de FastAPI es un texto,
 *  una lista (422) o, en el tope de fotos, un objeto con `mensaje`. */
export function errorDeRespuesta(status: number, cuerpo: unknown, porDefecto: string): ErrorSubida {
  const detail = (cuerpo as { detail?: unknown } | null)?.detail;
  let msg = porDefecto;
  let datos: unknown;
  if (typeof detail === "string" && detail) msg = detail;
  else if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    datos = detail;
    const m = (detail as { mensaje?: unknown }).mensaje;
    if (typeof m === "string" && m) msg = m;
  }
  const err: ErrorSubida = new Error(msg);
  err.status = status;
  err.datos = datos;
  return err;
}

/** Si el error es el 409 del tope de fotos, devuelve sus datos; si no, null. */
export function datosTope(ex: unknown): TopeFotos | null {
  const e = ex as ErrorSubida | null;
  if (!e || e.status !== 409 || !e.datos || typeof e.datos !== "object") return null;
  const d = e.datos as Partial<TopeFotos>;
  if (d.codigo !== "tope_fotos") return null;
  const vieja = d.mas_vieja && typeof d.mas_vieja.id === "string" && d.mas_vieja.id ? d.mas_vieja : null;
  return {
    mensaje: d.mensaje ?? "Llegaste al tope de fotos de tu plan",
    codigo: "tope_fotos",
    limite: typeof d.limite === "number" ? d.limite : 0,
    precio_extra: typeof d.precio_extra === "number" ? d.precio_extra : 0,
    moneda: d.moneda ?? "BOB",
    mas_vieja: vieja,
  };
}

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
        let cuerpo: unknown = null;
        try { cuerpo = JSON.parse(xhr.responseText); } catch {}
        reject(errorDeRespuesta(xhr.status, cuerpo, "No se pudo subir"));
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
  /** Opcional: avance de la subida, de 0 a 100 (para los archivos grandes, como
   *  el PDF del catálogo). Sin esto no cambia nada para quien ya lo usa. */
  onProgress?: (pct: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    if (onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
      };
    }
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

    // Se manda el cuerpo YA ARMADO, no el FormData. Ver `armarMultipart`.
    const { blob, contentType } = armarMultipart(fd);
    xhr.setRequestHeader("Content-Type", contentType);
    xhr.send(blob);
  });
}


/**
 * Arma el cuerpo multipart a mano y lo devuelve como Blob.
 *
 * POR QUÉ NO SE LE PASA EL `FormData` AL NAVEGADOR
 * ================================================
 *
 * En el iPhone, tanto `fetch` como XHR mandaban el pedido con `Content-Length: 0`:
 * el navegador ponía la cabecera con su delimitador y no escribía un solo byte
 * del cuerpo. Del lado del servidor llegaban dieciocho altas de campo sin ningún
 * campo, y el error que devolvía —"Falta la ubicación"— señalaba el dato
 * equivocado, porque con el formulario vacío ése es el primer control que se
 * cruza.
 *
 * Serializando nosotros, el cuerpo es un Blob común: no depende de que el
 * navegador convierta el FormData en bytes. Un Blob se manda o no se manda; no
 * se manda vacío.
 *
 * El formato es el del estándar y no tiene margen: cada parte abre con
 * `--delimitador`, sigue con su cabecera, una línea en blanco, el contenido, y
 * cierra con un salto. Al final va `--delimitador--`. Un salto de menos y el
 * servidor lee basura.
 */
export function armarMultipart(fd: FormData): { blob: Blob; contentType: string } {
  const CRLF = "\r\n";
  // El delimitador tiene que ser una secuencia que NO aparezca en el contenido.
  const limite = `----uruku${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
  const partes: BlobPart[] = [];

  fd.forEach((valor, clave) => {
    partes.push(`--${limite}${CRLF}`);
    if (valor instanceof Blob) {
      // Las comillas cierran el nombre del archivo en la cabecera: una comilla
      // adentro del nombre parte el encabezado en dos y corrompe lo que sigue.
      const nombre = ((valor as File).name || "archivo").replace(/["\r\n]/g, "'");
      partes.push(`Content-Disposition: form-data; name="${clave}"; filename="${nombre}"${CRLF}`);
      partes.push(`Content-Type: ${valor.type || "application/octet-stream"}${CRLF}${CRLF}`);
      partes.push(valor);
      partes.push(CRLF);
    } else {
      partes.push(`Content-Disposition: form-data; name="${clave}"${CRLF}${CRLF}`);
      partes.push(`${valor}${CRLF}`);
    }
  });
  partes.push(`--${limite}--${CRLF}`);

  return { blob: new Blob(partes), contentType: `multipart/form-data; boundary=${limite}` };
}
