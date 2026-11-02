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

/* ─── La marca para buscadores y asistentes de IA ───────────────────────────
 *
 * Docs: docs/visibilidad-buscadores-ia.md §3.10 (entidad y marca). Estas
 * constantes se usan IDÉNTICAS en el JSON-LD, las metas de la home, /que-es-uruku,
 * llms.txt y las bios de las redes: que el nombre, el descriptor y la frase
 * canónica no varíen es lo que le permite a un buscador (o a un modelo) saber
 * que todo eso es la misma entidad. Decididas por el dueño el 2/11.
 *
 * `MARCA` (arriba) sigue siendo «Uruku» (la plantilla de títulos, que sigue el
 * manual). En texto corrido y en datos estructurados el nombre es «URUKU». */

/** El nombre en texto y en datos estructurados (`Organization.name`). */
export const BRAND_NAME = "URUKU";

/** Otras formas con las que se nombra a la marca (`Organization.alternateName`). */
export const BRAND_ALTERNATE_NAMES: readonly string[] = ["Uruku", "uruku.bo"];

/** El lema de la marca entera (`Organization.slogan`). Fijo para todo el país;
 *  el tagline de frontera de `tagline()` cambia por ciudad y NO es el slogan. */
export const SLOGAN = "Llevá tu ciudad con vos.";

/** Qué es URUKU en una frase corta. */
export const DESCRIPTOR = "Guía de comercios y servicios de Bolivia";

/** La frase canónica: qué es URUKU, dónde nació y qué ofrece. Se usa tal cual en
 *  `Organization.description`, el primer párrafo de /que-es-uruku, llms.txt y
 *  las bios. No se reescribe por página. */
export const ONE_LINER =
  "URUKU es la guía de comercios y servicios de Bolivia, nacida en Bermejo, en la frontera con Argentina: qué vende cada local, dónde queda y cómo llegar. Llevá tu ciudad con vos.";

/** Quién responde por el sitio (para /que-es-uruku y datos de contacto). Por
 *  ahora es el equipo, no una persona: una sola constante para cambiarlo. */
export const RESPONSIBLE = "Equipo URUKU";

/** Dirección pública del sitio, sin barra final. */
export const SITE_URL = "https://uruku.bo";

/** Contacto (NAP: mismo en todos lados). */
export const CONTACT = {
  telefono: "+59167671888",
  email: "info@uruku.bo",
  area: "Bermejo, Tarija, Bolivia",
} as const;

/** Perfiles que identifican a la marca como entidad fuera del sitio (Wikidata,
 *  Google Business, Bing Places, Apple Business Connect). Van a `sameAs` de la
 *  Organization junto con las redes de `getRedes()`. VACÍO hasta que existan:
 *  nunca se inventa un perfil. */
export const ENTITY_PROFILES: readonly string[] = [];
