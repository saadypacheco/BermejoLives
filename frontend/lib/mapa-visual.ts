// Compartido por los dos mapas (HomeMap y MapResults): carga de Leaflet + plugin
// de clustering desde CDN (el SW cachea unpkg) y el color por rubro.

// Color por rubro (taxonomía v2). El color es por FAMILIA, para poder leer el
// mapa por zonas; el DIBUJO de cada rubro ya no vive acá sino en
// components/ic.tsx, y `lib/iconos-svg.ts` lo deja listo para el pin. Esta
// tabla es además la lista de qué rubros necesitan dibujo: el generador la lee.
// + aliases de slugs viejos.
export const CATEGORY_STYLE: Record<string, { color: string }> = {
  // 👗 Moda y accesorios
  ropa: { color: "#3b82f6" }, calzado: { color: "#3b82f6" },
  bolsos: { color: "#3b82f6" }, joyeria: { color: "#3b82f6" },
  // 💄 Belleza
  belleza: { color: "#ec4899" }, optica: { color: "#ec4899" },
  // 📱 Tecnología
  celulares: { color: "#06b6d4" }, computacion: { color: "#06b6d4" },
  electronica: { color: "#06b6d4" }, electrodomesticos: { color: "#06b6d4" },
  // 🏠 Hogar
  bazar: { color: "#14b8a6" }, hogar: { color: "#14b8a6" },
  muebles: { color: "#14b8a6" },
  // 🔧 Ferretería
  ferreteria: { color: "#eab308" },
  // 🚗 Vehículos
  "repuestos-autos": { color: "#64748b" }, neumaticos: { color: "#64748b" },
  motos: { color: "#64748b" }, bicicletas: { color: "#64748b" },
  // 🛒 Consumo
  alimentos: { color: "#22c55e" }, bebidas: { color: "#22c55e" },
  farmacia: { color: "#22c55e" }, mascotas: { color: "#22c55e" },
  // 🍽️ Gastronomía
  restaurantes: { color: "#f97316" }, "comida-rapida": { color: "#f97316" },
  cafeteria: { color: "#f97316" }, panaderia: { color: "#f97316" },
  // 🧰 Servicios
  cambio: { color: "#6366f1" }, envios: { color: "#6366f1" },
  peluqueria: { color: "#6366f1" }, lavadero: { color: "#6366f1" },
  "gomeria-servicio": { color: "#6366f1" }, cerrajeria: { color: "#6366f1" },
  hospedaje: { color: "#6366f1" },
  // 🧸 Familia y ocio
  jugueteria: { color: "#f43f5e" }, bebes: { color: "#f43f5e" },
  deportes: { color: "#f43f5e" }, regaleria: { color: "#f43f5e" },
  // 👕 Feria americana / usado
  "ropa-americana": { color: "#92766a" }, "calzado-usado": { color: "#92766a" },
  usados: { color: "#92766a" },
  // 🚻 Servicios de la ciudad (rubros no comerciales, 0083/0113) y movilidad
  banos: { color: "#0ea5e9" }, estacionamiento: { color: "#0ea5e9" },
  cajeros: { color: "#0ea5e9" }, wifi: { color: "#0ea5e9" },
  emergencias: { color: "#ef4444" }, alquiler: { color: "#8b5cf6" },
  "servicio-tecnico": { color: "#64748b" },
  taxis: { color: "#eab308" }, "estacion-servicio": { color: "#64748b" },
  "taller-mecanico": { color: "#64748b" }, coca: { color: "#22c55e" },
  nocturna: { color: "#6366f1" }, carpinteria: { color: "#92766a" },
  herreria: { color: "#64748b" }, limpieza: { color: "#22c55e" },
  telas: { color: "#3b82f6" }, gimnasios: { color: "#f43f5e" },
  funeraria: { color: "#64748b" }, carniceria: { color: "#22c55e" },
  salones: { color: "#f43f5e" }, agro: { color: "#22c55e" },
  kiosco: { color: "#22c55e" }, lenceria: { color: "#3b82f6" },
  blanqueria: { color: "#8b5cf6" }, marroquineria: { color: "#3b82f6" },
  // 📦 Otros
  otros: { color: "#FFB020" }, floreria: { color: "#FFB020" },
  // aliases de slugs viejos (comercios cargados antes de la taxonomía v2)
  zapatillas: { color: "#3b82f6" }, moda: { color: "#3b82f6" },
  gastronomia: { color: "#f97316" }, mercado: { color: "#22c55e" },
  mercados: { color: "#22c55e" }, tecnologia: { color: "#06b6d4" },
  gomeria: { color: "#64748b" }, servicios: { color: "#6366f1" },
  tablets: { color: "#06b6d4" },
};
export const DEFAULT_STYLE = { color: "#FFB020" };

