// Compartido por los dos mapas (HomeMap y MapResults): carga de Leaflet + plugin
// de clustering desde CDN (el SW cachea unpkg) y el estilo por rubro (color+emoji).

// Ícono + color por rubro (matchea los slugs de los chips de categoría de Bermejo).
export const CATEGORY_STYLE: Record<string, { emoji: string; color: string }> = {
  ropa: { emoji: "👕", color: "#3b82f6" },
  "ropa-americana": { emoji: "👕", color: "#6366f1" },
  calzado: { emoji: "👟", color: "#8b5cf6" },
  zapatillas: { emoji: "👟", color: "#8b5cf6" },
  belleza: { emoji: "💄", color: "#ec4899" },
  mascotas: { emoji: "🐾", color: "#f59e0b" },
  restaurantes: { emoji: "🍴", color: "#f97316" },
  gastronomia: { emoji: "🍴", color: "#f97316" },
  mercado: { emoji: "🛒", color: "#22c55e" },
  mercados: { emoji: "🛒", color: "#22c55e" },
  alimentos: { emoji: "🛒", color: "#22c55e" },
  electronica: { emoji: "💻", color: "#06b6d4" },
  tecnologia: { emoji: "💻", color: "#06b6d4" },
  celulares: { emoji: "📱", color: "#0ea5e9" },
  tablets: { emoji: "📱", color: "#0ea5e9" },
  ferreteria: { emoji: "🔧", color: "#eab308" },
  hogar: { emoji: "🛋️", color: "#14b8a6" },
  electrodomesticos: { emoji: "🔌", color: "#ef4444" },
  farmacia: { emoji: "➕", color: "#ef4444" },
  gomeria: { emoji: "🛞", color: "#64748b" },
  muebles: { emoji: "🛋️", color: "#14b8a6" },
  jugueteria: { emoji: "🧸", color: "#f43f5e" },
  bebidas: { emoji: "🥤", color: "#a855f7" },
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
