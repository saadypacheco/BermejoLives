// «Visitá {ciudad}» (docs/turismo-home-y-repetidos.md §3): lo puro de la banda de turismo de la home y de la
// página /{ciudad}/turismo, sin red ni navegador, para poder probarlo con `npm test`.
//
// Acá están: cuándo aparece la banda, cómo se parten los comercios de `turismo` (guías / agencias) y de `taxis`
// (radio móviles y transporte), el orden del carrusel de lugares, el ícono de cada tipo de lugar, los accesos
// grandes y los enlaces de contacto. NUNCA un número de comercios: ni acá ni en lo que se arma con esto.
import type { NombreIcono } from "@/components/ic";
import { RUBRO_PARA_VISITAR, SUBCATEGORIAS_VISITAR, hayParaVisitar } from "./para-visitar";

export const RUBRO_TURISMO = "turismo";
export const RUBRO_TAXIS = "taxis";
export const RUBRO_HOSPEDAJE = "hospedaje";
export const RUBRO_RESTAURANTES = "restaurantes";
export const RUBRO_BEBIDAS = "bebidas";

/** Las etiquetas exactas que el backend pone al promover (docs/turismo-home-y-repetidos.md §2). */
export const SUBCAT_GUIA = "Guía de turismo";
export const SUBCAT_BODEGA = "Bodega";
/** Dentro del rubro `taxis`, lo que cuenta como «cómo moverse» (el resto son taxis de parada fija). */
export const SUBCATS_MOVERSE: readonly string[] = ["Radio móvil", "Transporte a los alrededores"];

