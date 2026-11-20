// El home de las ciudades (todas menos Bermejo) y los saludos de Dax: lo puro, sin React ni red, para poder
// probarlo con `npm test` (docs/home-ciudades.md).
//
// Acá están: las franjas del día (hora de Bolivia), el orden y el cartel de los botones de intención, sus
// opciones, el carrusel de comercios (rubros, títulos, foto y orden) y el
// saludo y las sugerencias de Dax. Regla de todo el archivo: NUNCA un acceso a un rubro sin comercios en la
// ciudad y NUNCA una cantidad de comercios.
import type { NombreIcono } from "@/components/ic";
import { accesoConComercios } from "./accesos-ciudad";
import { distanciaMetros } from "./distancia";
import { abiertoAhora, ahoraEnBolivia } from "./horario";
import { RUBRO_PARA_VISITAR } from "./para-visitar";

// ── Las franjas del día ─────────────────────────────────────────────────────

export type Franja = "madrugada" | "manana" | "mediodia" | "tarde" | "noche";

/** 0-6 madrugada · 6-11 mañana · 11-15 mediodía · 15-19 tarde · 19-24 noche. `hora` es la de Bolivia. */
export function franjaDe(hora: number): Franja {
  if (hora < 6) return "madrugada";
  if (hora < 11) return "manana";
  if (hora < 15) return "mediodia";
  if (hora < 19) return "tarde";
  return "noche";
}

/** La franja de ahora, con la hora de BOLIVIA (venga de donde venga quien mire). */
export function franjaAhora(base: Date = new Date()): Franja {
  return franjaDe(ahoraEnBolivia(base).getHours());
}

// ── Los rubros de cada cosa ─────────────────────────────────────────────────

export const RUBROS_COMER: readonly string[] = ["cafeteria", "restaurantes", "comida-rapida", "panaderia"];
export const RUBROS_DORMIR: readonly string[] = ["hospedaje"];
export const RUBROS_SERVICIOS: readonly string[] = [
  "taller-mecanico", "peluqueria", "servicio-tecnico", "cerrajeria", "lavadero", "gomeria-servicio",
  // «y los que haya en la ciudad»: los demás rubros de oficios.
  "servicios", "limpieza", "carpinteria", "herreria", "pintura", "alquiler",
];
export const RUBROS_BANCOS: readonly string[] = ["cajeros", "cambio"];
export const RUBRO_FARMACIA = "farmacia";

/** Los rubros de los carruseles de las franjas (menos los comerciales de la tarde): se piden uno por uno a la base. */
export const RUBROS_DE_FRANJAS: readonly string[] = ["cafeteria", "panaderia", "restaurantes", "comida-rapida", "nocturna", "farmacia"];

/** ¿La ciudad tiene turnos de farmacia cargados (de hoy o de los próximos días)? `null` = no se pudo leer: no se afirma. */
export function hayTurnosCargados(turnos: readonly unknown[] | null | undefined): boolean {
  return Array.isArray(turnos) && turnos.length > 0;
}

/** Los rubros que ya tienen su propio botón: «Negocios» no los repite. */
const RUBROS_CON_BOTON_PROPIO = new Set<string>([
  ...RUBROS_COMER, ...RUBROS_DORMIR, ...RUBROS_SERVICIOS, ...RUBROS_BANCOS, RUBRO_FARMACIA, "otros",
]);

/** El nombre que se usa si el catálogo de rubros no trae el del rubro. */
const NOMBRE_RUBRO: Record<string, string> = {
  cafeteria: "Cafeterías", restaurantes: "Restaurantes", "comida-rapida": "Comida rápida", panaderia: "Panaderías",
  hospedaje: "Hoteles y hostales", farmacia: "Todas las farmacias", cajeros: "Cajeros y bancos", cambio: "Casas de cambio",
  "taller-mecanico": "Talleres mecánicos", peluqueria: "Peluquerías", "servicio-tecnico": "Servicio técnico",
  cerrajeria: "Cerrajerías", lavadero: "Lavaderos", "gomeria-servicio": "Gomerías", servicios: "Servicios",
  limpieza: "Limpieza", carpinteria: "Carpinterías", herreria: "Herrerías", pintura: "Pinturerías", alquiler: "Alquileres",
  nocturna: "Boliches y karaoke",
};

