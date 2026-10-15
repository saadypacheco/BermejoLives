/**
 * Cómo se pintan las calles en Leaflet, para el panel y para la app del agente.
 *
 * ~600 polilíneas en SVG hacen un DOM de 600 nodos que se arrastra mal en un
 * celular de gama baja; en un canvas son un solo elemento. Por eso van con
 * `L.canvas()`, y con `tolerance` generoso: el dedo no acierta a una línea de
 * 6 px, así que el área tocable es bastante más ancha que lo que se ve.
 *
 * LO QUE RESALTA ES LO HECHO. En una ciudad recién empezada casi todo está
 * pendiente (Tarija: 1.471 de 1.536 cuadras) y pintar eso en rojo tapaba todo.
 * Ahora: lo recorrido en verde grueso, lo parcial en ámbar, las cuadras
 * pendientes que TOCAN por una esquina a una recorrida en naranja («seguir por
 * acá»: la cuadra siguiente) y el resto de las pendientes en gris finito.
 */
import { COLOR_CALLE, COLOR_SIGUIENTE, TRAZO_CALLE, type TramoCalle } from "@/lib/calles";

/* eslint-disable @typescript-eslint/no-explicit-any */
// Leaflet se carga por <script> (lib/mapa-visual.ts) y no trae tipos: igual que
// en el resto de los mapas, `L` es `any`.

/** Cuánto se acerca el dedo a una línea y sigue contando como toque. */
const TOLERANCIA_PX = 12;

/** Dos puntas de cuadra a menos de esto son la misma esquina. */
const ESQUINA_M = 25;

/** Cómo se VE un tramo: el estado, más la división de las pendientes. */
export type VisualCalle = "recorrida" | "parcial" | "siguiente" | "lejana" | "sin_comercios";

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

const M_POR_GRADO = 111_320;

/** Separa las pendientes en «siguiente» y «lejana». Siguiente = una cuadra
 *  pendiente con una PUNTA en la misma esquina (≤ 25 m) que la punta de una
 *  recorrida o parcial: la cuadra que sigue. Antes era «cualquier punto a
 *  ≤ 150 m de algo recorrido», y con calles largas se encendía media ciudad
 *  (Tarija: 97 km en naranja contra 3 km recorridos). Grilla por celdas. */
export function clasificarCalles(tramos: TramoCalle[]): Map<string, VisualCalle> {
  const out = new Map<string, VisualCalle>();
  if (tramos.length === 0) return out;
  const lat0 = tramos[0].geom[0]?.[0] ?? -22;
  const mLng = M_POR_GRADO * Math.cos((lat0 * Math.PI) / 180);
  const celda = ESQUINA_M;
  const puntas = (g: TramoCalle["geom"]) => (g.length > 0 ? [g[0], g[g.length - 1]] : []);
  const clave = (lat: number, lng: number) => `${Math.floor((lat * M_POR_GRADO) / celda)}:${Math.floor((lng * mLng) / celda)}`;
  const hechos = new Map<string, [number, number][]>();
  for (const t of tramos) {
    if (t.estado !== "recorrida" && t.estado !== "parcial") continue;
    for (const p of puntas(t.geom)) {
      const k = clave(p[0], p[1]);
      const l = hechos.get(k); if (l) l.push(p); else hechos.set(k, [p]);
    }
  }
  const cerca = (lat: number, lng: number): boolean => {
    const cy = Math.floor((lat * M_POR_GRADO) / celda), cx = Math.floor((lng * mLng) / celda);
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      for (const q of hechos.get(`${cy + dy}:${cx + dx}`) ?? []) {
        const d = Math.hypot((q[0] - lat) * M_POR_GRADO, (q[1] - lng) * mLng);
        if (d <= ESQUINA_M) return true;
      }
    }
    return false;
  };
  for (const t of tramos) {
    if (t.estado !== "pendiente") { out.set(t.id, t.estado); continue; }
    out.set(t.id, hechos.size > 0 && puntas(t.geom).some((p) => cerca(p[0], p[1])) ? "siguiente" : "lejana");
  }
  return out;
}

/** Lo dibujado primero queda abajo: el fondo gris, arriba lo recorrido. */
const ORDEN: VisualCalle[] = ["lejana", "sin_comercios", "siguiente", "parcial", "recorrida"];

function estiloVisual(v: VisualCalle, grosor: number): Record<string, unknown> {
  const base = { lineCap: "round", lineJoin: "round" };
  switch (v) {
    case "recorrida": return { ...base, color: COLOR_CALLE.recorrida, weight: grosor + 1, opacity: 1 };
    case "parcial": return { ...base, color: COLOR_CALLE.parcial, weight: grosor, opacity: 0.95, dashArray: TRAZO_CALLE.parcial };
    case "siguiente": return { ...base, color: COLOR_SIGUIENTE, weight: Math.max(2, grosor - 1), opacity: 0.9 };
    case "sin_comercios": return { ...base, color: COLOR_CALLE.sin_comercios, weight: 1.5, opacity: 0.55, dashArray: TRAZO_CALLE.sin_comercios };
    default: return { ...base, color: COLOR_CALLE.pendiente, weight: Math.max(1.5, grosor - 3), opacity: 0.45 };
  }
}

