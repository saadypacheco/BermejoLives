// Lógica PURA de precios y vencimientos de las ofertas (primer incremento del
// análisis de Avellaneda a un Toque, docs/analisis-avellaneda-al-toque.md §5 y §7):
//
//   · «≈ $ ARS» al lado de un precio en bolivianos, con el cambio del día.
//   · «Vencen hoy»: qué ofertas vencen hoy o mañana, en hora de Bolivia.
//
// Sin imports (ni `@/` ni la base) para probarlo con `npm test`
// (tests/precios.test.ts). Las pantallas lo usan desde `components/precio-ars.tsx`
// y `app/page.tsx`.

/* ─── ≈ pesos argentinos ─────────────────────────────────────────────────── */

/** A cuántos pesos se redondea la aproximación: «≈ $ 12.350» se lee mejor que
 *  «$ 12.347», y de todos modos el cambio del día es una referencia. */
const REDONDEO_ARS = 10;

/**
 * Un precio en bolivianos, en pesos argentinos, aproximado.
 *
 * `arsPorBs` es cuántos Bs vale 1 ARS (`Tasas.ars_bob` de `lib/cambio.ts`, que ya
 * viene dividido por mil). Devuelve `null` —y la pantalla no muestra nada— si no
 * hay cambio cargado, si el precio no es un número positivo o si no es en Bs:
 * el dólar y el peso no se convierten acá.
 */
export function arsAproximado(precio: number | null | undefined, moneda: string, arsPorBs: number | null | undefined): number | null {
  if (moneda !== "BOB") return null;
  if (precio == null || !Number.isFinite(precio) || precio <= 0) return null;
  if (arsPorBs == null || !Number.isFinite(arsPorBs) || arsPorBs <= 0) return null;
  const ars = precio / arsPorBs;
  const r = Math.round(ars / REDONDEO_ARS) * REDONDEO_ARS;
  // Un precio chiquito (Bs 1) no puede quedar en «≈ $ 0».
  return r > 0 ? r : Math.max(1, Math.round(ars));
}

/** «12350» → «12.350». A mano y no con `toLocaleString`: el separador no tiene que
 *  depender de los datos de idioma que traiga el navegador o Node. */
export function miles(n: number): string {
  return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

/** El texto que va al lado del precio: «≈ $ 12.350 ARS», o `null` si no hay qué mostrar. */
export function precioArsTexto(precio: number | null | undefined, moneda: string, arsPorBs: number | null | undefined): string | null {
  const ars = arsAproximado(precio, moneda, arsPorBs);
  return ars == null ? null : `≈ $ ${miles(ars)} ARS`;
}

/* ─── Vencimientos, en hora de Bolivia ───────────────────────────────────── */

/** Bolivia es UTC-4 todo el año (no tiene horario de verano). */
const OFFSET_BOLIVIA_MS = -4 * 60 * 60 * 1000;

/** La fecha de hoy en Bolivia, «YYYY-MM-DD». El servidor corre en UTC: a las 21:00 de
 *  Bermejo ya es «mañana» para él, y una oferta que vence hoy se vería como vencida. */
export function hoyEnBolivia(ahora: Date = new Date()): string {
  return new Date(ahora.getTime() + OFFSET_BOLIVIA_MS).toISOString().slice(0, 10);
}

const FECHA = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Días de calendario desde hoy (Bolivia) hasta la fecha `vence_el` («YYYY-MM-DD», el
 *  ÚLTIMO día de la oferta): 0 = vence hoy, 1 = mañana, negativo = ya venció.
 *  `null` si no hay fecha o no es válida. */
export function diasHastaVencer(venceEl: string | null | undefined, ahora: Date = new Date()): number | null {
  if (!venceEl) return null;
  const v = FECHA.exec(venceEl);
  const h = FECHA.exec(hoyEnBolivia(ahora));
  if (!v || !h) return null;
  const dia = (m: RegExpExecArray) => Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  const d = Math.round((dia(v) - dia(h)) / 86400000);
  return Number.isFinite(d) ? d : null;
}

/** ¿Vence hoy (en Bolivia)? */
export function venceHoy(venceEl: string | null | undefined, ahora: Date = new Date()): boolean {
  return diasHastaVencer(venceEl, ahora) === 0;
}

/** «Vence hoy» / «Vence mañana» para la etiqueta de la tarjeta; `null` si no es ni lo uno ni lo otro. */
export function etiquetaVence(venceEl: string | null | undefined, ahora: Date = new Date()): string | null {
  const d = diasHastaVencer(venceEl, ahora);
  if (d === 0) return "Vence hoy";
  if (d === 1) return "Vence mañana";
  return null;
}

/** ¿Sigue vigente (en Bolivia)? Sin fecha de vencimiento, sí: la oferta no vence.
 *  Con fecha, vigente hasta el final de ese día (`vence_el` es el ÚLTIMO día). Una
 *  fecha ilegible no se descarta: ante la duda, la oferta se muestra. */
export function ofertaVigente(venceEl: string | null | undefined, ahora: Date = new Date()): boolean {
  const d = diasHastaVencer(venceEl, ahora);
  return d === null || d >= 0;
}

/** Saca las ofertas vencidas (`feed_publico` no las filtra), conservando el orden. */
export function soloVigentes<T extends { vence_el: string | null }>(items: readonly T[], ahora: Date = new Date()): T[] {
  return items.filter((it) => ofertaVigente(it.vence_el, ahora));
}

/** Las ofertas que vencen hoy o mañana, las de hoy primero (después, por orden de
 *  llegada). Una oferta sin fecha, ya vencida o que vence en más de dos días no entra. */
export function ofertasPorVencer<T extends { vence_el: string | null }>(items: readonly T[], ahora: Date = new Date(), max = 8): T[] {
  return items
    .map((it, i) => ({ it, i, d: diasHastaVencer(it.vence_el, ahora) }))
    .filter((x): x is { it: T; i: number; d: number } => x.d === 0 || x.d === 1)
    .sort((a, b) => a.d - b.d || a.i - b.i)
    .slice(0, max)
    .map((x) => x.it);
}

/** El título de la tira según lo que haya adentro: «Vencen hoy», «Vencen mañana» o
 *  «Vencen hoy y mañana». Es lo que se promete, ni más ni menos. */
export function tituloVencen(items: readonly { vence_el: string | null }[], ahora: Date = new Date()): string {
  const hoy = items.some((o) => diasHastaVencer(o.vence_el, ahora) === 0);
  const manana = items.some((o) => diasHastaVencer(o.vence_el, ahora) === 1);
  if (hoy && manana) return "Vencen hoy y mañana";
  return manana ? "Vencen mañana" : "Vencen hoy";
}