export type RubroCatalogo = { slug: string; nombre: string; comercial?: boolean | null };

/** Sin el emoji que traen los nombres de la base («👟 Calzado» → «Calzado»). Copia corta de `sinEmoji`,
 *  para que este módulo no dependa de nada más. */
function limpio(nombre: string): string {
  const n = nombre.trim();
  return n.replace(/^[^\p{L}\p{N}]+/u, "").trim() || n;
}

function nombreDeRubro(slug: string, catalogo: readonly RubroCatalogo[]): string {
  return NOMBRE_RUBRO[slug] ?? limpio(catalogo.find((r) => r.slug === slug)?.nombre ?? slug);
}

export const hrefRubro = (slug: string): string => `/buscar?rubro=${encodeURIComponent(slug)}&vista=mapa`;

// ── Los botones de intención ────────────────────────────────────────────────

export type IdIntencion = "comer" | "negocios" | "productos" | "servicios" | "farmacias" | "bancos" | "dormir";

/** Una opción del panel de un botón: lleva a un mapa (o a la página de turnos) con algo adentro. */
/** `rubro` = el slug, para dibujar el ícono del rubro (`IcRubro`); sin él, se usa `i`. */
export type OpcionIntencion = { t: string; d?: string; href: string; i: NombreIcono; rubro?: string };

export type Intencion = {
  id: IdIntencion;
  titulo: string;
  /** La bajada del encabezado del panel. */
  subtitulo: string;
  icono: NombreIcono;
  /** «opciones» = lista de enlaces; «productos» = chips de productos que llevan a `/buscar?q=…`. */
  tipo: "opciones" | "productos";
  opciones: OpcionIntencion[];
  productos: string[];
  /** El cartel verde adentro del botón («Cenar», «De turno»…); `null` si no es el resaltado de la franja. */
  cartel: string | null;
};

/** El orden de los botones y el resaltado de cada franja (docs/home-ciudades.md §4). */
const ORDEN: Record<Franja, IdIntencion[]> = {
  manana: ["comer", "negocios", "productos", "servicios", "farmacias", "bancos", "dormir"],
  mediodia: ["comer", "negocios", "productos", "servicios", "farmacias", "bancos", "dormir"],
  tarde: ["negocios", "productos", "servicios", "comer", "farmacias", "bancos", "dormir"],
  noche: ["comer", "negocios", "productos", "dormir", "farmacias", "bancos", "servicios"],
  madrugada: ["farmacias", "bancos", "dormir", "comer", "negocios", "productos", "servicios"],
};
const RESALTADO: Record<Franja, { id: IdIntencion; cartel: string }> = {
  manana: { id: "comer", cartel: "Desayunos" },
  mediodia: { id: "comer", cartel: "Almuerzos" },
  tarde: { id: "negocios", cartel: "Abiertos" },
  noche: { id: "comer", cartel: "Cenar" },
  madrugada: { id: "farmacias", cartel: "De turno" },
};

export const ordenIntenciones = (f: Franja): IdIntencion[] => [...ORDEN[f]];
export const resaltadoDeFranja = (f: Franja): { id: IdIntencion; cartel: string } => RESALTADO[f];

/** Opciones fijas (un rubro cada una) que la ciudad tiene. `accesoConComercios` es la regla única del
 *  proyecto para «sólo si la ciudad lo tiene». */