/** Sin mayúsculas, tildes ni espacios de más: «Guía de turismo» == «guia de turismo ». */
export function normalizarEtiqueta(s: string | null | undefined): string {
  return (s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").trim().replace(/\s+/g, " ").toLowerCase();
}

/** Lo mínimo de un comercio para listarlo (lo que se recuerda en memoria y llega al HTML). */
export type LocalTurismo = {
  id: string;
  slug: string;
  nombre: string;
  subcategoria: string | null;
  whatsapp: string | null;
  telefono: string | null;
  /** La miniatura de 200 px (`portada_thumb_url`), si el comercio tiene foto propia. */
  foto: string | null;
};

const esGuia = (l: Pick<LocalTurismo, "subcategoria">): boolean => normalizarEtiqueta(l.subcategoria) === normalizarEtiqueta(SUBCAT_GUIA);

/** Los guías autorizados y el resto de los negocios del rubro `turismo` (agencias, operadoras, complejos…),
 *  cada grupo por nombre. */
export function partirTurismo<T extends Pick<LocalTurismo, "subcategoria" | "nombre">>(locales: readonly T[]): { guias: T[]; agencias: T[] } {
  const guias: T[] = [];
  const agencias: T[] = [];
  for (const l of locales) (esGuia(l) ? guias : agencias).push(l);
  const porNombre = (a: T, b: T) => a.nombre.localeCompare(b.nombre, "es");
  return { guias: guias.sort(porNombre), agencias: agencias.sort(porNombre) };
}

/** Los del rubro `taxis` que sirven para «cómo moverse»: radio móviles y transporte a los alrededores. */
export function filtrarMoverse<T extends Pick<LocalTurismo, "subcategoria" | "nombre">>(locales: readonly T[]): T[] {
  const validas = SUBCATS_MOVERSE.map(normalizarEtiqueta);
  return locales
    .filter((l) => validas.includes(normalizarEtiqueta(l.subcategoria)))
    .sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
}

// ── Lugares para visitar ────────────────────────────────────────────────────

/** El ícono de cada tipo de lugar (`SUBCATEGORIAS_VISITAR`); lo desconocido cae en «para visitar». */
const ICONO_TIPO: Record<string, NombreIcono> = {
  plaza: "visita_plaza", parque: "visita_parque", mirador: "visita_mirador", museo: "visita_museo",
  "biblioteca o archivo": "visita_biblioteca", iglesia: "visita_iglesia", patrimonio: "visita_patrimonio",
  "centro cultural": "visita_cultural", excursion: "visita_excursion", "area protegida": "visita_area",
};

export function iconoDeLugar(subcategoria: string | null | undefined): NombreIcono {
  return ICONO_TIPO[normalizarEtiqueta(subcategoria)] ?? "para-visitar";
}

/**
 * El orden del carrusel: primero los que tienen foto propia (se ven mejor), y dentro de cada tanda se
 * ALTERNAN los tipos en el orden de la lista fija (una plaza, un mirador, un museo, una excursión…), para que
 * lo primero que ve el visitante sea variado y no ocho iglesias seguidas. Máximo `max`.
 */
export function lugaresParaCarrusel<T extends Pick<LocalTurismo, "subcategoria" | "nombre" | "foto">>(lugares: readonly T[], max = 12): T[] {
  const orden = SUBCATEGORIAS_VISITAR.map((s) => normalizarEtiqueta(s));
  const clave = (l: T) => { const i = orden.indexOf(normalizarEtiqueta(l.subcategoria)); return i < 0 ? orden.length : i; };
  const alternar = (tanda: T[]): T[] => {
    const grupos = new Map<number, T[]>();
    for (const l of [...tanda].sort((a, b) => a.nombre.localeCompare(b.nombre, "es"))) {
      const k = clave(l);
      grupos.set(k, [...(grupos.get(k) ?? []), l]);
    }
    const colas = [...grupos.entries()].sort((a, b) => a[0] - b[0]).map(([, v]) => v);
    const salida: T[] = [];
    for (let ronda = 0; salida.length < tanda.length; ronda++) {
      for (const c of colas) if (c[ronda]) salida.push(c[ronda]);
    }
    return salida;
  };
  const conFoto = lugares.filter((l) => !!l.foto);
  const sinFoto = lugares.filter((l) => !l.foto);
  return [...alternar(conFoto), ...alternar(sinFoto)].slice(0, Math.max(0, max));
}

// ── Cuándo aparece ──────────────────────────────────────────────────────────

/** ¿Sale la banda «Visitá {ciudad}» (y existe la página)? Sólo si la ciudad tiene lugares para visitar. */
export function mostrarVisitaCiudad(
  pares: readonly { city_slug: string; category_slug: string }[] | null | undefined,
  ciudadSlug: string | null | undefined,
): boolean {
  return hayParaVisitar(pares, ciudadSlug);
}

/** ¿La ciudad tiene un rubro cargado? (par ciudad + rubro de `city_category_pages()`). */
export function tieneRubro(
  pares: readonly { city_slug: string; category_slug: string }[] | null | undefined,
  ciudadSlug: string,
  rubro: string,
): boolean {
  return !!pares && pares.some((p) => p.city_slug === ciudadSlug && p.category_slug === rubro);
}

// ── Enlaces ─────────────────────────────────────────────────────────────────

export const rutaTurismo = (ciudadSlug: string, ancla?: string): string => `/${ciudadSlug}/turismo${ancla ? `#${ancla}` : ""}`;

/** La lista de un rubro en la ciudad: la página `/{ciudad}/{rubro}` (con lista en el HTML). */
export const rutaRubro = (ciudadSlug: string, rubro: string): string => `/${ciudadSlug}/${rubro}`;

// ── Los accesos grandes ─────────────────────────────────────────────────────

export type AccesoVisita = { clave: string; i: NombreIcono; t: string; d: string; href: string };

/** Lo que se sabe de lo cargado en la ciudad. `null` (no se pudo leer) = se decide sólo con los rubros. */
export type ResumenTurismo = { guias: boolean; agencias: boolean; moverse: boolean };

/**
 * Los accesos de «Visitá {ciudad}», en este orden: guías, agencias, dónde dormir, dónde comer, bodegas y vinos,
 * cómo moverse. Cada uno sale SÓLO si hay algo detrás (un acceso a una lista vacía es peor que no tenerlo):
 *  - guías / agencias / moverse: según `resumen`; sin resumen, según el rubro `turismo` / `taxis` de la ciudad.
 *  - dormir / comer: si la ciudad tiene el rubro `hospedaje` / `restaurantes`.
 *  - bodegas y vinos: si tiene `bebidas` (va a la búsqueda por la subcategoría «Bodega»).
 * Sin números: ni «22 guías» ni «49 hoteles».
 */
export function accesosVisita(
  ciudadSlug: string,
  pares: readonly { city_slug: string; category_slug: string }[] | null | undefined,
  resumen: ResumenTurismo | null,
): AccesoVisita[] {
  const rubro = (r: string) => tieneRubro(pares, ciudadSlug, r);
  const hayGuias = resumen ? resumen.guias : rubro(RUBRO_TURISMO);
  const hayAgencias = resumen ? resumen.agencias : rubro(RUBRO_TURISMO);
  const hayMoverse = resumen ? resumen.moverse : rubro(RUBRO_TAXIS);
  const lista: (AccesoVisita | null)[] = [
    hayGuias ? { clave: "guias", i: "visita_guia", t: "Guías de turismo autorizados", d: "Quién te lleva y te cuenta", href: rutaTurismo(ciudadSlug, "guias") } : null,
    hayAgencias ? { clave: "agencias", i: "turismo", t: "Agencias y operadoras", d: "Paseos y excursiones", href: rutaTurismo(ciudadSlug, "agencias") } : null,
    rubro(RUBRO_HOSPEDAJE) ? { clave: "dormir", i: "hospedaje", t: "Dónde dormir", d: "Hoteles y alojamientos", href: rutaRubro(ciudadSlug, RUBRO_HOSPEDAJE) } : null,
    rubro(RUBRO_RESTAURANTES) ? { clave: "comer", i: "restaurantes", t: "Dónde comer", d: "Para probar lo de acá", href: rutaRubro(ciudadSlug, RUBRO_RESTAURANTES) } : null,
    rubro(RUBRO_BEBIDAS) ? { clave: "vinos", i: "visita_vino", t: "Bodegas y vinos", d: "Ruta del vino y más", href: `/buscar?rubro=${RUBRO_BEBIDAS}&sub=${encodeURIComponent(SUBCAT_BODEGA)}` } : null,
    hayMoverse ? { clave: "moverse", i: "taxis", t: "Cómo moverse", d: "Radio móviles y traslados", href: rutaTurismo(ciudadSlug, "moverse") } : null,
  ];
  return lista.filter((a): a is AccesoVisita => a !== null);
}

/** Las secciones de la página con lista propia (las que traen los que NO tienen punto en el mapa). */
export type SeccionTurismo = "guias" | "agencias" | "moverse";

/** Las anclas de la página y su texto, en orden: las listas propias primero (según lo cargado) y después los
 *  enlaces a las listas por rubro que ya existen. Sólo las que tienen algo detrás. */
export function navegacionTurismo(
  ciudadSlug: string,
  pares: readonly { city_slug: string; category_slug: string }[] | null | undefined,
  resumen: ResumenTurismo,
): { id: string; t: string }[] {
  const rubro = (r: string) => tieneRubro(pares, ciudadSlug, r);
  const nav: ({ id: string; t: string } | null)[] = [
    rubro(RUBRO_PARA_VISITAR) ? { id: "visitar", t: "Qué visitar" } : null,
    resumen.guias ? { id: "guias", t: "Guías" } : null,
    resumen.agencias ? { id: "agencias", t: "Agencias" } : null,
    rubro(RUBRO_HOSPEDAJE) ? { id: "dormir", t: "Dormir" } : null,
    rubro(RUBRO_RESTAURANTES) ? { id: "comer", t: "Comer" } : null,
    rubro(RUBRO_BEBIDAS) ? { id: "vinos", t: "Vinos" } : null,
    resumen.moverse ? { id: "moverse", t: "Moverse" } : null,
  ];
  return nav.filter((n): n is { id: string; t: string } => n !== null);
}

// ── Contacto ────────────────────────────────────────────────────────────────

const soloDigitos = (n: string | null | undefined): string => (n ?? "").replace(/\D/g, "");

/** El número sirve para abrir un chat de WhatsApp: al menos 8 dígitos (con prefijo de país). */
export function numeroWhatsapp(n: string | null | undefined): string | null {
  const d = soloDigitos(n);
  return d.length >= 8 ? d : null;
}

/** `tel:` del teléfono (deja el `+` inicial), o null si no hay un número de verdad (7 dígitos o más). */
export function enlaceLlamar(tel: string | null | undefined): string | null {
  const t = (tel ?? "").trim();
  if (soloDigitos(t).length < 7) return null;
  return `tel:${t.replace(/[^\d+]/g, "")}`;
}

/** Los botones que corresponden a un local: WhatsApp si tiene, llamar si tiene teléfono (y, si el «teléfono»
 *  es el mismo número que el WhatsApp, no se repite: es el mismo contacto). */
export function contactoDe(l: Pick<LocalTurismo, "whatsapp" | "telefono">): { whatsapp: string | null; llamar: string | null } {
  const whatsapp = numeroWhatsapp(l.whatsapp);
  const llamar = enlaceLlamar(l.telefono);
  const mismo = whatsapp !== null && llamar !== null && soloDigitos(l.telefono).endsWith(whatsapp.slice(-8));
  return { whatsapp, llamar: mismo ? null : llamar };
}

// ── Textos ──────────────────────────────────────────────────────────────────

/** El título de la página: «Tarija para el que la visita» (y su `<title>`, con la marca puesta por quien llama). */
export function tituloPaginaTurismo(ciudadNombre: string): string {
  return `${ciudadNombre} para el que la visita`;
}

/** La bajada de la banda y de la página: textos propios de URUKU, para el que llega por primera vez. */
export function bajadaVisita(ciudadNombre: string): string {
  return `Lo que no te podés perder en ${ciudadNombre}, quién te lleva y te lo cuenta, y dónde dormir, comer y moverte. Todo en un solo lugar, con el WhatsApp de cada uno.`;
}
