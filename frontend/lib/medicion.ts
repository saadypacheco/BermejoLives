// Medición del sitio: el ÚNICO punto de entrada.
//
// Ningún componente llama a `fetch` para medir. Todo pasa por acá:
//   - `vistaDePagina(path)`   → POST /collect {t:'pv'}   (página vista)
//   - `evento(nombre, detail)` → POST /collect {t:'ev'}   (catálogo cerrado, abajo)
//   - `contacto(...)`          → POST /lead               (contactos, vistas de ficha, compartir, redes)
//   - `busqueda(...)`          → POST /busquedas/log      (devuelve el `busqueda_id`)
//   - `configurarMedicion()`   → GET  /public/measurement-config (cache de 5 min)
// Spec: docs/estadisticas-v2.md §4.3 y §4.5.
//
// SIN COOKIES, SIN IP, SIN USER-AGENT. La «sesión» es un número al azar que vive en la pestaña
// (`sessionStorage`) y se pierde al cerrarla: no identifica a nadie. Por eso no hay cartel de cookies.
//
// Reglas:
//  - Todo va en try/catch y es «fuego y olvido»: perder un número no puede costar una visita ni una venta.
//  - Las rutas internas (`/admin`, `/contenido`…) no se miden. La lista es IGUAL a `RUTAS_INTERNAS` de
//    `backend/app/services/site_metrics.py`: si cambia una, cambia la otra.
//  - Al equipo no se lo mide: con el token de admin, agente o publicador en este navegador no se manda nada.
//    Al comerciante logueado no se le cuentan vistas ni contactos de SU PROPIO comercio.
//  - Umami NO se carga en esta ronda: `GET /public/measurement-config` devuelve `umami: null` y este módulo no
//    carga ningún script de terceros. Cuando se prenda, se engancha acá (y sólo acá).
//
// Las rutas de import son relativas (no `@/`) para que los tests (`npm test`, compilados con tsc a commonjs)
// puedan cargar este archivo.
import { leadDeRespuesta, anotarContacto } from "./contestaron";
import { CIUDAD_COOKIE } from "./ciudad";
import { refGuardado } from "./ref";
import { sesionDeLaPestania } from "./sesion";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------------------------------------
// Constantes y tipos
// ---------------------------------------------------------------------------------------------------------

/** Rutas que NO se miden. Igual a `RUTAS_INTERNAS` de `backend/app/services/site_metrics.py` (comparan en
 *  minúsculas y con `startsWith`). */
export const RUTAS_INTERNAS = ["/admin", "/contenido", "/publicar", "/campo", "/mi-comercio", "/api/"] as const;

/** Lo que el backend acepta en `POST /collect` (2 KB). Se deja un margen: este tope es el de ESTE lado. */
export const MAX_BODY_BYTES = 2000;
/** Una misma vista de ficha por comercio, una vez cada 30 minutos por pestaña. */
export const VENTANA_VISTA_MS = 30 * 60 * 1000;
/** Misma ruta dos veces dentro de este tiempo = una sola página vista. */
export const VENTANA_MISMA_RUTA_MS = 1000;
/** La config pública se guarda 5 minutos en `sessionStorage`. */
export const CONFIG_VIDA_MS = 5 * 60 * 1000;

/** Tokens de quienes trabajan en el sitio: con cualquiera de estos en el navegador no se mide nada. */
export const TOKENS_DEL_EQUIPO = ["bermejo_admin_token", "bermejo_agente_token", "bermejo_publicador_token"] as const;
const TOKEN_COMERCIO = "bermejo_comercio_token";
const SESION_COMERCIO = "bermejo_comercio";

export type Dispositivo = "mobile" | "tablet" | "desktop";

/** Catálogo cerrado de eventos (§4.5). `null` = el detalle es un uuid (el id del video). */
export const CATALOGO_EVENTOS = {
  share: ["native", "copy"],
  pwa_install: ["shown", "accepted", "dismissed", "installed", "ios_hint"],
  video_play: null,
  video_network_click: ["tiktok", "instagram", "facebook", "youtube"],
  uruku_whatsapp_click: ["canal", "comunidad", "contacto"],
} as const satisfies Record<string, readonly string[] | null>;

export type NombreEvento = keyof typeof CATALOGO_EVENTOS;

/** Lo que se registra por comercio en `leads`. `compartir` y `red` llevan `detalle`. */
export type TipoLead = "whatsapp" | "telefono" | "email" | "web" | "vista" | "mapa" | "reserva" | "compartir" | "red";
export type RedDelComercio = "instagram" | "facebook" | "tiktok" | "youtube";
export type CanalDeCompartir = "native" | "copy";