function opcionesDeRubros(
  slugs: readonly string[], rubros: ReadonlySet<string> | null, catalogo: readonly RubroCatalogo[],
): OpcionIntencion[] {
  return slugs
    .filter((s) => accesoConComercios(hrefRubro(s), rubros) && (rubros === null || rubros.has(s)))
    .map((s) => ({ t: nombreDeRubro(s, catalogo), href: hrefRubro(s), i: "comercios" as const, rubro: s }));
}

export type DatosIntenciones = {
  franja: Franja;
  ciudadSlug: string;
  /** Los rubros con comercios en la ciudad (`rubrosDeCiudad`); `null` = no se sabe. */
  rubros: ReadonlySet<string> | null;
  catalogo: readonly RubroCatalogo[];
  /** ¿La ciudad tiene turnos de farmacia cargados para hoy? */
  hayTurnos: boolean;
  productosFrecuentes: readonly string[];
};

/** Los botones de la fila, en el orden de la franja y sin los que no tienen nada adentro. */
export function intencionesDeCiudad(d: DatosIntenciones): Intencion[] {
  const { rubros, catalogo } = d;
  const base = (id: IdIntencion, titulo: string, subtitulo: string, icono: NombreIcono): Intencion =>
    ({ id, titulo, subtitulo, icono, tipo: "opciones", opciones: [], productos: [], cartel: null });

  const comerciales = catalogo.filter((r) => r.comercial !== false).map((r) => r.slug);
  // «Negocios» necesita saber qué hay en la ciudad: sin ese dato no se inventa una lista.
  const negocios = rubros === null ? [] : [...new Set(comerciales)]
    .filter((s) => !RUBROS_CON_BOTON_PROPIO.has(s) && rubros.has(s))
    .sort((a, b) => nombreDeRubro(a, catalogo).localeCompare(nombreDeRubro(b, catalogo), "es"));

  const farmacia: OpcionIntencion[] = [];
  if (d.hayTurnos) {
    farmacia.push({ t: "De turno hoy", d: "Cuáles atienden hoy", href: `/${d.ciudadSlug}/farmacias-de-turno`, i: "turno_farmacia" });
  }
  farmacia.push(...opcionesDeRubros([RUBRO_FARMACIA], rubros, catalogo));

  const todas: Record<IdIntencion, Intencion> = {
    negocios: { ...base("negocios", "Negocios", "Todos los rubros de la ciudad", "comercios"), opciones: negocios.map((s) => ({ t: nombreDeRubro(s, catalogo), href: hrefRubro(s), i: "comercios" as const, rubro: s })) },
    productos: { ...base("productos", "Productos", "Lo que se consigue en la ciudad", "encargo"), tipo: "productos", productos: [...d.productosFrecuentes] },
    servicios: { ...base("servicios", "Servicios", "Talleres, peluquerías y más", "servicios"), opciones: opcionesDeRubros(RUBROS_SERVICIOS, rubros, catalogo) },
    comer: { ...base("comer", "Comer", "Cafés, restaurantes y panaderías", "restaurantes"), opciones: opcionesDeRubros(RUBROS_COMER, rubros, catalogo) },
    dormir: { ...base("dormir", "Dormir", "Dónde quedarte", "hospedaje"), opciones: opcionesDeRubros(RUBROS_DORMIR, rubros, catalogo) },
    farmacias: { ...base("farmacias", "Farmacias", "Siempre a mano", "farmacia"), opciones: farmacia },
    bancos: { ...base("bancos", "Bancos y cajeros", "Plata a mano", "cajeros"), opciones: opcionesDeRubros(RUBROS_BANCOS, rubros, catalogo) },
  };

  const { id: resaltado, cartel } = RESALTADO[d.franja];
  // Sin saber qué rubros tiene la ciudad (falló la lectura de los pares) sólo salen los botones que ya existían como
  // accesos (Farmacias y Bancos y cajeros): los nuevos podrían abrir un mapa vacío.
  const SIN_DATO_PERMITIDOS: readonly IdIntencion[] = ["farmacias", "bancos"];
  return ORDEN[d.franja]
    .filter((id) => rubros !== null || SIN_DATO_PERMITIDOS.includes(id))
    .map((id) => todas[id])
    .filter((x) => (x.tipo === "productos" ? x.productos.length > 0 : x.opciones.length > 0))
    .map((x) => (x.id === resaltado ? { ...x, cartel } : x));
}

