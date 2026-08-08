// Cliente del panel de PUBLICADOR (contenido de la home: cotizaciones/clima/videos).
import { subirConProgreso } from "@/lib/upload";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "bermejo_publicador_token";

export const getPubToken = (): string | null =>
  typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);
export const clearPub = () => localStorage.removeItem(TOKEN_KEY);
export const hayPub = () => Boolean(getPubToken());

export async function publicadorLogin(email: string, password: string): Promise<void> {
  const res = await fetch(`${API}/auth/publicador/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error("Credenciales incorrectas");
  localStorage.setItem(TOKEN_KEY, (await res.json()).access_token);
}

async function pFetch(path: string, init?: RequestInit) {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getPubToken() ?? ""}`, ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "Error");
  }
  return res.json();
}

export const editarCotizacion = (clave: string, valor: number) =>
  pFetch(`/contenido/cotizaciones/${clave}`, { method: "PUT", body: JSON.stringify({ valor }) });
export const overrideClima = (b: { temp_c?: number; descripcion?: string; icono?: string; horas?: number }) =>
  pFetch("/contenido/clima", { method: "PUT", body: JSON.stringify(b) });
export const refrescarClima = () => pFetch("/contenido/clima/refresh", { method: "POST" });

export type VideoPromoItem = { id: string; titulo: string | null; url: string };
export const listarVideosPromo = (): Promise<VideoPromoItem[]> =>
  pFetch("/contenido/videos-promo").then((d) => d.items ?? []);
export const subirVideoPromo = (file: File, titulo: string, onP?: (p: number) => void): Promise<VideoPromoItem> =>
  subirConProgreso<{ video: VideoPromoItem }>(`${API}/contenido/videos-promo`, "video", file, getPubToken(), titulo ? { titulo } : {}, onP).then((d) => d.video);
export const borrarVideoPromo = (id: string) =>
  pFetch(`/contenido/videos-promo/${id}`, { method: "DELETE" });

export const editarRed = (clave: string, url: string) =>
  pFetch(`/contenido/redes/${clave}`, { method: "PUT", body: JSON.stringify({ url }) });