export type ConfigMedicion = {
  internal: boolean;
  /** Reservado para Umami (fuera de esta ronda): se lee pero NO se usa para cargar nada. */
  umami: { script_url: string; website_id: string } | null;
};

const CONFIG_POR_DEFECTO: ConfigMedicion = { internal: true, umami: null };

/** Un almacén mínimo (sessionStorage / localStorage), para poder probar las reglas sin navegador. */
export type Almacen = Pick<Storage, "getItem" | "setItem">;

// ---------------------------------------------------------------------------------------------------------
// Piezas puras (con tests en tests/medicion.test.ts)
// ---------------------------------------------------------------------------------------------------------

/** La ruta sin query ni hash, que empieza con «/» y no pasa de 200 caracteres (el tope de las tablas). */
export function limpiarRuta(raw: string): string {
  let r = String(raw ?? "").trim();
  const corte = r.search(/[?#]/);
  if (corte >= 0) r = r.slice(0, corte);
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(r)) {
    try { r = new URL(r).pathname; } catch { r = "/"; }
  }
  if (!r.startsWith("/")) r = `/${r}`;
  return r.slice(0, 200);
}

/** ¿Es una ruta de trabajo (panel, campo, editor del comercio, API)? Esas no se miden. */
export function esRutaInterna(ruta: string): boolean {
  const r = String(ruta ?? "").toLowerCase();
  return RUTAS_INTERNAS.some((p) => r.startsWith(p));
}

/** Celular, tablet o computadora, por el user-agent (y el multitouch, para el iPad que se hace pasar por Mac). */
export function detectarDispositivo(ua: string, puntosTactiles = 0): Dispositivo {
  const u = ua || "";
  if (/ipad|tablet|playbook|silk/i.test(u) || (/android/i.test(u) && !/mobile/i.test(u)) || (/macintosh/i.test(u) && puntosTactiles > 1)) {
    return "tablet";
  }
  if (/mobi|iphone|ipod|android|windows phone/i.test(u)) return "mobile";
  return "desktop";
}

/** Sólo el HOST de donde vino (sin `www.`), o el paquete en `android-app://com.whatsapp/`. Null si es vacío,
 *  inválido o del propio sitio. La URL entera puede llevar datos de la otra página y no hace falta. */
export function hostDeReferrer(referrer: string | null | undefined, hostPropio: string): string | null {
  try {
    const r = (referrer ?? "").trim();
    if (!r) return null;
    const host = new URL(r).hostname.replace(/^www\./, "").toLowerCase();
    if (!host) return null;
    if (host === String(hostPropio ?? "").replace(/^www\./, "").toLowerCase()) return null;
    return host.slice(0, 100);
  } catch {
    return null;
  }
}

/** `?ref=` (QR impreso) o, si no está, `?utm_source=` (enlaces de redes e IA). El `ref` manda: un QR es una pista
 *  más concreta que «instagram». */
export function origenDeLaUrl(search: string): string | null {
  try {
    const q = new URLSearchParams(search);
    const v = (q.get("ref") || q.get("utm_source") || "").trim();
    return v ? v.slice(0, 64) : null;
  } catch {
    return null;
  }
}

/** La misma ruta dentro de la ventana de 1 s es UNA página vista (el buscador reescribe la URL en cada tecla y
 *  React en modo estricto monta dos veces). */
export function repiteRuta(ultima: { ruta: string; t: number } | null, ruta: string, ahora: number, ventanaMs = VENTANA_MISMA_RUTA_MS): boolean {
  return ultima !== null && ultima.ruta === ruta && ahora - ultima.t < ventanaMs;
}

const CLAVE_PRIMERA = "uk-pv-enviada";

/** ¿Es la primera página de la SESIÓN? Marca en el almacén de la pestaña y, si no hay (modo privado), en memoria.
 *  Devuelve true una sola vez por sesión. */
export function tomarPrimera(almacen: Almacen | null, estado: { v: boolean }): boolean {
  if (estado.v) return false;
  estado.v = true;
  try {
    if (almacen) {
      if (almacen.getItem(CLAVE_PRIMERA)) return false;
      almacen.setItem(CLAVE_PRIMERA, "1");
    }
  } catch { /* almacenamiento bloqueado: vale la marca en memoria */ }
  return true;
}

/** ¿Esta pestaña ya mandó la vista de ESTA ficha hace menos de 30 minutos? Si no, anota la hora. */
export function vistaRepetida(almacen: Almacen | null, comercioId: string, ahora: number, ventanaMs = VENTANA_VISTA_MS): boolean {
  if (!almacen) return false;
  const clave = `uk-vista-${comercioId}`;
  try {
    const antes = Number(almacen.getItem(clave));
    if (Number.isFinite(antes) && antes > 0 && ahora - antes < ventanaMs) return true;
    almacen.setItem(clave, String(ahora));
  } catch { /* sin almacenamiento: el backend deduplica igual */ }
  return false;
}

/** ¿Hay un token del equipo (admin, agente, publicador) en este navegador? */
export function esEquipo(almacen: Pick<Storage, "getItem"> | null): boolean {
  if (!almacen) return false;
  try { return TOKENS_DEL_EQUIPO.some((k) => !!almacen.getItem(k)); } catch { return false; }
}

/** ¿El comerciante logueado en este navegador es el dueño de ESTE comercio? Sus vistas y contactos no se cuentan. */
export function esMiComercio(almacen: Pick<Storage, "getItem"> | null, comercioId: string): boolean {
  if (!almacen) return false;
  try {
    if (!almacen.getItem(TOKEN_COMERCIO)) return false;
    const raw = almacen.getItem(SESION_COMERCIO);
    if (!raw) return false;
    const s = JSON.parse(raw) as { id?: unknown };
    return typeof s.id === "string" && s.id === comercioId;
  } catch {
    return false;
  }
}

/** ¿El evento está en el catálogo cerrado? (el backend descarta lo demás sin avisar.) */
export function eventoValido(nombre: string, detail?: string | null): boolean {
  if (!Object.prototype.hasOwnProperty.call(CATALOGO_EVENTOS, nombre)) return false;
  const permitidos = (CATALOGO_EVENTOS as Record<string, readonly string[] | null>)[nombre];
  const d = detail ?? "";
  if (permitidos === null) return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(d);
  return permitidos.includes(d);
}

function bytes(texto: string): number {
  return new TextEncoder().encode(texto).length;
}

/** El cuerpo de `/collect` en JSON, garantizado bajo el tope. Si un campo opcional lo pasara, se va soltando (lo
 *  menos importante primero) hasta que entre; la ruta se recorta como último recurso. */
export function armarCuerpo(payload: Record<string, unknown>, tope = MAX_BODY_BYTES): string {
  const p: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(payload)) if (v !== undefined && v !== null && v !== "") p[k] = v;
  let texto = JSON.stringify(p);
  for (const k of ["referrer", "ref", "city", "detail", "device"]) {
    if (bytes(texto) <= tope) break;
    delete p[k];
    texto = JSON.stringify(p);
  }
  if (bytes(texto) > tope && typeof p.path === "string") {
    p.path = p.path.slice(0, 80);
    texto = JSON.stringify(p);
  }
  return texto;
}