// ── El carrusel de comercios ────────────────────────────────────────────────

/** Lo mínimo de un comercio para la tarjeta del carrusel: es lo que viaja al navegador. */
export type ComercioCarrusel = {
  id: string;
  slug: string;
  nombre: string;
  /** La foto de la tarjeta (ver `fotoDeTarjeta`). */
  foto: string;
  /** El encuadre vertical (`object-position`) SÓLO si la foto es la miniatura: la de tarjeta y la de diseño ya vienen recortadas. */
  fotoPos: number | null;
  /** `portada_calidad` (0 a 100); `null` = la portada todavía no tiene puntaje. */
  calidad?: number | null;
  rubro: string;
  rubroNombre: string;
  horario: string | null;
  horarioEstimado: boolean;
  lat: number | null;
  lng: number | null;
  estrella: boolean;
  plan_orden: number;
};

/** Lo que se lee de `buscar_comercios` para armar candidatos y productos. */
export type ComercioDeLaCiudad = {
  id: string;
  slug: string;
  nombre: string;
  portada_thumb_url: string | null;
  portada_pos: number | null;
  /** Migración 0202: la portada recortada 4:3 y mejorada (800 px) y su puntaje. Ausentes antes de aplicarla: se cae a la miniatura. */
  portada_card_url?: string | null;
  portada_calidad?: number | null;
  /** 0200: la portada con diseño de publicidad (ya encuadrada). */
  portada_diseno_url?: string | null;
  rubro_slug: string | null;
  rubro_nombre: string | null;
  subcategoria?: string | null;
  horario: string | null;
  horario_estimado?: boolean;
  lat: number | null;
  lng: number | null;
  estrella?: boolean;
  plan_orden?: number;
  prod_obs_human: string | null;
  prod_det_ia: string | null;
};

export type ConfigCarrusel = {
  titulo: string;
  subtitulo: string;
  /** Los rubros de la franja; `null` = «los comerciales» (la de la tarde y el respaldo). */
  rubros: readonly string[] | null;
};

/** Rubros, título y bajada del carrusel según la franja (§7). */
export function configCarrusel(f: Franja, ciudad: string): ConfigCarrusel {
  switch (f) {
    case "manana": return { titulo: "Para desayunar", subtitulo: "Abiertos ahora, primero los más cerca", rubros: ["cafeteria", "panaderia"] };
    case "mediodia": return { titulo: "Para almorzar", subtitulo: "Abiertos ahora, primero los más cerca", rubros: ["restaurantes", "comida-rapida"] };
    case "tarde": return { titulo: "Abiertos ahora", subtitulo: "Comercios para recorrer esta tarde", rubros: null };
    case "noche": return { titulo: `Esta noche en ${ciudad}`, subtitulo: "Boliches, karaoke y restaurantes", rubros: ["nocturna", "restaurantes"] };
    case "madrugada": return { titulo: "Abiertas ahora", subtitulo: "Farmacias que atienden a esta hora", rubros: ["farmacia"] };
  }
}

export type CandidatosCarrusel = {
  titulo: string;
  subtitulo: string;
  items: ComercioCarrusel[];
  /** A dónde lleva «Ver todos»: el mapa con el rubro de la franja (el buscador acepta uno solo). */
  verTodos: string;
};

const MAX_CANDIDATOS = 80;

type FotoTarjeta = { url: string; recortada: boolean };

