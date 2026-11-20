// ¿Una dirección que viene en una respuesta de Dax es del sitio? (components/asistente.tsx). Sin React, para poder
// probarlo con `npm test`.
//
// Seguridad: sólo es propia `https://uruku.bo` (sola) o `https://uruku.bo/…`, y lo que sigue pasa por
// `rutaInternaSegura`. Antes se le sacaba «https://uruku.bo» a cualquier cosa que EMPEZARA así, y
// `https://uruku.bo//evil.com` o `https://uruku.bo/\evil.com` quedaban como `//evil.com`: otro sitio, en la misma pestaña.
import { rutaInternaSegura } from "./ruta-interna";

export const ORIGEN_URUKU = "https://uruku.bo";

/** La ruta interna (`/buscar?q=…`) de una dirección propia, o `null` si no es propia o no es segura. */
export function rutaPropia(url: string | null | undefined): string | null {
  if (!url) return null;
  if (url === ORIGEN_URUKU) return "/";
  if (url.startsWith(`${ORIGEN_URUKU}/`)) return rutaInternaSegura(url.slice(ORIGEN_URUKU.length));
  if (url.startsWith("/")) return rutaInternaSegura(url);
  return null;
}

/** ¿Se puede usar como `src` de una imagen? http(s) o una ruta del sitio (nunca `//otro-sitio`, `data:` ni `javascript:`). */
export function esFotoSegura(url: string | null | undefined): url is string {
  return !!url && (/^https?:\/\/\S+$/i.test(url) || (url.startsWith("/") && !url.startsWith("//") && !url.includes("\\")));
}

/** Una dirección que se puede poner en un enlace externo: sólo http(s). */
export function esUrlWeb(url: string | null | undefined): url is string {
  return !!url && /^https?:\/\/\S+$/i.test(url);
}
