// Fotos con estilo URUKU (docs/fotos-estilo-uruku.md §5-§7): los tipos del contrato y la lógica pura de la
// ventana «Fotos» de Admin › Comercios. Sin red ni navegador: lo que llega del servidor se lee acá con
// tolerancia (un campo que falta no rompe la ventana) y lo que se muestra se decide acá, para poder probarlo.

export type Method = "free" | "gemini" | "external";

/** Lo que devuelven las rutas de portada (`/portada-diseno…`). */
export type CoverDesign = {
  portada_diseno_url: string | null;
  portada_diseno_propuesta_url: string | null;
  proposal_method: Method | null;
};

/** Una foto de la galería (`GET .../fotos-estilo` y las rutas `.../fotos/{id}/diseno…`). */
export type GalleryItem = {
  foto_id: string;
  photo_url: string;
  thumb_url: string | null;
  design_url: string | null;
  design_thumb_url: string | null;
  proposal_url: string | null;
  proposal_method: Method | null;
};

export type GeminiState = {
  available: boolean;
  /** En español, para mostrar tal cual. */
  reason: string | null;
  /** Estimado por imagen. */
  cost_usd: number;
  used_today: number;
  /** El tope diario de llamadas a la IA. `null` = el servidor no lo informó (no es un 0: un 0 SÍ bloquea la IA). */
  daily_cap: number | null;
  merchant_uses: number;
  merchant_cost_usd: number;
};

export type CoverState = {
  photo_url: string | null;
  design_url: string | null;
  proposal_url: string | null;
  proposal_method: Method | null;
};

export type PhotoStyleState = {
  comercio: { id: string; nombre: string; slug: string };
  cover: CoverState;
  gallery: GalleryItem[];
  gemini: GeminiState;
  instructions: { version: string; cover: string; gallery: string };
};

/** A qué foto se le arma el estilo: la portada o una de la galería. */
export type Objetivo = { tipo: "cover" } | { tipo: "foto"; id: string };

/** Lo que contesta una acción, según el objetivo (la portada y la galería devuelven formas distintas). */
export type Resultado =
  | { tipo: "cover"; data: CoverDesign }
  | { tipo: "foto"; data: GalleryItem };

// ---------------------------------------------------------------------------------------------
// Lectura tolerante del JSON del servidor
// ---------------------------------------------------------------------------------------------

type Json = Record<string, unknown>;

function obj(v: unknown): Json {
  return v !== null && typeof v === "object" && !Array.isArray(v) ? (v as Json) : {};
}
function txt(v: unknown): string | null {
  return typeof v === "string" && v.trim() ? v : null;
}
function num(v: unknown): number {
  return typeof v === "number" && Number.isFinite(v) ? v : 0;
}
function metodo(v: unknown): Method | null {
  return v === "free" || v === "gemini" || v === "external" ? v : null;
}

export function leerCoverDesign(raw: unknown): CoverDesign {
  const d = obj(raw);
  return {
    portada_diseno_url: txt(d.portada_diseno_url),
    portada_diseno_propuesta_url: txt(d.portada_diseno_propuesta_url),
    proposal_method: metodo(d.proposal_method),
  };
}

export function leerGalleryItem(raw: unknown): GalleryItem {
  const d = obj(raw);
  return {
    foto_id: typeof d.foto_id === "string" ? d.foto_id : "",
    photo_url: typeof d.photo_url === "string" ? d.photo_url : "",
    thumb_url: txt(d.thumb_url),
    design_url: txt(d.design_url),
    design_thumb_url: txt(d.design_thumb_url),
    proposal_url: txt(d.proposal_url),
    proposal_method: metodo(d.proposal_method),
  };
}

export function leerEstado(raw: unknown): PhotoStyleState {
  const d = obj(raw);
  const co = obj(d.comercio);
  const cv = obj(d.cover);
  const g = obj(d.gemini);
  const ins = obj(d.instructions);
  return {
    comercio: { id: String(co.id ?? ""), nombre: String(co.nombre ?? ""), slug: String(co.slug ?? "") },
    cover: {
      photo_url: txt(cv.photo_url), design_url: txt(cv.design_url),
      proposal_url: txt(cv.proposal_url), proposal_method: metodo(cv.proposal_method),
    },
    gallery: (Array.isArray(d.gallery) ? d.gallery : []).map(leerGalleryItem).filter((f) => f.foto_id !== ""),
    gemini: {
      available: g.available === true,
      reason: txt(g.reason),
      cost_usd: num(g.cost_usd),
      used_today: num(g.used_today),
      daily_cap: typeof g.daily_cap === "number" && Number.isFinite(g.daily_cap) ? g.daily_cap : null,
      merchant_uses: num(g.merchant_uses),
      merchant_cost_usd: num(g.merchant_cost_usd),
    },
    instructions: {
      version: String(ins.version ?? ""), cover: String(ins.cover ?? ""), gallery: String(ins.gallery ?? ""),
    },
  };
}

/** Pone al día el estado con lo que contestó una acción (sin tocar lo demás). */
export function aplicarResultado(estado: PhotoStyleState, objetivo: Objetivo, r: Resultado): PhotoStyleState {
  if (objetivo.tipo === "cover" && r.tipo === "cover") {
    return {
      ...estado,
      cover: {
        ...estado.cover,
        design_url: r.data.portada_diseno_url,
        proposal_url: r.data.portada_diseno_propuesta_url,
        proposal_method: r.data.proposal_method,
      },
    };
  }
  if (objetivo.tipo === "foto" && r.tipo === "foto") {
    // Si el servidor no repitió el id, se usa el del objetivo: la fila es la que se tocó.
    const item = { ...r.data, foto_id: r.data.foto_id || objetivo.id };
    return { ...estado, gallery: estado.gallery.map((f) => (f.foto_id === objetivo.id ? item : f)) };
  }
  return estado;
}

