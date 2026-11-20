// El clima de cada ciudad (tabla `clima_ciudades`, migración 0201): lo puro, para poder probarlo con `npm test`.
// El backend lo refresca cada 30 minutos; un dato de más de 3 horas no se muestra (un «22°» viejo es peor que nada).

export type ClimaCiudad = { temp_c: number; descripcion: string | null };

export const VIGENCIA_CLIMA_MS = 3 * 60 * 60 * 1000;

type FilaClima = { temp_c: unknown; descripcion?: unknown; actualizado_en?: unknown } | null | undefined;

/** La fila de `clima_ciudades` lista para mostrar, o `null` si falta, no tiene temperatura, no tiene fecha
 *  o es más vieja que 3 horas. Nunca tira. */
export function climaVigente(fila: FilaClima, ahora: Date = new Date()): ClimaCiudad | null {
  if (!fila) return null;
  const temp = typeof fila.temp_c === "number" ? fila.temp_c : typeof fila.temp_c === "string" ? Number(fila.temp_c) : NaN;
  if (!Number.isFinite(temp)) return null;
  const cuando = typeof fila.actualizado_en === "string" ? Date.parse(fila.actualizado_en) : NaN;
  if (!Number.isFinite(cuando)) return null;
  const edad = ahora.getTime() - cuando;
  // Una fecha en el futuro (reloj corrido) tampoco es confiable.
  if (edad < -5 * 60_000 || edad > VIGENCIA_CLIMA_MS) return null;
  return { temp_c: temp, descripcion: typeof fila.descripcion === "string" && fila.descripcion.trim() ? fila.descripcion : null };
}
