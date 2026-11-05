// Admin › Negocios › «Dados de baja»: qué decir de cada uno según `baja_motivo`.
//
//  - 'admin'         lo dio de baja el equipo.
//  - null / vacío    baja vieja, sin motivo registrado.
//  - 'sin_verificar' se registró solo y está OCULTO hasta que el dueño confirma su WhatsApp
//                    o alguien del equipo lo aprueba. Se aprueba con el mismo endpoint que
//                    «Reactivar» (POST /admin/comercio/{id}/reactivar): lo único que cambia es
//                    cómo se llama y qué se le pregunta al admin.

export type BajaMotivo = "admin" | "sin_verificar" | string | null | undefined;

export function esSinVerificar(motivo: BajaMotivo): boolean {
  return motivo === "sin_verificar";
}

/** Texto + ícono (nunca sólo color) de la línea de motivo. */
export function etiquetaBaja(motivo: BajaMotivo): { texto: string; icono: "cerrajeria" | "aviso" | "reloj" } {
  if (esSinVerificar(motivo)) return { texto: "Sin verificar", icono: "reloj" };
  if (motivo === "admin") return { texto: "Dado de baja por el admin", icono: "cerrajeria" };
  return { texto: "Sin motivo registrado", icono: "aviso" };
}

/** El botón de la fila: «Aprobar» para los sin verificar, «Reactivar» para el resto. */
export function botonReactivar(motivo: BajaMotivo): { texto: string; enCurso: string; fallo: string } {
  return esSinVerificar(motivo)
    ? { texto: "Aprobar", enCurso: "Aprobando…", fallo: "No se pudo aprobar" }
    : { texto: "Reactivar", enCurso: "Reactivando…", fallo: "No se pudo reactivar" };
}

/** La pregunta de confirmación (la acción es visible al público: no va sin confirmar). */
export function confirmarReactivar(motivo: BajaMotivo, nombre: string | null | undefined): string {
  const n = nombre || "este negocio";
  return esSinVerificar(motivo)
    ? `¿Aprobar "${n}"? Se registró solo y su WhatsApp todavía no se confirmó. Pasa a verse en URUKU.`
    : `¿Reactivar "${n}"? Vuelve a verse en URUKU.`;
}

/** La línea de resumen sobre la lista. */
export function resumenBajas(total: number, sinVerificar: number): string {
  const base = `${total} ${total === 1 ? "negocio dado de baja" : "negocios dados de baja"}`;
  const extra = sinVerificar > 0 ? ` (${sinVerificar} sin verificar)` : "";
  return `${base}${extra}. No se ven en URUKU hasta que los reactives o los apruebes.`;
}
