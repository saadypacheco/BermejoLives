const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Nunca debe interrumpir el flujo del usuario: cualquier falla se ignora. */
export function reportarError(mensaje: string, opts?: { stack?: string; contexto?: Record<string, unknown> }) {
  try {
    const body = JSON.stringify({
      mensaje: mensaje.slice(0, 2000),
      stack: opts?.stack,
      ruta: typeof window !== "undefined" ? window.location.pathname : undefined,
      contexto: opts?.contexto,
    });
    if (typeof navigator !== "undefined" && navigator.sendBeacon) {
      navigator.sendBeacon(`${API}/errores`, new Blob([body], { type: "application/json" }));
    } else {
      fetch(`${API}/errores`, { method: "POST", headers: { "Content-Type": "application/json" }, body, keepalive: true }).catch(() => {});
    }
  } catch {
    // no-op
  }
}

export function reportarMetrica(ruta: string, metrica: string, valorMs: number, repetida?: boolean) {
  try {
    const body = JSON.stringify({ ruta, metrica, valor_ms: valorMs, repetida });
    if (typeof navigator !== "undefined" && navigator.sendBeacon) {
      navigator.sendBeacon(`${API}/metricas`, new Blob([body], { type: "application/json" }));
    } else {
      fetch(`${API}/metricas`, { method: "POST", headers: { "Content-Type": "application/json" }, body, keepalive: true }).catch(() => {});
    }
  } catch {
    // no-op
  }
}