/** Lo que responde `POST /lead` cuando la misma sesión ya hizo ese contacto hoy: `{ok, id, token, repetido:true}`. */
export function leadRepetido(j: unknown): boolean {
  return !!j && typeof j === "object" && (j as { repetido?: unknown }).repetido === true;
}

/** Lee la config pública. Todo lo que no entienda cae al valor por defecto (medir, sin Umami). */
export function leerConfig(j: unknown): ConfigMedicion {
  if (!j || typeof j !== "object") return CONFIG_POR_DEFECTO;
  const { internal, umami } = j as { internal?: unknown; umami?: unknown };
  const u = umami && typeof umami === "object" ? (umami as { script_url?: unknown; website_id?: unknown }) : null;
  return {
    internal: internal !== false,
    umami: u && typeof u.script_url === "string" && typeof u.website_id === "string"
      ? { script_url: u.script_url, website_id: u.website_id } : null,
  };
}

/** Del elemento tocado, el evento que declara con `data-uk-evento` / `data-uk-detalle` (los enlaces de URUKU que
 *  viven en páginas de servidor). Null si no declara uno válido. */
export function eventoDeEnlace(el: { getAttribute(n: string): string | null } | null): { nombre: NombreEvento; detail: string } | null {
  if (!el) return null;
  const nombre = el.getAttribute("data-uk-evento");
  const detail = el.getAttribute("data-uk-detalle") ?? "";
  return nombre && eventoValido(nombre, detail) ? { nombre: nombre as NombreEvento, detail } : null;
}

// ---------------------------------------------------------------------------------------------------------
// Estado del navegador (sólo en el cliente)
// ---------------------------------------------------------------------------------------------------------

