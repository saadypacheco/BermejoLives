/**
 * «Mandarle su ficha por WhatsApp»: el mensaje que el agente le manda al dueño
 * desde SU celular (WAHA sólo lee: no puede enviar) y el link para abrirlo.
 *
 * SIN PRECIOS, a propósito. Los precios están en la guía de venta y se dicen en
 * persona; un número escrito en un WhatsApp reenviable se vuelve una promesa.
 */

/** La ficha pública se comparte siempre con el dominio de producción, aunque el
 *  agente esté usando QA: el dueño tiene que recibir el link real. */
export const SITIO_PUBLICO = "https://uruku.bo";

export function linkFichaPublica(slug: string): string {
  return `${SITIO_PUBLICO}/comercios/${encodeURIComponent(slug)}`;
}

/** El texto del mensaje: saludo, el link de su ficha, qué gana completándola y
 *  cómo sumarse a un plan (respondiendo este mismo mensaje). */
export function mensajeFicha(nombre: string, slug: string): string {
  const quien = nombre.trim() && nombre.trim().toLowerCase() !== "comercio" ? `, ${nombre.trim()}` : "";
  return [
    `Hola${quien}. Soy de URUKU: tu local ya está en el mapa.`,
    "",
    `Mirá tu ficha acá: ${linkFichaPublica(slug)}`,
    "",
    "Si la completás (horario, fotos y qué vendés), te encuentran más clientes por lo que vendés y te escriben directo a tu WhatsApp.",
    "",
    "Si querés sumarte a un plan, respondé este mensaje y te contamos cómo.",
  ].join("\n");
}

/** Sólo los dígitos de un número. */
export function soloDigitos(n: string | null | undefined): string {
  return (n ?? "").replace(/\D/g, "");
}

/** `https://wa.me/<número>?text=…`. El número va con prefijo de país y sin signos. */
export function linkWhatsapp(numero: string, texto: string): string {
  return `https://wa.me/${soloDigitos(numero)}?text=${encodeURIComponent(texto)}`;
}