/** Las familias del mapa, para la referencia de colores. El color es por
 *  familia (no por rubro) justamente para poder leer el mapa por zonas: dónde
 *  está la ropa, dónde la comida. Esta lista es la traducción de ese color a
 *  palabras; si se agrega una familia nueva arriba, va también acá. */
export const FAMILIAS: { nombre: string; color: string }[] = [
  { nombre: "Consumo diario", color: "#22c55e" },
  { nombre: "Gastronomía", color: "#f97316" },
  { nombre: "Moda", color: "#3b82f6" },
  { nombre: "Tecnología", color: "#06b6d4" },
  { nombre: "Hogar", color: "#14b8a6" },
  { nombre: "Servicios", color: "#6366f1" },
  { nombre: "Vehículos y oficios", color: "#64748b" },
  { nombre: "Ferretería y taxis", color: "#eab308" },
  { nombre: "Familia y ocio", color: "#f43f5e" },
  { nombre: "Belleza", color: "#ec4899" },
  { nombre: "Usado", color: "#92766a" },
  { nombre: "Servicios de la ciudad", color: "#0ea5e9" },
  { nombre: "Alquileres", color: "#8b5cf6" },
  { nombre: "Emergencias", color: "#ef4444" },
  { nombre: "Otros / sin rubro", color: "#FFB020" },
];
export const rubroStyle = (slug: string | null) => (slug && CATEGORY_STYLE[slug]) || DEFAULT_STYLE;

let leafletPromise: Promise<any> | null = null;
function cargarCss(href: string) {
  if (document.querySelector(`link[href="${href}"]`)) return;
  const l = document.createElement("link"); l.rel = "stylesheet"; l.href = href; document.head.appendChild(l);
}
function cargarJs(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve();
    const s = document.createElement("script"); s.src = src; s.onload = () => resolve(); s.onerror = reject;
    document.head.appendChild(s);
  });
}

// Opciones de cluster SIN "patitas" (spiderfy): tocar un grupo hace ZOOM (no expande
// con líneas). El zoom lo maneja cada mapa con manejarClusterClick para poder caer a
// la "hoja" (lista) cuando los pines están tan pegados que el zoom no los separa.
export function opcionesCluster(L: any) {
  return {
    spiderfyOnMaxZoom: false,
    zoomToBoundsOnClick: false,        // lo manejamos nosotros (zoom fuerte o hoja)
    showCoverageOnHover: false,
    maxClusterRadius: 45,
    disableClusteringAtZoom: 19,       // de acá se ven todos individuales
    chunkedLoading: true,
    iconCreateFunction: (cl: any) => L.divIcon({
      className: "", iconSize: [38, 38], html: `<div class="ukclus">${cl.getChildCount()}</div>`,
    }),
  };
}

/** Al tocar un cluster: si se pueden separar con zoom, vuela ahí (zoom fuerte).
 * Si están casi en el mismo punto (el zoom no los separa), devuelve "hoja" con la
 * lista de los comercios (cada marker guarda su dato en m.__data) para elegir. */
export function manejarClusterClick(map: any, e: any, zoomMax = 18, minSpanM = 6): { accion: "zoom" | "hoja"; comercios: any[] } {
  const b = e.layer.getBounds();
  const spanM = b.getNorthEast().distanceTo(b.getSouthWest());
  if (map.getZoom() < zoomMax && spanM > minSpanM) {
    map.flyToBounds(b, { maxZoom: zoomMax, padding: [50, 50], duration: 0.45 });
    return { accion: "zoom", comercios: [] };
  }
  return { accion: "hoja", comercios: e.layer.getAllChildMarkers().map((m: any) => m.__data) };
}

/** Escapa texto para meterlo en HTML de un divIcon/tooltip sin romper ni inyectar. */
export function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch] as string));
}

/** Carga Leaflet + markercluster una sola vez y resuelve `L` (con markerClusterGroup). */
export function loadLeaflet(): Promise<any> {
  if (typeof window === "undefined") return Promise.reject();
  if ((window as any).L?.markerClusterGroup) return Promise.resolve((window as any).L);
  if (leafletPromise) return leafletPromise;
  leafletPromise = (async () => {
    cargarCss("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css");
    cargarCss("https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css");
    if (!(window as any).L) await cargarJs("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js");
    if (!(window as any).L.markerClusterGroup) {
      await cargarJs("https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js");
    }
    return (window as any).L;
  })();
  return leafletPromise;
}
