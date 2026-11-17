// La ubicación de la ficha de un comercio (app/comercios/[slug]): qué enlace de «Cómo llegar» corresponde y cuándo
// no hay ninguno. Puro, para poder probarlo con `npm test`.
//
// Hay comercios SIN punto en el mapa (`lat`/`lng` null): los guías y radio móviles de turismo y las tarjetas
// promovidas «sin ubicación» (docs/turismo-home-y-repetidos.md §2). Antes la ficha armaba igual un enlace de
// Google Maps que buscaba el nombre de la CIUDAD: el botón «Cómo llegar» abría el mapa en el centro de Tarija,
// como si el local estuviera ahí. Ahora, sin punto ni dirección escrita ni enlace cargado, no hay botón.

export type UbicacionFicha = {
  como_llegar?: string | null;
  lat?: number | null;
  lng?: number | null;
  direccion?: string | null;
  calle?: string | null;
};

/** ¿Tiene un punto de verdad en el mapa? (`0` es una coordenada válida; `null` y `NaN` no.) */
export function tienePunto(c: Pick<UbicacionFicha, "lat" | "lng">): boolean {
  return typeof c.lat === "number" && Number.isFinite(c.lat) && typeof c.lng === "number" && Number.isFinite(c.lng);
}

function urlWeb(u: string | null | undefined): string | null {
  const t = (u ?? "").trim();
  if (!t) return null;
  try {
    const x = new URL(t);
    return x.protocol === "http:" || x.protocol === "https:" ? x.href : null;
  } catch {
    return null;
  }
}

/**
 * El destino de «Cómo llegar», o `null` si no hay a dónde mandar:
 *  1. el enlace que cargó el comercio (`como_llegar`), si es web;
 *  2. el punto (`lat`/`lng`);
 *  3. la dirección escrita (o la calle), con la ciudad para que el buscador no adivine.
 * Sin nada de eso, `null`: la ficha no muestra el botón (ni un mapa vacío).
 */
export function destinoComoLlegar(c: UbicacionFicha, ciudadNombre: string): string | null {
  const propio = urlWeb(c.como_llegar);
  if (propio) return propio;
  if (tienePunto(c)) return `https://www.google.com/maps/search/?api=1&query=${c.lat},${c.lng}`;
  const donde = (c.direccion ?? "").trim() || (c.calle ?? "").trim();
  if (donde) return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(ciudadNombre ? `${donde}, ${ciudadNombre}` : donde)}`;
  return null;
}

/** Rubros que atienden «en toda la ciudad» y pueden no tener local ni punto: se los llama, no se va a buscarlos. */
const RUBROS_SIN_LOCAL = ["taxis", "turismo"];

/** ¿Es un comercio sin local ni punto cuyo rubro lo explica? (taxi/radio móvil, guía de turismo). */
export function atiendeSinLocal(c: UbicacionFicha, rubroSlug: string | null | undefined): boolean {
  return RUBROS_SIN_LOCAL.includes(rubroSlug ?? "") && !tienePunto(c) && !(c.direccion ?? "").trim();
}

/** La línea de la tarjeta «Dónde atiende» de la ficha de un comercio sin local. */
export function textoDondeAtiende(rubroSlug: string | null | undefined, tieneTelefono: boolean): string {
  const medio = `por WhatsApp${tieneTelefono ? " o por teléfono" : ""}`;
  return rubroSlug === "turismo"
    ? `No tiene un local para visitar: se lo contacta ${medio} y se coordina dónde encontrarse.`
    : `En toda la ciudad: no tiene parada fija, se pide ${medio}.`;
}
