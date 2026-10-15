/**
 * Cómo se pintan las calles en Leaflet, para el panel y para la app del agente.
 *
 * ~600 polilíneas en SVG hacen un DOM de 600 nodos que se arrastra mal en un
 * celular de gama baja; en un canvas son un solo elemento. Por eso van con
 * `L.canvas()`, y con `tolerance` generoso: el dedo no acierta a una línea de
 * 6 px, así que el área tocable es bastante más ancha que lo que se ve.
 */
import { COLOR_CALLE, TRAZO_CALLE, type TramoCalle } from "@/lib/calles";

/* eslint-disable @typescript-eslint/no-explicit-any */
// Leaflet se carga por <script> (lib/mapa-visual.ts) y no trae tipos: igual que
// en el resto de los mapas, `L` es `any`.

/** Cuánto se acerca el dedo a una línea y sigue contando como toque. */
const TOLERANCIA_PX = 12;

/** Trazo grueso para que se toque; más fino al alejar para que no sea una mancha. */
export function grosorPorZoom(zoom: number): number {
  if (zoom <= 13) return 3;
  if (zoom === 14) return 4;
  if (zoom === 15) return 5;
  if (zoom === 16) return 6;
  return 8;
}

/** El renderer en canvas, ya puesto en el mapa. Se crea ANTES de dibujar nada
 *  más, así queda por debajo de los círculos y pines que se agreguen después. */
export function crearRendererCalles(L: any, map: any): any {
  const r = L.canvas({ padding: 0.4, tolerance: TOLERANCIA_PX });
  r.addTo(map);
  return r;
}

export function estiloCalle(t: TramoCalle, grosor: number): Record<string, unknown> {
  return {
    color: COLOR_CALLE[t.estado],
    weight: grosor,
    opacity: t.estado === "sin_comercios" ? 0.85 : 0.95,
    dashArray: TRAZO_CALLE[t.estado],
    lineCap: "round",
    lineJoin: "round",
  };
}

/** Dibuja los tramos en `grupo`. Devuelve id → polilínea, para resaltar una. */
export function pintarCalles(
  L: any, renderer: any, grupo: any, tramos: TramoCalle[], grosor: number, alTocar: (id: string) => void,
): Map<string, any> {
  const lineas = new Map<string, any>();
  for (const t of tramos) {
    const linea = L.polyline(t.geom, {
      ...estiloCalle(t, grosor),
      renderer,
      interactive: true,
      bubblingMouseEvents: false,
    });
    linea.on("click", () => alTocar(t.id));
    linea.addTo(grupo);
    lineas.set(t.id, linea);
  }
  return lineas;
}

/** Un halo blanco debajo de la calle elegida, y la calle por encima. */
export function resaltarCalle(
  L: any, renderer: any, grupo: any, anterior: any | null, linea: any | null, tramo: TramoCalle | null, grosor: number,
): any | null {
  if (anterior) grupo.removeLayer(anterior);
  if (!linea || !tramo) return null;
  const halo = L.polyline(tramo.geom, {
    color: "#ffffff", weight: grosor + 7, opacity: 0.95, renderer, interactive: false, lineCap: "round", lineJoin: "round",
  });
  halo.addTo(grupo);
  linea.bringToFront();
  return halo;
}