/** La foto de la tarjeta del carrusel (§11): la versión «tarjeta» (4:3, 800 px, mejorada); si no hay, la portada con
 *  diseño (ya encuadrada); y si tampoco, la miniatura de 200 px. `null` = el comercio no tiene ninguna foto.
 *  `recortada` = ya viene encuadrada: no lleva `object-position`. */
export function fotoDeTarjeta(c: Pick<ComercioDeLaCiudad, "portada_card_url" | "portada_diseno_url" | "portada_thumb_url">): FotoTarjeta | null {
  const limpia = (u: string | null | undefined): string | null => (typeof u === "string" && u.trim() ? u : null);
  const tarjeta = limpia(c.portada_card_url);
  if (tarjeta) return { url: tarjeta, recortada: true };
  const diseno = limpia(c.portada_diseno_url);
  if (diseno) return { url: diseno, recortada: true };
  const miniatura = limpia(c.portada_thumb_url);
  return miniatura ? { url: miniatura, recortada: false } : null;
}

/** Los comercios que pueden salir en el carrusel de la franja (con foto), sin decidir todavía cuáles están
 *  abiertos: eso lo hace el navegador, que conoce la hora y la ubicación. Sin ninguno de los rubros de la
 *  franja, el respaldo son los comerciales con foto y el título pasa a «Comercios de {ciudad}». */
export function candidatosCarrusel(
  comercios: readonly ComercioDeLaCiudad[], franja: Franja, ciudad: string, comerciales: ReadonlySet<string>,
  /** Los comercios de cada rubro pedidos POR RUBRO a la base (`getHomeCiudad`): en una ciudad grande los de `comercios`
   *  (una muestra) pueden no traer ninguno de los rubros de la franja. Sin esto se filtra `comercios`. */
  porRubro: Readonly<Record<string, readonly ComercioDeLaCiudad[]>> = {},
): CandidatosCarrusel {
  const cfg = configCarrusel(franja, ciudad);
  const conFoto = comercios.filter((c) => fotoDeTarjeta(c) && c.rubro_slug);
  const aItem = (c: ComercioDeLaCiudad): ComercioCarrusel => ({
    id: c.id, slug: c.slug, nombre: c.nombre, foto: fotoDeTarjeta(c)?.url ?? "",
    fotoPos: fotoDeTarjeta(c)?.recortada === false ? c.portada_pos : null,
    calidad: typeof c.portada_calidad === "number" ? c.portada_calidad : null,
    rubro: c.rubro_slug as string, rubroNombre: limpio(c.rubro_nombre ?? c.rubro_slug ?? ""),
    horario: c.horario, horarioEstimado: c.horario_estimado === true, lat: c.lat, lng: c.lng,
    estrella: c.estrella === true, plan_orden: c.plan_orden ?? 0,
  });
  const esComercial = (c: ComercioDeLaCiudad) => comerciales.has(c.rubro_slug as string);

  const deLaFranja = (rubros: readonly string[]): ComercioDeLaCiudad[] => {
    const vistos = new Set<string>();
    const lista: ComercioDeLaCiudad[] = [];
    for (const r of rubros) {
      for (const c of porRubro[r] ?? comercios) {
        if (c.rubro_slug !== r || !fotoDeTarjeta(c) || vistos.has(c.id)) continue;
        vistos.add(c.id);
        lista.push(c);
      }
    }
    return lista;
  };
  const delasFranja = cfg.rubros
    ? deLaFranja(cfg.rubros)
    : conFoto.filter((c) => esComercial(c) && !RUBROS_COMER.includes(c.rubro_slug as string));
  if (delasFranja.length > 0) {
    const primero = cfg.rubros ? cfg.rubros.find((r) => delasFranja.some((c) => c.rubro_slug === r)) : null;
    return {
      titulo: cfg.titulo, subtitulo: cfg.subtitulo, items: delasFranja.slice(0, MAX_CANDIDATOS).map(aItem),
      verTodos: primero ? hrefRubro(primero) : "/buscar?vista=mapa",
    };
  }
  const respaldo = conFoto.filter(esComercial).slice(0, MAX_CANDIDATOS).map(aItem);
  return { titulo: `Comercios de ${ciudad}`, subtitulo: "Locales para conocer", items: respaldo, verTodos: "/buscar?vista=mapa" };
}