let config: ConfigMedicion = CONFIG_POR_DEFECTO;
let configPedida = false;
let ultimaVista: { ruta: string; t: number } | null = null;
let referrerYaMandado = false;
const primeraEnMemoria = { v: false };
const CLAVE_CONFIG = "uk-medicion-cfg";

const enNavegador = () => typeof window !== "undefined";

function almacenSesion(): Storage | null {
  try { return window.sessionStorage; } catch { return null; }
}
function almacenLocal(): Storage | null {
  try { return window.localStorage; } catch { return null; }
}

/** ¿Se puede medir ahora? No en el servidor, no al equipo, no con la config apagada. */
function puedeMedir(): boolean {
  return enNavegador() && config.internal && !esEquipo(almacenLocal());
}

function ciudadDeLaCookie(): string | null {
  try {
    const c = document.cookie.split(";").find((x) => x.trim().startsWith(`${CIUDAD_COOKIE}=`));
    const v = c ? decodeURIComponent(c.split("=")[1] ?? "") : "";
    return /^[a-z0-9-]{1,40}$/i.test(v) ? v : null;
  } catch {
    return null;
  }
}

function estaInstalada(): boolean {
  try {
    if (window.matchMedia("(display-mode: standalone)").matches) return true;
  } catch { /* sin matchMedia */ }
  return (window.navigator as Navigator & { standalone?: boolean }).standalone === true;
}

/** Lo común a toda página vista y todo evento. */
function contexto() {
  const nav = window.navigator;
  return {
    session: sesionDeLaPestania().id,
    device: detectarDispositivo(nav.userAgent, nav.maxTouchPoints),
    standalone: estaInstalada(),
    city: ciudadDeLaCookie() ?? undefined,
  };
}

/** `fetch` con `keepalive`, `text/plain` (no dispara el preflight de CORS) y SIN credenciales. Va primero
 *  porque `sendBeacon` siempre manda credenciales y el backend no las acepta (no usa cookies): el dato llegaba
 *  igual, pero el navegador anotaba un error de CORS en la consola en cada página. `sendBeacon` queda de
 *  respaldo para navegadores sin `keepalive`. */
function mandarCollect(payload: Record<string, unknown>): void {
  const cuerpo = armarCuerpo(payload);
  const url = `${API}/collect`;
  try {
    if (typeof fetch === "function") {
      fetch(url, {
        method: "POST", headers: { "Content-Type": "text/plain;charset=UTF-8" },
        body: cuerpo, keepalive: true, credentials: "omit",
      }).catch(() => { /* perder un número no puede costar una visita */ });
      return;
    }
  } catch { /* cae al beacon */ }
  try {
    if (typeof navigator.sendBeacon === "function") {
      navigator.sendBeacon(url, new Blob([cuerpo], { type: "text/plain;charset=UTF-8" }));
    }
  } catch { /* nada */ }
}

// ---------------------------------------------------------------------------------------------------------
// API pública
// ---------------------------------------------------------------------------------------------------------

/** Lee `/public/measurement-config` (cache de 5 min en `sessionStorage`). No bloquea nada: mientras no llega, se
 *  mide con la config por defecto. Se pide una sola vez por carga, aunque falle (nada de reintentos en cada render). */
export function configurarMedicion(): void {
  if (!enNavegador() || configPedida) return;
  configPedida = true;
  try {
    const guardada = almacenSesion()?.getItem(CLAVE_CONFIG);
    if (guardada) {
      const g = JSON.parse(guardada) as { t?: number; cfg?: unknown };
      if (typeof g.t === "number" && Date.now() - g.t < CONFIG_VIDA_MS) { config = leerConfig(g.cfg); return; }
    }
  } catch { /* cache ilegible: se vuelve a pedir */ }
  try {
    fetch(`${API}/public/measurement-config`, { credentials: "omit" })
      .then((r) => (r.ok ? r.json() : null))
      .then((j: unknown) => {
        if (j === null) return;
        config = leerConfig(j);
        try { almacenSesion()?.setItem(CLAVE_CONFIG, JSON.stringify({ t: Date.now(), cfg: j })); } catch { /* sin cache */ }
      })
      .catch(() => { /* sigue la config por defecto */ });
  } catch { /* nada */ }
}

