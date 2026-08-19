// Compartido por los dos mapas (HomeMap y MapResults): carga de Leaflet + plugin
// de clustering desde CDN (el SW cachea unpkg) y el estilo por rubro (color+emoji).

// Ícono + color por rubro (taxonomía v2, 42 rubros). Color por FAMILIA (para leer
// el mapa por zonas de color) y EMOJI distinto por rubro. + aliases de slugs viejos.
export const CATEGORY_STYLE: Record<string, { emoji: string; color: string }> = {
  // 👗 Moda y accesorios
  ropa: { emoji: "👕", color: "#3b82f6" }, calzado: { emoji: "👟", color: "#3b82f6" },
  bolsos: { emoji: "🎒", color: "#3b82f6" }, joyeria: { emoji: "💍", color: "#3b82f6" },
  // 💄 Belleza
  belleza: { emoji: "💄", color: "#ec4899" }, optica: { emoji: "👓", color: "#ec4899" },
  // 📱 Tecnología
  celulares: { emoji: "📱", color: "#06b6d4" }, computacion: { emoji: "💻", color: "#06b6d4" },
  electronica: { emoji: "📺", color: "#06b6d4" }, electrodomesticos: { emoji: "🔌", color: "#06b6d4" },
  // 🏠 Hogar
  bazar: { emoji: "🍳", color: "#14b8a6" }, hogar: { emoji: "🛏️", color: "#14b8a6" },
  muebles: { emoji: "🛋️", color: "#14b8a6" },
  // 🔧 Ferretería
  ferreteria: { emoji: "🔧", color: "#eab308" },
  // 🚗 Vehículos
  "repuestos-autos": { emoji: "🚗", color: "#64748b" }, neumaticos: { emoji: "🛞", color: "#64748b" },
  motos: { emoji: "🏍️", color: "#64748b" }, bicicletas: { emoji: "🚲", color: "#64748b" },
  // 🛒 Consumo
  alimentos: { emoji: "🛒", color: "#22c55e" }, bebidas: { emoji: "🥤", color: "#22c55e" },
  farmacia: { emoji: "💊", color: "#22c55e" }, mascotas: { emoji: "🐾", color: "#22c55e" },
  // 🍽️ Gastronomía
  restaurantes: { emoji: "🍽️", color: "#f97316" }, "comida-rapida": { emoji: "🍔", color: "#f97316" },
  cafeteria: { emoji: "☕", color: "#f97316" }, panaderia: { emoji: "🥖", color: "#f97316" },
  // 🧰 Servicios
  cambio: { emoji: "💱", color: "#6366f1" }, envios: { emoji: "📦", color: "#6366f1" },
  peluqueria: { emoji: "💈", color: "#6366f1" }, lavadero: { emoji: "🧼", color: "#6366f1" },
  "gomeria-servicio": { emoji: "🔩", color: "#6366f1" }, cerrajeria: { emoji: "🗝️", color: "#6366f1" },
  hospedaje: { emoji: "🏨", color: "#6366f1" },
  // 🧸 Familia y ocio
  jugueteria: { emoji: "🧸", color: "#f43f5e" }, bebes: { emoji: "👶", color: "#f43f5e" },
  deportes: { emoji: "⚽", color: "#f43f5e" }, regaleria: { emoji: "🎉", color: "#f43f5e" },
  // 👕 Feria americana / usado
  "ropa-americana": { emoji: "👕", color: "#92766a" }, "calzado-usado": { emoji: "👟", color: "#92766a" },
  usados: { emoji: "♻️", color: "#92766a" },
  // 📦 Otros
  otros: { emoji: "📦", color: "#FFB020" }, floreria: { emoji: "🌷", color: "#FFB020" },
  // aliases de slugs viejos (comercios cargados antes de la taxonomía v2)
  zapatillas: { emoji: "👟", color: "#3b82f6" }, moda: { emoji: "👕", color: "#3b82f6" },
  gastronomia: { emoji: "🍽️", color: "#f97316" }, mercado: { emoji: "🛒", color: "#22c55e" },
  mercados: { emoji: "🛒", color: "#22c55e" }, tecnologia: { emoji: "💻", color: "#06b6d4" },
  gomeria: { emoji: "🛞", color: "#64748b" }, servicios: { emoji: "🧰", color: "#6366f1" },
  tablets: { emoji: "📱", color: "#06b6d4" },
};
export const DEFAULT_STYLE = { emoji: "📍", color: "#FFB020" };
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