export type TarjetaComercio = ComercioCarrusel & { metros: number | null };

export const MAX_CARRUSEL = 12;

/** El orden de los carruseles (§11): primero los abiertos (un horario que falta o no se entiende cuenta como abierto para
 *  ordenar, como en `ordenarCerca`), después el plan estrella (el más caro arriba), después `portada_calidad` de mayor a
 *  menor (sin puntaje, al final de su grupo) y, sólo con «Más cerca» prendido, la distancia. Lo demás queda como venía. */
export function ordenarCarrusel<T extends ComercioCarrusel>(
  lista: readonly T[], distancia: ((c: T) => number | null) | null, ahora: Date = ahoraEnBolivia(),
): T[] {
  const filas = lista.map((c) => ({
    c,
    cerrado: abiertoAhora(c.horario, ahora).estado === "cerrado" ? 1 : 0,
    estrella: c.estrella ? 1 : 0,
    plan: c.estrella ? c.plan_orden : 0,
    calidad: c.calidad ?? -1,
    d: distancia ? distancia(c) ?? 1e12 : 0,
  }));
  filas.sort((a, b) => a.cerrado - b.cerrado || b.estrella - a.estrella || b.plan - a.plan || b.calidad - a.calidad || a.d - b.d);
  return filas.map((f) => f.c);
}

/** Lo que se ve en el carrusel ahora: con «Abiertos» sólo los abiertos (un horario que no se entiende no es
 *  «abierto»: mandar a alguien a una puerta cerrada cuesta la confianza), en el orden de `ordenarCarrusel`. Los metros
 *  (y la distancia en el orden) sólo con «Más cerca». */
export function prepararCarrusel(
  candidatos: readonly ComercioCarrusel[],
  o: { abiertos: boolean; cerca: boolean; ubicacion: { lat: number; lng: number } | null; ahora?: Date; max?: number },
): TarjetaComercio[] {
  const ahora = o.ahora ?? ahoraEnBolivia();
  const base = o.abiertos ? candidatos.filter((c) => abiertoAhora(c.horario, ahora).estado === "abierto") : [...candidatos];
  const dist = (c: ComercioCarrusel): number | null =>
    o.ubicacion && c.lat != null && c.lng != null ? distanciaMetros(o.ubicacion.lat, o.ubicacion.lng, c.lat, c.lng) : null;
  return ordenarCarrusel(base, o.cerca ? dist : null, ahora).slice(0, o.max ?? MAX_CARRUSEL)
    .map((c) => ({ ...c, metros: o.cerca ? dist(c) : null }));
}

// ── Dax: saludo y sugerencias ───────────────────────────────────────────────

/** «¡Buen día!», «¡Hola!» o «¡Buenas noches!» según la franja. */
export function saludoDeFranja(f: Franja): string {
  if (f === "manana") return "¡Buen día!";
  if (f === "mediodia" || f === "tarde") return "¡Hola!";
  return "¡Buenas noches!";
}

/** La bienvenida de Dax: el saludo de la franja y la ciudad. */
export function bienvenidaDax(f: Franja, ciudad: string, conGuia: boolean): string {
  const presentacion = `${saludoDeFranja(f)} Soy Dax y conozco ${ciudad}.`;
  return conGuia
    ? `${presentacion} Preguntame dónde conseguir algo, si un local está abierto, a cuánto está el dólar, o cómo publicar tu negocio.`
    : `${presentacion} ${f === "noche" ? "¿Salís esta noche?" : "¿Qué necesitás?"}`;
}

