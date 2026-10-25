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

/** Mensajes del admin para el comercio (Admin › Suscripciones). Los manda la
 *  persona desde su WhatsApp Web: acá sólo se arma el texto. Sin precios. */
function saludoNombre(nombre: string): string {
  const n = nombre.trim();
  return n && n.toLowerCase() !== "comercio" ? ` ${n}` : "";
}

export function mensajePasarQr(nombre: string): string {
  return `Hola${saludoNombre(nombre)}, soy de URUKU. Para activar tu suscripción, pagá con este QR: ${SITIO_PUBLICO}/pagar — y mandanos el comprobante por acá. ¡Gracias!`;
}

export function mensajePedirFotos(nombre: string): string {
  return `Hola${saludoNombre(nombre)}, soy de URUKU. ¿Nos mandás fotos de tus productos a tu grupo de WhatsApp con URUKU? Así salen en tu ficha y en la publicidad de la portada.`;
}

/** El número sirve para abrir un chat: al menos 8 dígitos (con prefijo de país). */
export function whatsappValido(numero: string | null | undefined): boolean {
  return soloDigitos(numero).length >= 8;
}
