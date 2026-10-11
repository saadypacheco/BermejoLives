// Ayudas de «Lo que suma» en la ficha del comercio (spec docs/ficha-destacados.md):
// validar el PDF del catálogo antes de subirlo y decidir qué enlaces se muestran.

/** El PDF del catálogo pesa hasta 8 MB (lo mismo que controla el servidor). */
export const CATALOGO_MAX_BYTES = 8 * 1024 * 1024;
export const CATALOGO_MAX_TEXTO = "8 MB";

/** Devuelve el motivo por el que el archivo no sirve, o null si está bien.
 *  Se mira ANTES de mandar: con señal mala, subir 9 MB para enterarse de que no
 *  entra es perder el rato del agente en la puerta del local. El servidor
 *  vuelve a controlar (por contenido); esto sólo ahorra el viaje. */
export function validarCatalogoPdf(file: File): string | null {
  const esPdf = file.type === "application/pdf" || /\.pdf$/i.test(file.name);
  if (!esPdf) return "El catálogo tiene que ser un PDF. Si lo tenés en otro formato, pegá el enlace.";
  if (file.size > CATALOGO_MAX_BYTES) {
    // Redondeado para ARRIBA: con toFixed, 8 MB + 1 byte decía «pesa 8,0 MB»,
    // que contradice el «hasta 8 MB» de la misma frase.
    const mb = Math.ceil((file.size / (1024 * 1024)) * 10) / 10;
    return `El catálogo puede pesar hasta ${CATALOGO_MAX_TEXTO} y este pesa ${mb.toFixed(1).replace(".", ",")} MB.`;
  }
  if (file.size === 0) return "El archivo está vacío.";
  return null;
}

/** El texto de un error de subida/borrado de catálogo. Un 413 puede venir sin
 *  `detail` (lo corta el proxy antes de llegar a la API): se le pone el motivo. */
export function textoErrorCatalogo(e: unknown): string {
  const status = (e as { status?: number } | null)?.status;
  const msg = e instanceof Error ? e.message : "";
  if (status === 413 && (!msg || /HTTP 413/.test(msg))) {
    return `El catálogo puede pesar hasta ${CATALOGO_MAX_TEXTO}.`;
  }
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    return "Sin conexión: no se pudo completar. Probá de nuevo cuando haya señal.";
  }
  return msg || "No se pudo completar";
}

/** El enlace tal cual, sólo si es http(s). Un `javascript:` o un texto suelto en
 *  un `href` es un enlace roto con cara de funcionar —o algo peor—, así que lo
 *  que no es web no se muestra. */
export function urlHttp(u: string | null | undefined): string | null {
  const t = (u ?? "").trim();
  if (!/^https?:\/\/\S+$/i.test(t)) return null;
  // Que además sea una dirección de verdad: `https:///x` o `http://[::1` pasaban
  // la forma y el servidor después los rechazaba. Y nada de «usuario@» antes
  // del dominio (`https://uruku.bo@otro.com` lleva a otro.com).
  try {
    const url = new URL(t);
    return url.hostname && !url.username && !url.password ? t : null;
  } catch { return null; }
}

/** El canal de WhatsApp listo para un `href`: sólo si lleva a WhatsApp
 *  (whatsapp.com o wa.me). Acepta el que se guardó sin «https://» antes de que
 *  los formularios lo completaran solos, que si no quedaba oculto. */
export function enlaceCanal(u: string | null | undefined): string | null {
  const t = (u ?? "").trim();
  const href = urlHttp(t) ?? (/^[a-z][a-z0-9+.-]*:/i.test(t) ? null : normalizarEnlace(t));
  if (!href) return null;
  try {
    const h = new URL(href).hostname.toLowerCase();
    return h === "wa.me" || h === "whatsapp.com" || h.endsWith(".whatsapp.com") ? href : null;
  } catch { return null; }
}

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** ¿Esta URL es un PDF subido a URUKU (y no un enlace que pegó una persona)?
 *  El servidor lo guarda en `/fotos/catalogos/<id del comercio>/<token>.pdf`, en
 *  el dominio de la API. Mirar sólo la ruta no alcanzaba: un enlace ajeno como
 *  `mitienda.com/catalogos/2026.pdf` pasaba por subido, se escondía el campo
 *  del enlace y Mi comercio dejaba de mandarlo. Sirve para mostrar «Quitar»
 *  sólo donde hay un archivo que borrar. */
export function esCatalogoSubido(u: string | null | undefined): boolean {
  const t = (u ?? "").trim();
  if (!urlHttp(t)) return false;
  try {
    const url = new URL(t);
    return url.hostname === new URL(API).hostname && /^\/fotos\/catalogos\/[^/]+\/[^/]+\.pdf$/i.test(url.pathname);
  } catch { return false; }
}

/** El enlace de una red o del sitio web, listo para un `href`, o null si no se
 *  puede mostrar. Los agentes los cargan como los dicta el dueño («@mitienda»,
 *  «mitienda.com»), así que se arman acá; y lo que trae otro esquema
 *  (`javascript:`, `data:`) NUNCA llega a un href: con eso se robaba la sesión
 *  guardada en el navegador de quien tocara «Sitio web». */
export function enlaceRed(red: "instagram" | "tiktok" | "facebook" | "web", valor: string | null | undefined): string | null {
  const t = (valor ?? "").trim();
  if (!t) return null;
  if (/^[a-z][a-z0-9+.-]*:/i.test(t)) return urlHttp(t);     // tiene esquema: sólo http(s)
  const usuario = t.replace(/^@/, "");
  if (red !== "web" && /^[\w.]{1,60}$/.test(usuario)) {
    if (red === "instagram") return `https://instagram.com/${usuario}`;
    if (red === "tiktok") return `https://www.tiktok.com/@${usuario}`;
    return `https://facebook.com/${usuario}`;
  }
  return normalizarEnlace(t);
}

/** Deja un enlace en forma de enlace: el que ya empieza con http(s) queda igual;
 *  el que se pegó sin esquema («whatsapp.com/channel/abc») se completa con
 *  https://. Devuelve null si no se parece a una dirección web: en la ficha el
 *  botón sólo sale con http(s), y un enlace que no sale sin explicación es peor
 *  que avisar al guardar. */
export function normalizarEnlace(u: string): string | null {
  const t = u.trim();
  if (urlHttp(t)) return t;
  if (/^[^\s/:]+\.[^\s/:]{2,}(?:[/?#]\S*)?$/.test(t)) return `https://${t}`;
  return null;
}
