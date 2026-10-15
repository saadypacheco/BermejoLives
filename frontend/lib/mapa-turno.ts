/**
 * La farmacia de turno en el mapa: el pin destacado y el renglón del globo.
 * Leaflet arma el HTML como texto (ver `lib/iconos-mapa.ts`), así que acá no
 * hay React. Lo usan el mapa del buscador (`components/map-results.tsx`) y el
 * de `/farmacias-de-turno`.
 */
import { SVG_TURNO } from "@/lib/iconos-mapa";
import { escapeHtml } from "@/lib/mapa-visual";
import { telHref } from "@/lib/turnos-farmacia";
import { comoLlegarHref } from "@/lib/types";

/** Lado del pin de turno, en px: más grande que cualquier otro del mapa. */
export const PIN_TURNO = 40;

/** El pin: círculo verde con la cruz y un aro. Es el único pin con la cruz. */
export function pinTurnoHtml(): string {
  return `<div class="ukpin turno" role="img" aria-label="Farmacia de turno ahora"><i class="ukpin-ring turno"></i><span class="ukpin-emo">${SVG_TURNO}</span></div>`;
}

/** «De turno ahora · hasta mañana 08:00» para el globo (ícono + texto, no sólo color). */
export function selloTurnoHtml(hasta: string): string {
  return `<em class="map-pop-turno"><span class="map-pop-turno-ic">${SVG_TURNO}</span>De turno ahora · ${escapeHtml(hasta)}</em>`;
}

/** El globo completo de una farmacia de turno (página `/farmacias-de-turno`). */
export function popupFarmaciaHtml(f: {
  nombre: string; slug: string; direccion: string | null; telefono: string | null;
  lat: number | null; lng: number | null;
}, hasta: string): string {
  const tel = telHref(f.telefono);
  return `
    <div class="map-pop">
      <b>${escapeHtml(f.nombre)}</b>
      ${selloTurnoHtml(hasta)}
      ${f.direccion ? `<span>${escapeHtml(f.direccion)}</span>` : ""}
      <div class="map-pop-act">
        ${tel ? `<a href="${escapeHtml(tel)}">Llamar</a>` : ""}
        <a href="${escapeHtml(comoLlegarHref(f))}" target="_blank" rel="noopener">Cómo llegar</a>
        <a href="/comercios/${encodeURIComponent(f.slug)}">Ver ficha</a>
      </div>
    </div>`;
}