/** Una página vista. `path` puede traer query o hash: se limpian. */
export function vistaDePagina(path: string): void {
  try {
    if (!puedeMedir()) return;
    const ruta = limpiarRuta(path);
    if (esRutaInterna(ruta)) return;
    const ahora = Date.now();
    if (repiteRuta(ultimaVista, ruta, ahora)) return;
    ultimaVista = { ruta, t: ahora };

    const first = tomarPrimera(almacenSesion(), primeraEnMemoria);
    // El referrer va sólo en la primera página de la CARGA: en las siguientes es la propia página anterior.
    let referrer: string | null = null;
    if (!referrerYaMandado) {
      referrerYaMandado = true;
      referrer = hostDeReferrer(document.referrer, window.location.hostname);
    }
    mandarCollect({
      t: "pv", path: ruta, ...contexto(), first,
      ref: origenDeLaUrl(window.location.search) ?? undefined,
      referrer: referrer ?? undefined,
    });
  } catch { /* medir no puede romper la página */ }
}

/** Un evento del catálogo cerrado (§4.5). Lo que no esté en el catálogo se ignora. */
export function evento(nombre: NombreEvento, detail?: string): void {
  try {
    if (!puedeMedir() || !eventoValido(nombre, detail)) return;
    const ruta = limpiarRuta(window.location.pathname);
    if (esRutaInterna(ruta)) return;
    mandarCollect({ t: "ev", path: ruta, ...contexto(), event: nombre, detail });
  } catch { /* nada */ }
}

/** Un contacto (o vista, o compartir, o toque a una red) con un comercio. Devuelve el `id` que dio el servidor
 *  (null si no hay: vistas, compartir, redes, descartado o sin conexión). Nunca falla hacia arriba ni bloquea.
 *
 *  - `origen`: el `?ref=` con el que llegó. Si quien llama no lo pasa se toma el guardado: así los botones de
 *    WhatsApp, mapa y reserva atribuyen el contacto sin repetirlo en cada uno.
 *  - `busquedaId`: ata el contacto a la búsqueda que lo produjo.
 *  - `nombre`: el del local, para el «¿te contestó Rústico?» de después.
 *  - `detalle`: la red (`instagram`…) en `red`, o `native`/`copy` en `compartir`. */
export async function contacto(
  comercioId: string,
  tipo: TipoLead = "whatsapp",
  opts: { busquedaId?: string | null; origen?: string | null; nombre?: string | null; detalle?: string | null } = {},
): Promise<string | null> {
  try {
    if (!puedeMedir() || !comercioId) return null;
    if (esRutaInterna(limpiarRuta(window.location.pathname))) return null;
    if (esMiComercio(almacenLocal(), comercioId)) return null;
    if (tipo === "vista" && vistaRepetida(almacenSesion(), comercioId, Date.now())) return null;

    const sesion = sesionDeLaPestania().id;
    const body: Record<string, string> = { comercio_id: comercioId, tipo, sesion };
    if (opts.busquedaId) body.busqueda_id = opts.busquedaId;
    const origen = opts.origen || refGuardado();
    if (origen) body.origen = origen;
    if (opts.detalle) body.detalle = opts.detalle.slice(0, 20);

    const r = await fetch(`${API}/lead`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body), keepalive: true, credentials: "omit",
    });
    const j: unknown = await r.json().catch(() => null);
    const lead = leadDeRespuesta(j);
    if (!lead) return null;
    // Un contacto de WhatsApp o teléfono queda anotado para preguntar después «¿te contestó?». Si el servidor dice
    // `repetido` (la misma sesión ya lo hizo hoy) NO se vuelve a anotar: es el mismo id, y se pregunta una sola vez.
    if ((tipo === "whatsapp" || tipo === "telefono") && !leadRepetido(j)) {
      anotarContacto(lead.id, comercioId, opts.nombre || "el local", lead.token, sesion);
    }
    return lead.id;
  } catch {
    return null;
  }
}

/** Registra una búsqueda y devuelve su id, para poder atarle el contacto que venga después. El servidor enmascara
 *  teléfonos y mails antes de guardar. Nunca falla hacia arriba: si el registro se cae, la persona igual busca. */
export async function busqueda(query: string, resultados: number, comercios?: string[]): Promise<string | null> {
  // Tres, no dos: con dos entraban «re» y «om» (prefijos de «restaurante» y «comida») y se leían como demanda.
  const q = (query ?? "").trim();
  if (q.length < 3) return null;
  try {
    if (!puedeMedir()) return null;
    const res = await fetch(`${API}/busquedas/log`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: q.slice(0, 100), resultados, comercios: comercios?.slice(0, 10) }),
      keepalive: true, credentials: "omit",
    });
    if (!res.ok) return null;
    const j = (await res.json().catch(() => null)) as { busqueda_id?: unknown } | null;
    return typeof j?.busqueda_id === "string" ? j.busqueda_id : null;
  } catch {
    return null;
  }
}
