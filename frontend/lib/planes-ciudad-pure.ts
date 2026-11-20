// «Qué podés hacer en {ciudad}»: los planes ilustrados (docs/home-ciudades.md §12) y los gentilicios (§12, §15).
// Lo puro, sin React ni red, para probarlo con `npm test`.
//
// Regla de todo el archivo: un plan SALE SOLO si la ciudad tiene datos para su destino; la ciudad no se configura
// a mano. Y NUNCA una cantidad de comercios (ningún número al público).
import { HREF_PARA_VISITAR, RUBRO_PARA_VISITAR } from "./para-visitar";
import { rutaSabores } from "./platos-pure";
import { normalizarEtiqueta } from "./turismo-ciudad-pure";

// ── Gentilicios ─────────────────────────────────────────────────────────────

/** `f` = femenino singular, para «Noche chapaca»; `mp` = masculino plural, para «Sabores chapacos». */
const GENTILICIOS: Record<string, { f: string; mp: string }> = {
  tarija: { f: "chapaca", mp: "chapacos" },
  "santa-cruz": { f: "cruceña", mp: "cruceños" },
  "la-paz": { f: "paceña", mp: "paceños" },
  cochabamba: { f: "cochabambina", mp: "cochabambinos" },
  oruro: { f: "orureña", mp: "orureños" },
  sucre: { f: "sucrense", mp: "sucrenses" },
  potosi: { f: "potosina", mp: "potosinos" },
  bermejo: { f: "bermejeña", mp: "bermejeños" },
};

/** «Noche chapaca» / «Noche de Trinidad»: lo que va después de «Noche». Las ciudades sin gentilicio conocido usan «de {ciudad}». */
export function nocheDe(ciudadSlug: string, ciudadNombre: string): string {
  const g = GENTILICIOS[ciudadSlug];
  return g ? g.f : `de ${ciudadNombre}`;
}

/** «Sabores chapacos» / «Sabores de Trinidad»: lo que va después de «Sabores». */
export function saboresDe(ciudadSlug: string, ciudadNombre: string): string {
  const g = GENTILICIOS[ciudadSlug];
  return g ? g.mp : `de ${ciudadNombre}`;
}

/** El título de la página `/{ciudad}/sabores`. */
export const tituloSabores = (ciudadSlug: string, ciudadNombre: string): string => `Sabores ${saboresDe(ciudadSlug, ciudadNombre)}`;

// ── Los planes ──────────────────────────────────────────────────────────────

/** Las ilustraciones de `components/ilustraciones/`. */
export type IlustracionId =
  | "vino" | "centro" | "miradores" | "cascadas" | "noche" | "sabores" | "lagunas" | "parques" | "museos" | "mercados";

export type PlanId = "vino" | "centro" | "miradores" | "parques" | "museos" | "cascadas" | "lagunas" | "noche" | "sabores";

export type Plan = {
  id: PlanId;
  titulo: string;
  bajada: string;
  ilustracion: IlustracionId;
  href: string;
  /** Sólo en la tarjeta grande: la etiqueta de arriba del título y el texto del botón. */
  etiqueta: string;
  cta: string;
};

/** Lo que hace falta saber de la ciudad para decidir los planes. */
export type DatosPlanes = {
  ciudadSlug: string;
  ciudadNombre: string;
  /** Los rubros con comercios en la ciudad (`rubrosDeCiudad`); `null` = no se sabe: no sale ningún plan. */
  rubros: ReadonlySet<string> | null;
  /** Las subcategorías de «Para visitar» que la ciudad tiene (cualquier forma de escribirlas: se normalizan). */
  subcategorias: Iterable<string>;
  /** ¿La ciudad tiene platos típicos aprobados? */
  hayPlatos: boolean;
};

export type PlanesCiudad = {
  /** La tarjeta grande (la primera con datos entre: ruta del vino, centro histórico, noche), o `null`. */
  grande: Plan | null;
  /** El resto, en una grilla de 2 columnas. */
  grilla: Plan[];
  /** «Ver todos los planes en el mapa ›», si la ciudad tiene lugares para visitar. */
  verTodos: string | null;
};

export const MAX_GRILLA_PLANES = 6;

const hrefSub = (sub: string): string => `/buscar?rubro=${RUBRO_PARA_VISITAR}&sub=${encodeURIComponent(sub)}&vista=mapa`;
const hrefRubroMapa = (rubro: string): string => `/buscar?rubro=${encodeURIComponent(rubro)}&vista=mapa`;

/** El orden de la grilla (el de la maqueta aprobada; los parques y museos, al final). La tarjeta grande sale de acá. */
const ORDEN_GRILLA: readonly PlanId[] = ["centro", "miradores", "cascadas", "noche", "sabores", "lagunas", "parques", "museos"];
const ORDEN_GRANDE: readonly PlanId[] = ["vino", "centro", "noche"];

