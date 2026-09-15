// Dónde está la persona, para el mapa y para ordenar por cercanía.
//
// La posición se pide UNA vez y se guarda diez minutos en el navegador: el
// mapa y la lista la comparten, y volver a la pantalla no vuelve a preguntar.
// Se pide sola sólo cuando el permiso ya estaba dado (el navegador lo sabe sin
// preguntar); si no, la pide el botón. Un sitio que pide la ubicación apenas
// abre, antes de mostrar nada, es un sitio al que se le dice que no.
import { geoErrorMsg } from "@/lib/geo";

export type Ubicacion = { lat: number; lng: number; precision: number; en: number };

const CLAVE = "uk-ubicacion";
const VIGENCIA_MS = 10 * 60 * 1000;

export function ubicacionGuardada(): Ubicacion | null {
  try {
    const raw = localStorage.getItem(CLAVE);
    if (!raw) return null;
    const u = JSON.parse(raw) as Ubicacion;
    if (!u || typeof u.lat !== "number" || Date.now() - u.en > VIGENCIA_MS) return null;
    return u;
  } catch {
    return null;
  }
}

export async function permisoUbicacion(): Promise<"granted" | "prompt" | "denied" | "unknown"> {
  try {
    if (!("permissions" in navigator)) return "unknown";
    const p = await navigator.permissions.query({ name: "geolocation" as PermissionName });
    return p.state;
  } catch {
    return "unknown";
  }
}

/** Pide la posición al navegador. Rechaza con un mensaje para mostrar. */
export function pedirUbicacion(): Promise<Ubicacion> {
  return new Promise((resolve, reject) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      reject(new Error("Este navegador no puede dar la ubicación."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const u: Ubicacion = { lat: pos.coords.latitude, lng: pos.coords.longitude, precision: pos.coords.accuracy, en: Date.now() };
        try { localStorage.setItem(CLAVE, JSON.stringify(u)); } catch { /* modo privado */ }
        resolve(u);
      },
      (e) => reject(new Error(geoErrorMsg(e))),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    );
  });
}
