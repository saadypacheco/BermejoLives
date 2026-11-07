// Textos en castellano claro de la medición: de dónde llegan, qué hicieron, hace cuánto llegó el último dato.
// Lógica pura (con tests en tests/origenes.test.ts): la usan el panel del admin (`panel-visitas`) y las
// estadísticas del comerciante (`app/mi-comercio`). Sin imports: se compila para los tests tal cual.

export type TipoOrigen = "search" | "social" | "whatsapp" | "ai" | "direct" | "other";
/** `qr` sólo lo manda «Mi comercio» (el backend separa el QR); el panel del admin lo recibe como `other`/`qr_<clase>`. */
export type Origen = { kind: TipoOrigen | "qr"; name: string; n: number };

/** Nombres propios que no salen de poner la primera letra en mayúscula. */
const NOMBRES: Record<string, string> = {
  google: "Google", bing: "Bing", duckduckgo: "DuckDuckGo", yahoo: "Yahoo", ecosia: "Ecosia", brave: "Brave", yandex: "Yandex",
  facebook: "Facebook", instagram: "Instagram", tiktok: "TikTok", youtube: "YouTube", x: "X", linkedin: "LinkedIn",
  telegram: "Telegram", messenger: "Messenger", threads: "Threads", reddit: "Reddit", pinterest: "Pinterest",
  whatsapp: "WhatsApp", gmail: "Gmail",
  chatgpt: "ChatGPT", perplexity: "Perplexity", gemini: "Gemini", copilot: "Copilot", claude: "Claude",
  meta_ai: "Meta AI", deepseek: "DeepSeek", grok: "Grok", mistral: "Mistral",
};

/** Lo que dice cada clase de `?ref=` de los QR impresos. */
const QR: Record<string, string> = {
  volante: "QR del volante", mesa: "QR de la mesa", ficha: "QR de tu ficha", tarjeta: "QR de la tarjeta",
  vidriera: "QR de la vidriera", vitrina: "QR de la vidriera", cartel: "QR del cartel", afiche: "QR del afiche",
};

export function nombreCanonico(name: string): string {
  const n = (name || "").trim();
  if (!n) return "";
  return NOMBRES[n.toLowerCase()] ?? (n.length <= 30 && !n.includes(".") ? n.charAt(0).toUpperCase() + n.slice(1) : n);
}

function etiquetaQr(clase: string): string {
  const c = (clase || "").trim().toLowerCase();
  return QR[c] ?? (c ? `QR «${c}»` : "QR");
}

/** «De dónde llegaron» para el COMERCIANTE: «QR del volante», «Google», «Facebook», «WhatsApp», «Directo»… */
export function etiquetaOrigenComercio(o: { kind: string; name: string }): string {
  switch (o.kind) {
    case "qr": return etiquetaQr(o.name);
    case "direct": return "Directo (escribieron la dirección o abrieron un enlace)";
    case "ai": return `${nombreCanonico(o.name) || "Asistente"} (asistente de IA)`;
    case "other": return o.name.startsWith("qr_") ? etiquetaQr(o.name.slice(3)) : (nombreCanonico(o.name) || "Otros");
    default: return nombreCanonico(o.name) || "Otros";
  }
}

/** Lo mismo para el ADMIN: dentro de su grupo, el detalle (`qr_volante` → «QR: volante»). */
export function etiquetaOrigenPanel(o: { kind: string; name: string }): string {
  if (o.kind === "direct") return "Directo";
  if (o.name.startsWith("qr_")) return `QR: ${o.name.slice(3)}`;
  return nombreCanonico(o.name) || "Otros";
}

/** Cómo se llama cada grupo en el panel. */
export const NOMBRE_TIPO_ORIGEN: Record<TipoOrigen, string> = {
  search: "Google y buscadores", social: "Redes sociales", whatsapp: "WhatsApp",
  ai: "Asistentes de IA", direct: "Directo", other: "Otros (incluye QR)",
};
const ORDEN_TIPOS: TipoOrigen[] = ["search", "social", "whatsapp", "ai", "direct", "other"];

export type GrupoOrigen = { kind: TipoOrigen; n: number; items: { nombre: string; n: number }[] };

/** Junta los orígenes por tipo, del grupo más grande al más chico. Los grupos vacíos no salen. */
export function agruparOrigenes(items: { kind: string; name: string; n: number }[]): GrupoOrigen[] {
  const por = new Map<TipoOrigen, GrupoOrigen>();
  for (const it of items) {
    const kind = (ORDEN_TIPOS as string[]).includes(it.kind) ? (it.kind as TipoOrigen) : "other";
    const g = por.get(kind) ?? { kind, n: 0, items: [] };
    g.n += it.n;
    g.items.push({ nombre: etiquetaOrigenPanel({ kind, name: it.name }), n: it.n });
    por.set(kind, g);
  }
  const grupos = [...por.values()].filter((g) => g.n > 0);
  for (const g of grupos) g.items.sort((a, b) => b.n - a.n);
  return grupos.sort((a, b) => b.n - a.n || ORDEN_TIPOS.indexOf(a.kind) - ORDEN_TIPOS.indexOf(b.kind));
}

