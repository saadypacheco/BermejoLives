import type { Ciudad } from "@/lib/types";

export const CIUDAD_COOKIE = "ciudad";

/** Resuelve la ciudad a mostrar: por slug (si está activa), o la 1ª activa, o la 1ª. */
export function resolveCiudad(ciudades: Ciudad[], slug?: string | null): Ciudad | null {
  if (!ciudades.length) return null;
  const activas = ciudades.filter((c) => c.activa);
  if (slug) {
    const hit = ciudades.find((c) => c.slug === slug && c.activa);
    if (hit) return hit;
  }
  return activas[0] ?? ciudades[0];
}

/** Distancia aproximada (equirectangular, suficiente para elegir la más cercana). */
function dist(aLat: number, aLng: number, bLat: number, bLng: number): number {
  const dLat = aLat - bLat;
  const dLng = (aLng - bLng) * Math.cos((aLat * Math.PI) / 180);
  return dLat * dLat + dLng * dLng;
}

/** Ciudad ACTIVA más cercana a una coordenada (para el default por geolocalización). */
export function ciudadMasCercana(ciudades: Ciudad[], lat: number, lng: number): Ciudad | null {
  const activas = ciudades.filter((c) => c.activa && c.lat != null && c.lng != null);
  if (!activas.length) return null;
  return activas.reduce((best, c) =>
    dist(lat, lng, c.lat as number, c.lng as number) < dist(lat, lng, best.lat as number, best.lng as number) ? c : best
  );
}
