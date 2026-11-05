/**
 * Cómo se instala URUKU (PWA) según el aparato y el navegador.
 *
 * El problema de fondo: en Android, Chrome le pide a Google que arme la app
 * (un WebAPK firmado, con la versión de Android al día). Samsung Internet,
 * Edge, Firefox, Brave, Opera… la arman ELLOS, con un paquete viejo, y Google
 * Play Protect avisa «se diseñó para una versión anterior de Android». No es
 * un error de URUKU, pero asusta: por eso en Android con otro navegador
 * mandamos a instalar desde Chrome.
 *
 * Todo lo de acá es PURO (sin `window`): recibe el User-Agent y lo que haga
 * falta, devuelve datos. Así se prueba con `npm test`.
 */

export type SistemaApp = "android" | "ios" | "escritorio";

export type NavegadorApp =
  | "chrome"
  | "samsung"
  | "edge"
  | "firefox"
  | "opera"
  | "brave"
  | "safari"
  | "ios-otro"
  | "webview"
  | "otro";

export interface Plataforma {
  sistema: SistemaApp;
  navegador: NavegadorApp;
}

export interface OpcionesDeteccion {
  /** `navigator.brave` existe (Brave no se distingue de Chrome por el UA). */
  brave?: boolean;
  /** `navigator.maxTouchPoints`: el iPad nuevo se presenta como Mac. */
  maxTouchPoints?: number;
}

/** Cuatro navegadores de iPhone que no son Safari (CriOS, FxiOS, EdgiOS, OPiOS). */
const IOS_NO_SAFARI = /CriOS|FxiOS|EdgiOS|OPiOS|OPT\//;

/** Navegadores incrustados en otras apps (Instagram, Facebook, TikTok…): no instalan nada. */
const WEBVIEW = /; wv\)|FBAN|FBAV|FB_IAB|Instagram|TikTok|musical_ly|Line\/|Snapchat/i;

