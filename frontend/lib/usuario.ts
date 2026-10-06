// Cliente de la cuenta liviana del comprador/visitante: celular + clave de 6
// números. La primera vez (y si la olvidó) confirma con su WhatsApp, y ahí se le
// muestra la clave. Objetivo único: guardar comercios favoritos
// y dejar el celular con consentimiento para avisos/ofertas. No confundir
// con las cuentas de comercio (lib/comercio.ts).
import { detalleDeError } from "@/lib/acceso";
import { refGuardado } from "@/lib/ref";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "bermejo_usuario_token";
const SESSION_KEY = "bermejo_usuario";

export type UsuarioSession = { id: string; whatsapp: string };

export function getUsuarioToken(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);
}
export function getUsuarioSession(): UsuarioSession | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(SESSION_KEY);
  return raw ? (JSON.parse(raw) as UsuarioSession) : null;
}
export function clearUsuario() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(SESSION_KEY);
}

/** `whatsapp` es el número ya normalizado por el backend (E.164 sin «+»): es el
 *  que hay que usar para verificar, no el que tipeó la persona. */
export type SolicitudCodigo = { codigo: string; wa_link: string; whatsapp: string };

/** Ya no manda nada por WhatsApp — devuelve el código y el link wa.me para
 * que el usuario mande "CONFIRMAR-XXXXXX" él mismo (login por mensaje
 * entrante, sin riesgo de ban por envío saliente automatizado). */
export async function solicitarCodigoUsuario(whatsapp: string): Promise<SolicitudCodigo> {
  const ref = refGuardado();   // vence a los 30 días (lib/ref.ts)
  const res = await fetch(`${API}/auth/usuario/solicitar-codigo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    // `consentimiento` va siempre en false: sólo cuenta con un tilde explícito
    // y todavía no hay pantalla que lo pida.
    body: JSON.stringify({ whatsapp, ref: ref || undefined, consentimiento: false }),
  });
  if (!res.ok) {
    // 400 = número inválido: el backend dice por qué y se muestra tal cual.
    const d = await res.json().catch(() => ({}));
    throw new Error(typeof d.detail === "string" && d.detail ? d.detail : "No se pudo generar el código");
  }
  const data = await res.json();
  return { codigo: data.codigo, wa_link: data.wa_link, whatsapp: typeof data.whatsapp === "string" && data.whatsapp ? data.whatsapp : whatsapp };
}

/** Lo que devuelve confirmar por WhatsApp: la sesión y, si es su primera vez (o
 *  se le generó una), la clave. Es la ÚNICA vez que se ve. */
export type EntradaUsuario = { usuario: UsuarioSession; claveNueva: string | null };

function guardarSesion(data: { access_token: string; usuario: UsuarioSession; clave_nueva?: unknown }): EntradaUsuario {
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(SESSION_KEY, JSON.stringify(data.usuario));
  const clave = typeof data.clave_nueva === "string" && data.clave_nueva ? data.clave_nueva : null;
  return { usuario: data.usuario, claveNueva: clave };
}

/** Puede devolver null (todavía no se confirmó por WhatsApp) en vez de
 * tirar excepción — pensado para pollear sin llenar la consola de errores. */
export async function verificarCodigoUsuario(whatsapp: string, codigo: string): Promise<EntradaUsuario | null> {
  const res = await fetch(`${API}/auth/usuario/verificar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ whatsapp, codigo }),
  });
  if (!res.ok) return null;
  return guardarSesion(await res.json());
}

/** Entra con celular + clave de 6 números. 401 («Celular o clave incorrectos»)
 *  y 429 («Demasiados intentos…») traen su motivo en `detail`: se muestra tal cual. */
export async function ingresarUsuario(whatsapp: string, clave: string): Promise<UsuarioSession> {
  const res = await fetch(`${API}/auth/usuario/ingresar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ whatsapp, clave }),
  });
  if (!res.ok) throw new Error(await detalleDeError(res, "No se pudo entrar. Probá de nuevo."));
  return guardarSesion(await res.json()).usuario;
}

async function uFetch(path: string, init?: RequestInit) {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getUsuarioToken() ?? ""}`,
      ...(init?.headers ?? {}),
    },
  });
  if (res.status === 401) {
    clearUsuario();
    throw new Error("Tu sesión venció, volvé a entrar");
  }
  if (!res.ok) throw new Error("Error en la solicitud");
  return res.json();
}

export type FavoritoComercio = {
  id: string; slug: string; nombre: string; logo_url: string | null; portada_url: string | null;
  direccion: string | null; rating: number; whatsapp: string; verificado: boolean;
};

export const listarFavoritos = (): Promise<FavoritoComercio[]> =>
  uFetch("/usuario/favoritos").then((d) => d.items as FavoritoComercio[]);

export const agregarFavorito = (comercioId: string): Promise<void> =>
  uFetch("/usuario/favoritos", { method: "POST", body: JSON.stringify({ comercio_id: comercioId }) });

export const quitarFavorito = (comercioId: string): Promise<void> =>
  uFetch(`/usuario/favoritos/${comercioId}`, { method: "DELETE" });