// ---- Qué hicieron (eventos) ---------------------------------------------------------------------

export type EventoContado = { event: string; detail: string; n: number };

export type ResumenEventos = {
  compartieron: { total: number; nativo: number; copiado: number };
  instalacion: { mostrada: number; aceptada: number; rechazada: number; instalada: number; pistaIphone: number };
  videos: { reproducidos: number; distintos: number; aRedes: { red: string; n: number }[] };
  canal: { canal: number; comunidad: number; contacto: number };
  /** Hubo al menos un evento de alguna clase. */
  hayAlgo: boolean;
};

/** Suma el catálogo cerrado de eventos en lo que se muestra en el panel. */
export function resumirEventos(eventos: EventoContado[] | undefined): ResumenEventos {
  const r: ResumenEventos = {
    compartieron: { total: 0, nativo: 0, copiado: 0 },
    instalacion: { mostrada: 0, aceptada: 0, rechazada: 0, instalada: 0, pistaIphone: 0 },
    videos: { reproducidos: 0, distintos: 0, aRedes: [] },
    canal: { canal: 0, comunidad: 0, contacto: 0 },
    hayAlgo: false,
  };
  const redes = new Map<string, number>();
  for (const e of eventos ?? []) {
    const n = Number.isFinite(e.n) ? e.n : 0;
    if (n <= 0) continue;
    r.hayAlgo = true;
    switch (e.event) {
      case "share":
        r.compartieron.total += n;
        if (e.detail === "native") r.compartieron.nativo += n; else if (e.detail === "copy") r.compartieron.copiado += n;
        break;
      case "pwa_install":
        if (e.detail === "shown") r.instalacion.mostrada += n;
        else if (e.detail === "accepted") r.instalacion.aceptada += n;
        else if (e.detail === "dismissed") r.instalacion.rechazada += n;
        else if (e.detail === "installed") r.instalacion.instalada += n;
        else if (e.detail === "ios_hint") r.instalacion.pistaIphone += n;
        break;
      case "video_play":
        r.videos.reproducidos += n;
        r.videos.distintos += 1;       // el detalle es el id del video: una fila por video
        break;
      case "video_network_click":
        redes.set(e.detail, (redes.get(e.detail) ?? 0) + n);
        break;
      case "uruku_whatsapp_click":
        if (e.detail === "canal") r.canal.canal += n;
        else if (e.detail === "comunidad") r.canal.comunidad += n;
        else if (e.detail === "contacto") r.canal.contacto += n;
        break;
      default:
        break;
    }
  }
  r.videos.aRedes = [...redes.entries()].map(([red, n]) => ({ red: nombreCanonico(red), n })).sort((a, b) => b.n - a.n);
  return r;
}

// ---- Dispositivos y «hace cuánto» ------------------------------------------------------------------

export const NOMBRE_DISPOSITIVO: Record<string, string> = { mobile: "Celular", tablet: "Tablet", desktop: "Computadora" };

/** Porcentaje entero de `n` sobre `total` (0 si no hay total). */
export function porcentaje(n: number, total: number): number {
  return total > 0 ? Math.round((n / total) * 100) : 0;
}

/** «Último dato recibido hace X»: minutos, horas o días. `nivel` avisa si la medición parece caída. */
export function haceCuanto(iso: string | null | undefined, ahora: number = Date.now()): { texto: string; nivel: "ok" | "atento" | "caida" | "sin_datos" } {
  if (!iso) return { texto: "Todavía no llegó ningún dato.", nivel: "sin_datos" };
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return { texto: "No se pudo leer cuándo llegó el último dato.", nivel: "sin_datos" };
  const min = Math.max(0, Math.round((ahora - t) / 60000));
  if (min < 1) return { texto: "Último dato recibido hace menos de 1 minuto.", nivel: "ok" };
  if (min < 60) return { texto: `Último dato recibido hace ${min} min.`, nivel: min > 30 ? "atento" : "ok" };
  const h = Math.floor(min / 60);
  if (h < 24) return { texto: `Último dato recibido hace ${h} h.`, nivel: h >= 6 ? "caida" : "atento" };
  const d = Math.floor(h / 24);
  return { texto: `Último dato recibido hace ${d} ${d === 1 ? "día" : "días"}.`, nivel: "caida" };
}

/** Sólo una dirección https (el botón «Abrir Umami» no puede llevar a un `javascript:`). */
export function urlSegura(u: unknown): string | null {
  if (typeof u !== "string") return null;
  try {
    const x = new URL(u);
    return x.protocol === "https:" ? x.toString() : null;
  } catch {
    return null;
  }
}