/** Dibuja los tramos en `grupo`. Devuelve id → polilínea, para resaltar una. */
export function pintarCalles(
  L: any, renderer: any, grupo: any, tramos: TramoCalle[], grosor: number, alTocar: (id: string) => void,
): Map<string, any> {
  const lineas = new Map<string, any>();
  const visual = clasificarCalles(tramos);
  const ordenados = [...tramos].sort((a, b) => ORDEN.indexOf(visual.get(a.id) ?? "lejana") - ORDEN.indexOf(visual.get(b.id) ?? "lejana"));
  for (const t of ordenados) {
    const v = visual.get(t.id) ?? "lejana";
    const linea = L.polyline(t.geom, { ...estiloVisual(v, grosor), renderer, interactive: true, bubblingMouseEvents: false });
    linea._ukVisual = v;
    linea.on("click", () => alTocar(t.id));
    linea.addTo(grupo);
    lineas.set(t.id, linea);
  }
  return lineas;
}

/** Al acercar o alejar: cada línea con el grosor que le toca a su clase. */
export function reestilarCalles(lineas: Map<string, any>, grosor: number): void {
  lineas.forEach((linea) => linea.setStyle(estiloVisual(linea._ukVisual ?? "lejana", grosor)));
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

// ── Zonas: la ciudad entera de un vistazo ────────────────────────────────────

/** Lado de cada zona. 300 m son tres o cuatro cuadras: un barrio chico. */
const LADO_ZONA_M = 300;

export type Zona = { sur: number; oeste: number; norte: number; este: number; kmARecorrer: number; kmRecorridos: number; pct: number };

/** Reparte los km de cada calle entre las zonas que atraviesa (por tramos entre
 *  vértices) y saca el % recorrido de cada una. Las «sin comercios» no cuentan;
 *  lo parcial cuenta por su cobertura. */
export function calcularZonas(tramos: TramoCalle[]): Zona[] {
  if (tramos.length === 0) return [];
  const lat0 = tramos[0].geom[0]?.[0] ?? -22;
  const mLng = M_POR_GRADO * Math.cos((lat0 * Math.PI) / 180);
  const dLat = LADO_ZONA_M / M_POR_GRADO, dLng = LADO_ZONA_M / mLng;
  const acc = new Map<string, { y: number; x: number; total: number; hecho: number }>();
  for (const t of tramos) {
    if (t.estado === "sin_comercios") continue;
    const peso = t.estado === "recorrida" ? 1 : t.estado === "parcial" ? Math.min(1, Math.max(0, t.cobertura / 100)) : 0;
    for (let i = 1; i < t.geom.length; i++) {
      const [a, b] = [t.geom[i - 1], t.geom[i]];
      const m = Math.hypot((b[0] - a[0]) * M_POR_GRADO, (b[1] - a[1]) * mLng);
      const lat = (a[0] + b[0]) / 2, lng = (a[1] + b[1]) / 2;
      const y = Math.floor(lat / dLat), x = Math.floor(lng / dLng);
      const k = `${y}:${x}`;
      const z = acc.get(k) ?? { y, x, total: 0, hecho: 0 };
      z.total += m; z.hecho += m * peso;
      acc.set(k, z);
    }
  }
  const out: Zona[] = [];
  acc.forEach((z) => {
    if (z.total < 50) return;   // un pedacito de calle no hace una zona
    out.push({ sur: z.y * dLat, oeste: z.x * dLng, norte: (z.y + 1) * dLat, este: (z.x + 1) * dLng,
               kmARecorrer: z.total / 1000, kmRecorridos: z.hecho / 1000, pct: (100 * z.hecho) / z.total });
  });
  return out;
}

/** Verde más fuerte cuanto más recorrida; sin nada, sólo el borde. */
function estiloZona(pct: number): Record<string, unknown> {
  // Sin bordes: la cuadrícula de líneas ensuciaba el mapa. Sólo relleno.
  if (pct < 1) return { stroke: false, fillColor: "#64748b", fillOpacity: 0.07 };
  const fill = pct >= 70 ? 0.6 : pct >= 30 ? 0.42 : pct >= 10 ? 0.28 : 0.16;
  return { stroke: false, fillColor: COLOR_CALLE.recorrida, fillOpacity: fill };
}

/** Dibuja las zonas; tocar una avisa sus límites (para acercarse y ver las calles). */
export function pintarZonas(
  L: any, renderer: any, grupo: any, zonas: Zona[], alTocar: (b: [[number, number], [number, number]]) => void,
): void {
  for (const z of zonas) {
    const limites: [[number, number], [number, number]] = [[z.sur, z.oeste], [z.norte, z.este]];
    const r = L.rectangle(limites, { ...estiloZona(z.pct), renderer, interactive: true, bubblingMouseEvents: false });
    r.bindTooltip(`${Math.round(z.pct)} % recorrido · ${z.kmRecorridos.toFixed(1).replace(".", ",")} de ${z.kmARecorrer.toFixed(1).replace(".", ",")} km`, { sticky: true });
    r.on("click", () => alTocar(limites));
    r.addTo(grupo);
  }
}
