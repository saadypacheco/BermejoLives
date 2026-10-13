/**
 * «Le falta»: lo que un comercio todavía no tiene cargado.
 *
 * Vive acá (y no dentro de «Completar comercio») porque la misma cuenta la
 * necesitan tres pantallas: la propia pantalla de completar, la lista de
 * «Qué hay acá» (para decir «Completo» o «Le faltan 3: …» sin abrir cada local)
 * y la ficha del local. Tres copias del criterio terminan diciendo tres cosas.
 */
import type { ComercioAgente } from "@/lib/campo";

/** Fotos de galería para no figurar con «Le falta: fotos». */
export const FOTOS_MINIMAS = 3;

export type ClaveFalta = "horario" | "contacto" | "vidriera" | "fotos" | "vende" | "rubro" | "puesto";
export type Falta = { clave: ClaveFalta; label: string; ir: string; foco?: string };

/** Lo que el comercio NO tiene, en el orden de la charla con el dueño. Se calcula
 *  de lo GUARDADO (el comercio que llega por props), no de lo que está tipeado:
 *  un ítem sale de la lista cuando el dato ya está a salvo.
 *
 *  `nFotos` es la cantidad de fotos de la galería; `null` = todavía no se sabe y
 *  entonces NO se afirma que faltan. */
export function calcularFaltas(c: ComercioAgente, nFotos: number | null): Falta[] {
  const r: Falta[] = [];
  if (!(c.horario ?? "").trim()) r.push({ clave: "horario", label: "Horario", ir: "cc-horario" });
  if (!(c.whatsapp ?? "").trim() && !(c.telefono ?? "").trim()) r.push({ clave: "contacto", label: "Contacto", ir: "cc-contacto", foco: "cc-wa" });
  if (!c.portada_url) r.push({ clave: "vidriera", label: "Foto de la vidriera", ir: "cc-fotos" });
  // null = la galería todavía no respondió: no se afirma que falta. Pide 3, el
  // mismo mínimo que el backend usa para elegir los ejemplos «completos»
  // (`es_completo` en services/que_hay_aca.py): con 1 foto no se ve la mercadería.
  if (nFotos !== null && nFotos < FOTOS_MINIMAS) {
    r.push({ clave: "fotos", label: nFotos === 0 ? "Fotos del local" : `Fotos del local (${nFotos} de ${FOTOS_MINIMAS})`, ir: "cc-galeria" });
  }
  if (!(c.prod_obs_human ?? "").trim()) r.push({ clave: "vende", label: "Qué vende", ir: "cc-vende", foco: "cc-vende-txt" });
  if (!c.rubros) r.push({ clave: "rubro", label: "Rubro", ir: "cc-rubros" });
  if (c.lugar_id && !(c.puesto ?? "").trim()) r.push({ clave: "puesto", label: "Puesto", ir: "cc-mercado", foco: "cc-puesto" });
  return r;
}

/** Las etiquetas para la lista («Le faltan 3: horario, contacto, fotos»), cortas y en minúscula. */
export function etiquetasFaltas(faltas: Falta[]): string[] {
  return faltas.map((f) => f.label.toLowerCase());
}