/** Los planes de la ciudad que tienen datos, según la tabla del §12. Sin `rubros` (no se leyó) no sale ninguno. */
export function planesDeCiudad(d: DatosPlanes): PlanesCiudad {
  const { rubros } = d;
  if (rubros === null) return { grande: null, grilla: [], verTodos: null };
  const subs = new Set([...d.subcategorias].map(normalizarEtiqueta));
  const visitar = rubros.has(RUBRO_PARA_VISITAR);
  /** La primera de las subcategorías (en su forma canónica) que la ciudad tiene. */
  const primeraSub = (...candidatas: string[]): string | null =>
    (visitar ? candidatas.find((s) => subs.has(normalizarEtiqueta(s))) : undefined) ?? null;

  const todos = new Map<PlanId, Plan>();
  const poner = (p: Plan) => todos.set(p.id, p);

  if (rubros.has("bodegas")) {
    poner({
      id: "vino", titulo: "La ruta del vino y el singani", bajada: "Viñedos, bodegas y singani", ilustracion: "vino",
      href: hrefRubroMapa("bodegas"), etiqueta: "Recorrido", cta: "Ver la ruta en el mapa ›",
    });
  }
  const centro = primeraSub("Plaza", "Iglesia", "Patrimonio");
  if (centro) {
    poner({
      id: "centro", titulo: "Centro histórico", bajada: "Plazas, iglesias y casonas", ilustracion: "centro",
      href: hrefSub(centro), etiqueta: "Para caminar", cta: "Verlo en el mapa ›",
    });
  }
  const mirador = primeraSub("Mirador");
  if (mirador) {
    poner({ id: "miradores", titulo: "Miradores", bajada: "La ciudad desde arriba", ilustracion: "miradores", href: hrefSub(mirador), etiqueta: "Para mirar", cta: "Verlos en el mapa ›" });
  }
  const parque = primeraSub("Parque");
  if (parque) {
    poner({ id: "parques", titulo: "Parques", bajada: "Verde y aire libre para caminar", ilustracion: "parques", href: hrefSub(parque), etiqueta: "Al aire libre", cta: "Verlos en el mapa ›" });
  }
  const museo = primeraSub("Museo", "Centro cultural");
  if (museo) {
    poner({ id: "museos", titulo: "Museos", bajada: "Historia y cultura de la ciudad", ilustracion: "museos", href: hrefSub(museo), etiqueta: "Para aprender", cta: "Verlos en el mapa ›" });
  }
  const excursion = primeraSub("Excursión");
  if (excursion) {
    poner({ id: "cascadas", titulo: "Cascadas y ríos", bajada: "Para pasar el día al aire libre", ilustracion: "cascadas", href: hrefSub(excursion), etiqueta: "Excursión", cta: "Verlas en el mapa ›" });
  }
  const area = primeraSub("Área protegida");
  if (area) {
    poner({ id: "lagunas", titulo: "Lagunas y montaña", bajada: "Reservas naturales cerca", ilustracion: "lagunas", href: hrefSub(area), etiqueta: "Naturaleza", cta: "Verlas en el mapa ›" });
  }
  if (rubros.has("nocturna")) {
    poner({
      id: "noche", titulo: `Noche ${nocheDe(d.ciudadSlug, d.ciudadNombre)}`, bajada: "Boliches, peñas y karaoke", ilustracion: "noche",
      href: hrefRubroMapa("nocturna"), etiqueta: "Esta noche", cta: "Verlo en el mapa ›",
    });
  }
  if (d.hayPlatos) {
    poner({
      id: "sabores", titulo: tituloSabores(d.ciudadSlug, d.ciudadNombre), bajada: `Comida típica de ${d.ciudadNombre}`, ilustracion: "sabores",
      href: rutaSabores(d.ciudadSlug), etiqueta: "Para probar", cta: "Ver los sabores ›",
    });
  }

  const idGrande = ORDEN_GRANDE.find((id) => todos.has(id));
  const grande = idGrande ? todos.get(idGrande) ?? null : null;
  const grilla = ORDEN_GRILLA.filter((id) => id !== idGrande && todos.has(id)).map((id) => todos.get(id) as Plan)
    .slice(0, MAX_GRILLA_PLANES);
  return { grande, grilla, verTodos: visitar ? HREF_PARA_VISITAR : null };
}

/** ¿Hay al menos un plan para mostrar? Sin ninguno, el bloque no aparece. */
export function hayPlanes(p: PlanesCiudad): boolean {
  return p.grande !== null || p.grilla.length > 0;
}
