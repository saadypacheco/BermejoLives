/**
 * El párrafo que abre /{ciudad}/{rubro}: contesta «¿dónde queda y qué venden los
 * locales de X en Y?» con lo que hay cargado, y nada más.
 *
 * Spec: docs/visibilidad-buscadores-ia.md §3.3 y §3.8 (answer-first). Cada frase
 * aparece sólo si hay dato. NUNCA devuelve un número de comercios.
 *
 * PURO: sin red ni `@/` (lo cargan los tests con Node, `npm test`).
 */
import { productosDe } from "./productos";

function sinTildes(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

/** «Av. Bolivia 123» y «av bolivia» son la misma calle: sin número final, sin
 *  tildes ni mayúsculas, sin puntos. */
function claveCalle(calle: string): string {
  return sinTildes(calle).replace(/\s+(n[°º.]?\s*)?\d+[a-z]?$/i, "").replace(/[.,]/g, "").replace(/\s+/g, " ").trim();
}

/** La calle como se escribe, sin el número de puerta. */
function calleLimpia(calle: string): string {
  return calle.trim().replace(/\s+(n[°º.]?\s*)?\d+[a-zA-Z]?$/i, "").replace(/\s+/g, " ").trim();
}

/**
 * Las calles donde hay al menos `minimo` locales, de la más repetida a la menos
 * (a igual cantidad, la que apareció primero). Hasta `max`.
 */
export function callesFrecuentes(calles: readonly (string | null | undefined)[], minimo = 3, max = 3): string[] {
  const grupos = new Map<string, { texto: string; n: number }>();
  for (const c of calles) {
    const texto = calleLimpia(c ?? "");
    const clave = claveCalle(texto);
    if (clave.length < 3) continue;
    const g = grupos.get(clave);
    if (g) g.n += 1; else grupos.set(clave, { texto, n: 1 });
  }
  return [...grupos.values()].filter((g) => g.n >= minimo).sort((a, b) => b.n - a.n).slice(0, max).map((g) => g.texto);
}

export type FilaProductos = { prod_obs_human?: string | null; prod_det_ia?: string | null };

/**
 * Los productos que más se repiten entre los locales (`prod_obs_human` y
 * `prod_det_ia`), hasta `max`. Se cuenta cuántos locales lo nombran (un local que
 * lo repite no suma dos veces); a igual cantidad, el que apareció primero.
 */
export function productosFrecuentes(filas: readonly FilaProductos[], max = 6): string[] {
  const grupos = new Map<string, { texto: string; n: number }>();
  for (const f of filas) {
    const { terminos } = productosDe([f.prod_obs_human, f.prod_det_ia], "", 200);
    for (const t of terminos) {
      const clave = sinTildes(t.texto);
      const g = grupos.get(clave);
      if (g) g.n += 1; else grupos.set(clave, { texto: t.texto, n: 1 });
    }
  }
  return [...grupos.values()].sort((a, b) => b.n - a.n).slice(0, max).map((g) => g.texto);
}

/** «a, b y c». */
export function enLista(items: readonly string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} y ${items[items.length - 1]}`;
}

/** El primer párrafo de la página. Cada frase depende de que haya dato. */
export function parrafoCategoria(o: {
  ciudad: string; rubro: string; calles: readonly string[]; productos: readonly string[];
}): string {
  const rubro = o.rubro.toLowerCase();
  const partes: string[] = [];
  partes.push(
    o.calles.length > 0
      ? `En ${o.ciudad}, los locales de ${rubro} están sobre ${enLista(o.calles)}.`
      : `En ${o.ciudad} encontrás locales de ${rubro}.`,
  );
  if (o.productos.length > 0) partes.push(`Entre lo que venden: ${enLista(o.productos)}.`);
  partes.push("Tocá cada uno para ver dónde queda y cómo llegar.");
  return partes.join(" ");
}

/** Corta en palabra para una meta description (≤ `max` caracteres). */
export function cortarEnPalabra(texto: string, max = 155): string {
  if (texto.length <= max) return texto;
  const corte = texto.slice(0, max - 1);
  const ult = corte.lastIndexOf(" ");
  return `${(ult > 40 ? corte.slice(0, ult) : corte).replace(/[,;:\s]+$/, "")}…`;
}
