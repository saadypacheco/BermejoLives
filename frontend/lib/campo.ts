// Cliente del "modo agente de campo" (alta rápida de comercios).
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "bermejo_agente_token";

export function getAgenteToken(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);
}
export function clearAgente() {
  localStorage.removeItem(TOKEN_KEY);
}

export async function agenteLogin(email: string, password: string): Promise<void> {
  const res = await fetch(`${API}/auth/campo/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error("Credenciales incorrectas");
  const data = await res.json();
  localStorage.setItem(TOKEN_KEY, data.access_token);
}

export async function transcribirAudio(blob: Blob): Promise<string> {
  const fd = new FormData();
  fd.append("audio", blob, "qvende.webm");
  const res = await fetch(`${API}/campo/transcribir`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getAgenteToken() ?? ""}` },
    body: fd,
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "No se pudo transcribir");
  }
  return (await res.json()).texto as string;
}

export type AltaCampoResult = { ok: boolean; comercio: { nombre: string; slug: string; foto: boolean; gps: boolean } };

export async function altaComercioCampo(form: FormData): Promise<AltaCampoResult> {
  const res = await fetch(`${API}/campo/comercio`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getAgenteToken() ?? ""}` },
    body: form, // multipart; el browser pone el Content-Type con boundary
  });
  if (res.status === 401) {
    clearAgente();
    throw new Error("Sesión vencida, volvé a entrar");
  }
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "No se pudo guardar");
  }
  return res.json();
}
