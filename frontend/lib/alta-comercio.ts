// El alta por autoregistro (POST /auth/comercio/registro): el negocio nace OCULTO.
//
// Nadie probó que el WhatsApp sea del que se registra, así que el negocio no se ve en URUKU
// hasta que el dueño lo confirma por WhatsApp o el equipo lo aprueba (Admin › Dados de baja ›
// «Aprobar»). El backend lo dice con `oculto_hasta_confirmar: true` y manda el `aviso`, que
// se le muestra tal cual al comerciante.

/** El aviso a mostrar tras el alta, o null si el negocio ya se ve (respuesta sin la marca). */
export function avisoDeAlta(data: unknown): string | null {
  if (typeof data !== "object" || data === null) return null;
  const d = data as Record<string, unknown>;
  if (d.oculto_hasta_confirmar !== true) return null;
  return typeof d.aviso === "string" && d.aviso.trim()
    ? d.aviso.trim()
    : "Tu negocio todavía no se ve en URUKU: aparece cuando confirmes tu WhatsApp.";
}