export function detectarPlataforma(ua: string, opciones: OpcionesDeteccion = {}): Plataforma {
  const esAndroid = /Android/i.test(ua);
  const esIphone = /iPhone|iPad|iPod/i.test(ua);
  // iPadOS 13+ manda «Macintosh» y sólo se lo reconoce por la pantalla táctil.
  const esIpadComoMac = /Macintosh/i.test(ua) && (opciones.maxTouchPoints ?? 0) > 1;

  if (esIphone || esIpadComoMac) {
    return { sistema: "ios", navegador: IOS_NO_SAFARI.test(ua) ? "ios-otro" : "safari" };
  }

  const sistema: SistemaApp = esAndroid ? "android" : "escritorio";

  // El orden importa: Samsung, Edge y Opera dicen «Chrome/» en su UA.
  let navegador: NavegadorApp;
  if (esAndroid && WEBVIEW.test(ua)) navegador = "webview";
  else if (/SamsungBrowser/i.test(ua)) navegador = "samsung";
  else if (/EdgA|EdgiOS|Edg\//.test(ua)) navegador = "edge";
  else if (/OPR\/|OPT\/|Opera/.test(ua)) navegador = "opera";
  else if (/Firefox\/|FxiOS/.test(ua)) navegador = "firefox";
  else if (opciones.brave) navegador = "brave";
  else if (/Chrome\/|CriOS/.test(ua)) navegador = "chrome";
  else if (/Safari\//.test(ua)) navegador = "safari";
  else navegador = "otro";

  return { sistema, navegador };
}

/** Lo que hay que mostrar cuando alguien toca «Instalar la app». */
export type PlanInstalacion =
  /** Chrome con el aviso guardado: diálogo del sistema. */
  | "nativo"
  /** Android con otro navegador: conviene Chrome (botón + instrucción). */
  | "abrir-chrome"
  /** iPhone/iPad: Compartir → Agregar a inicio. */
  | "ios"
  /** Sin diálogo posible: instrucción del menú del navegador. */
  | "manual";

export function planInstalacion(p: Plataforma, tienePromptNativo: boolean): PlanInstalacion {
  if (p.sistema === "ios") return "ios";
  if (p.sistema === "android") {
    if (p.navegador === "chrome") return tienePromptNativo ? "nativo" : "manual";
    // El diálogo nativo de Samsung/Edge/Opera/Brave es justo el que arma el
    // paquete viejo: NO se usa aunque exista.
    return "abrir-chrome";
  }
  return tienePromptNativo ? "nativo" : "manual";
}

/**
 * Enlace `intent://` que abre la misma página en Chrome de Android. Si Chrome
 * no está instalado, Android vuelve al enlace de respaldo (la misma página).
 * Devuelve `null` si `href` no es una dirección http(s) válida.
 */
export function intentAbrirEnChrome(href: string): string | null {
  let u: URL;
  try { u = new URL(href); } catch { return null; }
  if (u.protocol !== "https:" && u.protocol !== "http:") return null;
  const esquema = u.protocol.replace(":", "");
  const ruta = `${u.host}${u.pathname}${u.search}`;
  const respaldo = encodeURIComponent(u.origin + u.pathname + u.search);
  return `intent://${ruta}#Intent;scheme=${esquema};package=com.android.chrome;S.browser_fallback_url=${respaldo};end`;
}

/** Nombre del navegador para hablarle a la persona. */
export function nombreNavegador(n: NavegadorApp): string {
  switch (n) {
    case "chrome": return "Chrome";
    case "samsung": return "Samsung Internet";
    case "edge": return "Edge";
    case "firefox": return "Firefox";
    case "opera": return "Opera";
    case "brave": return "Brave";
    case "safari": return "Safari";
    case "ios-otro": return "tu navegador";
    case "webview": return "este navegador";
    default: return "tu navegador";
  }
}

/** La instrucción a mano, en el menú de cada navegador (sin diálogo nativo). */
export function instruccionManual(p: Plataforma): string {
  if (p.sistema === "ios") {
    return "Tocá Compartir y elegí «Agregar a inicio».";
  }
  if (p.sistema === "android") {
    switch (p.navegador) {
      case "chrome": return "Tocá el menú ⋮ (arriba a la derecha) y elegí «Instalar app» o «Agregar a la pantalla principal».";
      case "samsung": return "Tocá el menú ☰ (abajo a la derecha), elegí «Agregar página a» y después «Pantalla de inicio».";
      case "edge": return "Tocá el menú ⋯ (abajo en el centro), elegí «Agregar al teléfono» o «Agregar a la pantalla de inicio».";
      case "firefox": return "Tocá el menú ⋮ (arriba a la derecha) y elegí «Instalar».";
      case "opera": return "Tocá el menú ⋮ (arriba a la derecha) y elegí «Pantalla de inicio» o «Agregar a la pantalla de inicio».";
      case "brave": return "Tocá el menú ⋮ (abajo a la derecha) y elegí «Instalar app» o «Agregar a la pantalla de inicio».";
      case "webview": return "Abrí el menú de esta pantalla (⋮), elegí «Abrir en el navegador» y desde ahí instalala.";
      default: return "Abrí el menú de tu navegador y buscá «Instalar app» o «Agregar a la pantalla de inicio».";
    }
  }
  switch (p.navegador) {
    case "chrome":
    case "brave":
    case "edge":
      return "Mirá la barra de direcciones: a la derecha hay un ícono para instalar. Si no lo ves, abrí el menú ⋮ y buscá «Instalar URUKU».";
    case "safari":
      return "En el menú Archivo elegí «Agregar al Dock».";
    case "firefox":
      return "Firefox de compu no instala aplicaciones web. Abrí URUKU en Chrome o Edge para instalarla.";
    default:
      return "Abrí el menú de tu navegador y buscá «Instalar» o «Agregar a la pantalla de inicio».";
  }
}
