/**
 * La marca dicha en palabras, y cómo cambia según la ciudad.
 *
 * EL PROBLEMA QUE RESUELVE
 * ========================
 * El manual de identidad fija el tagline en «Antes de cruzar, Uruku.» y el
 * mensaje principal en «Todo Bermejo en un solo lugar». Las dos frases son de
 * frontera — y el mismo manual, en su Visión, dice que URUKU va a «cada rincón
 * del país». En Santa Cruz, La Paz o Cochabamba nadie cruza nada: el tagline
 * ahí no significa nada, y el mensaje nombra una ciudad que no es la suya.
 *
 * Así que la marca tiene tres niveles, y sólo el primero es fijo:
 *
 *   URUKU                                 siempre
 *   Todo {Ciudad} en un solo lugar        la ciudad
 *   Antes de cruzar / salir, Uruku.       si la ciudad es de frontera
 *
 * `es_frontera` ya existe en la base desde la 0124, y el sitio ya la usa para
 * mostrar u ocultar la guía del paso, la cotización del peso y las chalanas.
 * Es el mismo interruptor: una decisión, un lugar.
 *
 * El glosario del manual dice que «cruzar» es el verbo central de la marca.
 * Donde no hay río que cruzar, el verbo equivalente —el que fija el nombre en
 * el momento exacto de uso, que es la función que el manual le pide al
 * tagline— es SALIR.
 */

export const MARCA = "Uruku";
export const CIUDAD_POR_DEFECTO = "Bermejo";

/** «Antes de cruzar, Uruku.» en la frontera; «Antes de salir, Uruku.» en el resto. */
export function tagline(esFrontera: boolean | null | undefined): string {
  return esFrontera ? "Antes de cruzar, Uruku." : "Antes de salir, Uruku.";
}

/** El mismo titular cuando todavía NO hay ciudad.
 *
 *  Es lo que ve el que llega de Google y lo que sale en la vista previa de un
 *  enlace: ahí no hay cookie, así que no hay ciudad que nombrar. Nombrar la
 *  de respaldo convierte a URUKU en «el sitio de Bermejo» para todo el que
 *  busque la marca desde cualquier otra parte de Bolivia. */
export const MENSAJE_SIN_CIUDAD = "Toda tu ciudad en un solo lugar";

/** El titular: «Todo Bermejo en un solo lugar». */
export function mensajePrincipal(ciudad?: string | null): string {
  return `Todo ${ciudad || CIUDAD_POR_DEFECTO} en un solo lugar`;
}

/** El <title> de una página. Sin ciudad, el titular no nombra ninguna. */
export function titulo(ciudad?: string | null): string {
  return `${MARCA} · ${ciudad ? mensajePrincipal(ciudad) : MENSAJE_SIN_CIUDAD}`;
}

/** La descripción para buscadores y para la vista previa al compartir.
 *
 *  Cambia el final además del nombre: «antes de cruzar» prometido en una
 *  ciudad del interior es una frase que no le habla a nadie. */
export function descripcion(ciudad?: string | null, esFrontera?: boolean | null): string {
  if (!ciudad) {
    // Sin ciudad: ni «tu visita a X» ni «antes de cruzar». Lo que sirve en
    // cualquier punto del país es qué se encuentra y cómo se le escribe.
    return "Los comercios de tu ciudad en un solo lugar: qué se vende, cuánto cuesta, dónde queda y el WhatsApp de cada local.";
  }
  const n = ciudad;
  return esFrontera
    ? `Comercios, ofertas, cambio del día y datos útiles para tu visita a ${n}. Antes de cruzar, Uruku.`
    : `Comercios, ofertas y lo que se vende hoy en ${n}: qué hay, cuánto cuesta y dónde queda. Antes de salir, Uruku.`;
}

/** Lo que va bajo el titular en la imagen que se ve al compartir el enlace. */
export function bajadaOg(esFrontera?: boolean | null): string {
  return esFrontera ? "Ofertas y cambio del día, antes de cruzar." : "Ofertas y comercios, antes de salir.";
}

/** Los colores oficiales (manual de identidad · Color). Acá y no sueltos en
 *  cada archivo: la imagen de vista previa se dibuja en el servidor, donde no
 *  hay CSS del que leer las variables. */
export const COLOR = {
  verde: "#1D8D52",
  verdeHondo: "#10623E",
  verdeTexto: "#1A764C",
  fondo: "#F9F6ED",
  cielo: "#E3EDFA",
  texto: "#214533",
  texto2: "#4E6053",
} as const;
