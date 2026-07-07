// Cliente de la cuenta liviana del comprador/visitante: solo celular + código
// por WhatsApp, sin contraseña. Objetivo único: guardar comercios favoritos
// y dejar el celular con consentimiento para avisos/ofertas. No confundir
// con las cuentas de comercio (lib/comercio.ts).
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

export async function solicitarCodigoUsuario(whatsapp: string): Promise<void> {
  const res = await fetch(`${API}/auth/usuario/solicitar-codigo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ whatsapp }),
  });
  if (!res.ok) throw new Error("No se pudo enviar el código");
}

export async function verificarCodigoUsuario(whatsapp: string, codigo: string): Promise<UsuarioSession> {
  const res = await fetch(`${API}/auth/usuario/verificar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ whatsapp, codigo }),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "Código incorrecto");
  }
  const data = await res.json();
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(SESSION_KEY, JSON.stringify(data.usuario));
  return data.usuario as UsuarioSession;
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