// ---------------------------------------------------------------------------------------------
// Textos y decisiones de la ventana
// ---------------------------------------------------------------------------------------------

/**
 * `textoCosto(0.0336) → "≈ US$ 0,034"`. Tres decimales (son centavos de dólar), con coma, y sin el cero de
 * sobra: 0,07 y no 0,070; nunca menos de dos decimales (0,00).
 */
export function textoCosto(usd: number): string {
  const v = Number.isFinite(usd) && usd > 0 ? usd : 0;
  let s = v.toFixed(3);
  if (s.endsWith("0")) s = s.slice(0, -1);
  return `≈ US$ ${s.replace(".", ",")}`;
}

export type ClaveEstado = "propuesta" | "con_diseno" | "original";

/**
 * En qué está una foto: con una propuesta esperando decisión (lo que hay que atender), con el diseño ya en la
 * ficha, o sólo la original. El texto va siempre junto al ícono: el estado no se dice sólo con color.
 */
export function estadoFoto(f: { design_url?: string | null; proposal_url?: string | null }):
  { clave: ClaveEstado; texto: string } {
  if (f.proposal_url) return { clave: "propuesta", texto: "Propuesta lista" };
  if (f.design_url) return { clave: "con_diseno", texto: "Con diseño" };
  return { clave: "original", texto: "Original" };
}

/** La revisión humana que pide la spec (§2) antes de usar una imagen que no armó la plantilla sola. */
export const AVISO_REVISION = "Revisá que la imagen no traiga texto, precios ni cambios en los productos o el letrero antes de usarla.";

/**
 * El aviso que lleva una propuesta según cómo se hizo: `gemini` y `external` (la IA tocó la foto) piden
 * revisar; la `free` (la plantilla) y una sin método no avisan nada.
 */
export function avisoPropuesta(method: Method | null | undefined): string | null {
  if (method === "gemini") return `Hecha con IA. ${AVISO_REVISION}`;
  if (method === "external") return `Hecha afuera (ChatGPT u otra herramienta). ${AVISO_REVISION}`;
  return null;
}

/**
 * ¿Se puede usar «Con IA»? Si no, `motivo` dice por qué, en español, para mostrarlo: interruptor apagado, sin
 * modelo o sin costo (lo explica el servidor en `reason`) o tope del día alcanzado. El camino gratis y el de
 * ChatGPT a mano no dependen de esto.
 */
export function puedeIA(g: GeminiState): { puede: boolean; motivo: string | null } {
  if (!g.available) return { puede: false, motivo: g.reason ?? "Fotos con IA no está disponible por ahora." };
  // Un tope en 0 es una decisión (el backend lo trae como «no disponible», pero igual no se ofrece el botón); un dato que
  // FALTA (undefined/null/no numérico) no es un 0: ahí no se sabe el tope y se deja al servidor contestar.
  if (g.daily_cap === 0) {
    return { puede: false, motivo: "El tope diario de fotos con IA está en 0. Mientras tanto andan Gratis y ChatGPT." };
  }
  if (g.daily_cap !== null && g.daily_cap > 0 && g.used_today >= g.daily_cap) {
    return { puede: false, motivo: `Se llegó al tope de ${g.daily_cap} fotos con IA por hoy. Mañana se renueva; mientras tanto andan Gratis y ChatGPT.` };
  }
  return { puede: true, motivo: null };
}

/** «≈ US$ 0,034 por foto · hoy 3 de 20 · este negocio: 2 (≈ US$ 0,067)». */
export function resumenIA(g: GeminiState): string {
  const partes: string[] = [];
  if (g.cost_usd > 0) partes.push(`${textoCosto(g.cost_usd)} por foto`);
  if (g.daily_cap !== null && g.daily_cap > 0) partes.push(`hoy ${g.used_today} de ${g.daily_cap}`);
  partes.push(`este negocio: ${g.merchant_uses}${g.merchant_uses > 0 ? ` (${textoCosto(g.merchant_cost_usd)})` : ""}`);
  return partes.join(" · ");
}

/** La etiqueta del botón «Con IA»: con el costo estimado si se conoce. */
export function etiquetaConIA(g: GeminiState, confirmando: boolean): string {
  const costo = g.cost_usd > 0 ? ` ${textoCosto(g.cost_usd)}` : "";
  return confirmando ? `Confirmar${costo}` : `Con IA${costo}`;
}

/** Topes de la imagen que se sube (§8 «Externa»): 15 MB y JPEG/PNG/WEBP. El servidor igual valida de nuevo. */
export const MAX_BYTES_EXTERNA = 15 * 1024 * 1024;
export const TIPOS_EXTERNA = ["image/jpeg", "image/png", "image/webp"] as const;

/** `null` si el archivo sirve; si no, el motivo en español. */
export function problemaArchivoExterno(a: { type: string; size: number }): string | null {
  if (!(TIPOS_EXTERNA as readonly string[]).includes(a.type)) return "La imagen tiene que ser JPG, PNG o WEBP.";
  if (a.size <= 0) return "El archivo está vacío.";
  if (a.size > MAX_BYTES_EXTERNA) return "La imagen pesa más de 15 MB. Achicala y probá de nuevo.";
  return null;
}

/** Nombre del archivo al «Descargar la foto»: `<slug>-portada.jpg` / `<slug>-foto-<n>.jpg`, sólo caracteres seguros. */
export function nombreDescarga(slug: string, objetivo: Objetivo, n?: number): string {
  const base = (slug || "negocio").toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "") || "negocio";
  return objetivo.tipo === "cover" ? `${base}-portada.jpg` : `${base}-foto-${n ?? 1}.jpg`;
}
