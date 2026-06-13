// Cliente del panel del COMERCIO logueado (login + chatbot de publicación).
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "bermejo_comercio_token";
const COMERCIO_KEY = "bermejo_comercio";

export type ComercioSession = { id: string; nombre: string; slug: string; confiable: boolean };

export function getCToken(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);
}
export function getComercioSession(): ComercioSession | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(COMERCIO_KEY);
  return raw ? (JSON.parse(raw) as ComercioSession) : null;
}
export function clearComercio() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(COMERCIO_KEY);
}

export async function comercioLogin(email: string, password: string): Promise<ComercioSession> {
  const res = await fetch(`${API}/auth/comercio/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error("Credenciales incorrectas");
  const data = await res.json();
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(COMERCIO_KEY, JSON.stringify(data.comercio));
  return data.comercio as ComercioSession;
}

export type RegistroPayload = {
  nombre: string;
  email: string;
  password: string;
  whatsapp: string;
  plan: "gratis" | "pro" | "premium";
  modalidad: "mayorista" | "minorista" | "ambos";
  rubro_slug?: string;
  zona_slug?: string;
  descripcion?: string;
};

export async function comercioRegistro(payload: RegistroPayload): Promise<ComercioSession & { pago_pendiente?: boolean }> {
  const res = await fetch(`${API}/auth/comercio/registro`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? "No se pudo crear la cuenta");
  }
  const data = await res.json();
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(COMERCIO_KEY, JSON.stringify(data.comercio));
  return { ...data.comercio, pago_pendiente: data.pago_pendiente };
}

export type PublicarPayload = {
  tipo: "oferta" | "video" | "novedad";
  titulo?: string;
  descripcion?: string;
  precio?: number | null;
  moneda?: "BOB" | "USD" | "ARS";
  imagen_url?: string;
  tiktok_url?: string;
};

export type PublicarResult = { ok: boolean; estado: string; publicado_directo: boolean };

export async function publicar(payload: PublicarPayload): Promise<PublicarResult> {
  const res = await fetch(`${API}/comercio/publicar`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getCToken() ?? ""}` },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("No se pudo publicar");
  return res.json();
}
