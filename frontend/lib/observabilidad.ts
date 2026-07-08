const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// No usamos navigator.sendBeacon: por spec siempre manda credentials:'include',
// y estos endpoints son anónimos (sin CORS allow-credentials) — el navegador
// bloquea el request. fetch+keepalive cubre el mismo caso (sobrevive a la
// navegación) sin ese problema.
function enviar(url: string, body: string) {
  fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
    credentials: "omit",
  }).catch(() => {});
}

/** Nunca debe interrumpir el flujo del usuario: cualquier falla se ignora. */
export function reportarError(mensaje: string, opts?: { stack?: string; contexto?: Record<string, unknown> }) {
  try {
    enviar(`${API}/errores`, JSON.stringify({
      mensaje: mensaje.slice(0, 2000),
      stack: opts?.stack,
      ruta: typeof window !== "undefined" ? window.location.pathname : undefined,
      contexto: opts?.contexto,
    }));
  } catch {
    // no-op
  }
}

export function reportarMetrica(ruta: string, metrica: string, valorMs: number, repetida?: boolean) {
  try {
    enviar(`${API}/metricas`, JSON.stringify({ ruta, metrica, valor_ms: valorMs, repetida }));
  } catch {
    // no-op
  }
}
