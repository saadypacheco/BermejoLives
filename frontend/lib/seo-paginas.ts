/**
 * Helpers puros de las páginas de contenido indexables (home, /cambio,
 * /comprar-en-bermejo, /que-es-uruku). Spec: docs/visibilidad-buscadores-ia.md
 * §3.8 (frescura) y §3.10 (entidad).
 *
 * PUREZA: sin red ni cookies y con imports relativos, para que `npm test` lo cargue.
 */
import { FOUNDER } from "./marca";
import type { JsonLdNode } from "./seo";

/** Una cotización es «de hoy» si tiene menos de 36 horas (§3.8). */
export const HORAS_FRESCA = 36;

/** ¿La fecha ISO tiene menos de `HORAS_FRESCA` horas? Sin fecha o ilegible, no. */
export function esFresca(iso: string | null | undefined, ahora: Date = new Date()): boolean {
  if (!iso) return false;
  const ms = ahora.getTime() - new Date(iso).getTime();
  return Number.isFinite(ms) && ms >= -60_000 && ms < HORAS_FRESCA * 3_600_000;
}

const MESES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];

/** «25 de octubre», en la hora de Bolivia (UTC-4): un ISO de madrugada en UTC
 *  no cae en el día siguiente al que vio la gente. */
export function fechaLarga(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return null;
  const d = new Date(t - 4 * 3_600_000);
  return `${d.getUTCDate()} de ${MESES[d.getUTCMonth()]}`;
}

/**
 * Suma `founder` y `foundingDate` al nodo `Organization` (dato del dueño, 2/11).
 * Se hace acá y no en `organizationNodes()` para no tocar `lib/seo.ts`. Los demás
 * nodos pasan igual.
 */
export function conFundador(nodes: readonly JsonLdNode[]): JsonLdNode[] {
  return nodes.map((n) => n["@type"] === "Organization"
    ? {
        ...n,
        founder: { "@type": "Person", name: FOUNDER.nombre, jobTitle: FOUNDER.cargo },
        foundingDate: FOUNDER.desde,
      }
    : n);
}
