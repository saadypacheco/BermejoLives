// Piezas compartidas por los dos ingresos (comerciante y comprador): celular +
// clave de 6 números, o confirmación por WhatsApp para la primera vez y para
// «me olvidé la clave».

/** Cada cuánto se pregunta si ya llegó el mensaje de confirmación. */
export const POLL_MS = 2500;

/** Pasado este tiempo el código deja de servir: se corta la espera y se pide otro. */
export const CONFIRMACION_VENCE_MS = 15 * 60 * 1000;

export const LARGO_CLAVE = 6;

/** La clave son sólo números: lo demás que se tipee o pegue se descarta. */
export function soloClave(texto: string): string {
  return texto.replace(/\D/g, "").slice(0, LARGO_CLAVE);
}

/** Lo que dijo el backend (`detail`), tal cual; si no dijo nada, el texto de respaldo. */
export async function detalleDeError(res: Response, respaldo: string): Promise<string> {
  const d: unknown = await res.json().catch(() => null);
  if (typeof d === "object" && d !== null) {
    const detail = (d as Record<string, unknown>).detail;
    if (typeof detail === "string" && detail) return detail;
  }
  return respaldo;
}

/** Un error de red (fetch tira TypeError) se dice como tal; el resto, con su mensaje. */
export function mensajeDeError(ex: unknown, respaldo: string): string {
  if (ex instanceof TypeError) return "Sin conexión. Revisá tu internet y probá de nuevo.";
  return ex instanceof Error && ex.message ? ex.message : respaldo;
}
