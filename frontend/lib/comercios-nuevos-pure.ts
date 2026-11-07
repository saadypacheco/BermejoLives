// La línea del home que dice cuántos comercios se sumaron (decisión del dueño, 6/11/2026).
//
// El número es REAL: lo cuenta la base, y sólo con los comercios que el público ve (la lectura
// anónima respeta RLS: un alta que espera confirmación no cuenta). Se cuenta desde el 7/11/2026:
// lo cargado antes no suma, por pedido del dueño. Mientras no haya ninguno en las últimas 24 horas
// (o si la base no contesta), la línea dice que se suman comercios, sin número.

/** Desde cuándo se cuentan (medianoche de Bolivia, UTC-4). */
export const CONTAR_DESDE = "2026-11-07T00:00:00-04:00";

const DIA_MS = 24 * 60 * 60 * 1000;

/** El inicio de la ventana: las últimas 24 horas, pero nunca antes de `CONTAR_DESDE`. */
export function desdeConteo(ahora: Date = new Date()): string {
  const hace24 = ahora.getTime() - DIA_MS;
  return new Date(Math.max(hace24, Date.parse(CONTAR_DESDE))).toISOString();
}

/** El texto de la línea. Sin número (0, null) no se inventa uno. */
export function lineaComerciosNuevos(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n) || n <= 0) return "Cada día se suman comercios nuevos";
  const cantidad = Math.floor(n).toLocaleString("es-BO");
  return n === 1
    ? "1 comercio nuevo en las últimas 24 horas"
    : `${cantidad} comercios nuevos en las últimas 24 horas`;
}