const SUGERENCIAS: Record<Franja, { t: string; rubros: readonly string[] }[]> = {
  manana: [
    { t: "¿Dónde desayuno?", rubros: ["cafeteria", "panaderia"] },
    { t: "Farmacia abierta cerca", rubros: ["farmacia"] },
    { t: "¿Qué visito hoy?", rubros: [RUBRO_PARA_VISITAR] },
  ],
  mediodia: [
    { t: "¿Dónde almuerzo?", rubros: ["restaurantes", "comida-rapida"] },
    { t: "Busco zapatillas", rubros: ["calzado", "zapatillas"] },
    { t: "Cajero cerca", rubros: ["cajeros"] },
  ],
  tarde: [
    { t: "Busco zapatillas", rubros: ["calzado", "zapatillas"] },
    { t: "Necesito un servicio técnico", rubros: ["servicio-tecnico"] },
    { t: "¿Qué hago hoy?", rubros: [RUBRO_PARA_VISITAR] },
  ],
  noche: [
    { t: "Boliches abiertos esta noche", rubros: ["nocturna"] },
    { t: "¿Dónde ceno?", rubros: ["restaurantes", "comida-rapida"] },
    { t: "Hotel para esta noche", rubros: ["hospedaje"] },
  ],
  madrugada: [
    { t: "Farmacia de turno", rubros: ["farmacia"] },
    { t: "Cajero cerca", rubros: ["cajeros"] },
    { t: "¿Dónde duermo?", rubros: ["hospedaje"] },
  ],
};

/** Las sugerencias de la franja, sólo las que la ciudad puede contestar (`rubros === null`: no se sabe, salen
 *  todas). Nunca habla del paso, la aduana ni los pesos. Si quedan menos de dos, se completan con dos que
 *  valen en cualquier ciudad. */
export function sugerenciasDeFranja(f: Franja, rubros: ReadonlySet<string> | null): string[] {
  const lista = SUGERENCIAS[f].filter((s) => rubros === null || s.rubros.some((r) => rubros.has(r))).map((s) => s.t);
  if (lista.length >= 2) return lista;
  return [...lista, "¿Qué hay abierto ahora?", "¿Cómo publico mi negocio?"].slice(0, Math.max(2, lista.length + 1));
}

export const MAX_PALABRAS_CONSULTA = 4;
export const MAX_CARACTERES_CONSULTA = 60;

/** Del mensaje de la persona a una búsqueda: sin signos ni palabras de relleno («¿Dónde hay una farmacia?» →
 *  «farmacia»), hasta 4 palabras y 60 caracteres. Para el botón «Ver comercios ›» cuando el servidor no manda su
 *  propio enlace. Si no queda nada, `""` (el botón lleva a la búsqueda sin texto). */
export function consultaDeBusqueda(pregunta: string): string {
  const RELLENO = new Set([
    "donde", "dónde", "hay", "una", "un", "unos", "unas", "el", "la", "los", "las", "de", "del", "en", "para", "por",
    "que", "qué", "quiero", "busco", "necesito", "cerca", "me", "mi", "esta", "este", "como", "cómo", "puedo", "hoy",
    "abierto", "abierta", "abiertos", "abiertas", "ahora", "conseguir", "consigo", "encuentro", "comprar", "compro",
    "tenés", "tenes", "tiene", "algún", "algun", "alguna", "alguno", "es", "son", "y", "o", "a",
  ]);
  const palabras = pregunta
    .replace(/[¿?¡!.,;:()"]/g, " ").split(/\s+/).filter((p) => p && !RELLENO.has(p.toLowerCase()))
    .slice(0, MAX_PALABRAS_CONSULTA);
  // Hasta 4 palabras y 60 caracteres (en límite de palabra): lo que escribe la persona puede tener 500 y no es una búsqueda.
  let q = "";
  for (const p of palabras) {
    const siguiente = q ? `${q} ${p}` : p;
    if (siguiente.length > MAX_CARACTERES_CONSULTA) break;
    q = siguiente;
  }
  return q;
}
