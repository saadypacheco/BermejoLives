// Convertir entre pesos argentinos, bolivianos y dólares con las cotizaciones
// del sitio (tabla `cotizaciones`, cargada a mano desde /contenido).
//
// Las tres filas que hay: usd_bob (Bs por 1 USD), ars_bob (Bs por 1.000 ARS —
// así se cotiza en la frontera: "1.000 pesos = 6,8 Bs") y usd_ars (ARS por 1
// USD). La fila decía "100 ARS" en su detalle y era mentira: el valor cargado
// siempre fue por mil. Dividir por cien hacía que el conversor dijera diez
// veces más de lo que dan (0109 corrige la etiqueta). Todo se convierte pasando por bolivianos, que es
// la moneda del lugar; ARS↔USD usa usd_ars si está, que es la que la gente
// mira, y si no, también por Bs.
import type { Cotizacion } from "@/lib/data";

export type Moneda = "ARS" | "BOB" | "USD";

export const MONEDAS: { codigo: Moneda; nombre: string; simbolo: string }[] = [
  { codigo: "ARS", nombre: "Pesos argentinos", simbolo: "$" },
  { codigo: "BOB", nombre: "Bolivianos", simbolo: "Bs" },
  { codigo: "USD", nombre: "Dólares", simbolo: "US$" },
];

export type Tasas = {
  usd_bob: number | null;   // Bs por 1 USD
  ars_bob: number | null;   // Bs por 1 ARS (la tabla lo guarda por 1.000)
  usd_ars: number | null;   // ARS por 1 USD
  actualizado_en: string | null;  // la más vieja de las tres: es la que manda
};

export function tasasDe(cotizaciones: Cotizacion[]): Tasas {
  const por = new Map(cotizaciones.map((c) => [c.clave, c]));
  const v = (k: string) => { const x = por.get(k)?.valor; return x != null && x > 0 ? Number(x) : null; };
  const fechas = cotizaciones.map((c) => c.actualizado_en).filter((f): f is string => Boolean(f)).sort();
  return {
    usd_bob: v("usd_bob"),
    ars_bob: v("ars_bob") != null ? (v("ars_bob") as number) / 1000 : null,
    usd_ars: v("usd_ars"),
    actualizado_en: fechas[0] ?? null,
  };
}

/** A bolivianos. null si falta la tasa. */
function aBs(monto: number, de: Moneda, t: Tasas): number | null {
  if (de === "BOB") return monto;
  if (de === "ARS") return t.ars_bob != null ? monto * t.ars_bob : null;
  return t.usd_bob != null ? monto * t.usd_bob : null;
}

export function convertir(monto: number, de: Moneda, a: Moneda, t: Tasas): number | null {
  if (!Number.isFinite(monto) || monto < 0) return null;
  if (de === a) return monto;
  if (de === "USD" && a === "ARS" && t.usd_ars != null) return monto * t.usd_ars;
  if (de === "ARS" && a === "USD" && t.usd_ars != null) return monto / t.usd_ars;
  const bs = aBs(monto, de, t);
  if (bs == null) return null;
  if (a === "BOB") return bs;
  if (a === "ARS") return t.ars_bob != null ? bs / t.ars_bob : null;
  return t.usd_bob != null ? bs / t.usd_bob : null;
}

/** "1.234,5" — como se escribe acá. Sin decimales en pesos (no existen los centavos
 *  que importen), dos en bolivianos y dólares cuando hacen falta. */
export function formatoMonto(n: number, moneda: Moneda): string {
  const r = Math.round(n * 100) / 100;
  const dec = moneda === "ARS" || Number.isInteger(r) ? 0 : 2;
  return r.toLocaleString("es-BO", { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

export function diasDesde(iso: string | null): number | null {
  if (!iso) return null;
  const ms = Date.now() - new Date(iso).getTime();
  return Number.isFinite(ms) ? Math.floor(ms / 86400000) : null;
}

/** A partir de cuántos días la cotización se considera vieja. En la frontera
 *  cambia todos los días; dos sin cargar ya es una guía, no un dato. */
export const DIAS_VIEJA = 2;
