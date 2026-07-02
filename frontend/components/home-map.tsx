"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import type { ComercioMapa } from "@/lib/data";

const BERMEJO: [number, number] = [-22.7361, -64.3433];

// Ícono + color por rubro (coincide con los slugs de los chips de categoría).
const CATEGORY_STYLE: Record<string, { emoji: string; color: string }> = {
  gomeria: { emoji: "🔧", color: "#14b8a6" },
  farmacia: { emoji: "➕", color: "#ef4444" },
  gastronomia: { emoji: "🍴", color: "#f97316" },
  mercado: { emoji: "🛒", color: "#8b5cf6" },
  tecnologia: { emoji: "📱", color: "#3b82f6" },
};
const DEFAULT_STYLE = { emoji: "📍", color: "#FFB020" };

function pinHtml(rubroSlug: string | null, pct: number | null | undefined, selected: boolean): string {
  const style = (rubroSlug && CATEGORY_STYLE[rubroSlug]) || DEFAULT_STYLE;
  const badge = pct ? `<b class="catpin-badge">-${pct}%</b>` : "";
  return `<div class="catpin${selected ? " sel" : ""}" style="background:${style.color}">${badge}<span>${style.emoji}</span></div>`;
}

let leafletPromise: Promise<any> | null = null;
function loadLeaflet(): Promise<any> {
  if (typeof window === "undefined") return Promise.reject();
  if ((window as any).L) return Promise.resolve((window as any).L);
  if (leafletPromise) return leafletPromise;
  leafletPromise = new Promise((resolve, reject) => {
    const css = document.createElement("link");
    css.rel = "stylesheet";
    css.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    document.head.appendChild(css);
    const js = document.createElement("script");
    js.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    js.onload = () => resolve((window as any).L);
    js.onerror = reject;
    document.head.appendChild(js);
  });
  return leafletPromise;
}

export function HomeMap({ comercios, onSelect, selectedId, descuentoPorId }: {
  comercios: ComercioMapa[]; onSelect?: (c: ComercioMapa) => void; selectedId?: string | null;
  descuentoPorId?: Record<string, number>;
}) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const layerRef = useRef<any>(null);
  const LRef = useRef<any>(null);
  const meRef = useRef<[number, number] | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const pathRef = useRef<SVGPathElement>(null);
  const selCoordRef = useRef<[number, number] | null>(null);
  const onSelRef = useRef(onSelect);
  onSelRef.current = onSelect;

  // init una sola vez
  useEffect(() => {
    let cancelled = false;
    loadLeaflet().then((L) => {
      if (cancelled || !elRef.current || mapRef.current) return;
      LRef.current = L;
      const map = L.map(elRef.current, { zoomControl: false, attributionControl: false, scrollWheelZoom: false }).setView(BERMEJO, 15);
      mapRef.current = map;
      L.control.zoom({ position: "topleft" }).addTo(map);
      // updateWhenIdle/keepBuffer: menos descargas de tiles (clave con internet malo)
      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        maxZoom: 19, updateWhenIdle: true, updateWhenZooming: false, keepBuffer: 2, crossOrigin: true,
      }).addTo(map);
      layerRef.current = L.layerGroup().addTo(map);
      pintar();
      // el conector pin→tarjeta se redibuja al mover/zoomear el mapa
      map.on("move zoom moveend", drawConnector);
      // El contenedor flex puede terminar de asentar su alto real después del
      // primer render (chips, fuentes, hidratación) sin que dispare un evento
      // "resize" de la ventana — sin este observer, map.getSize() queda con un
      // tamaño viejo y el pin calculado por latLngToContainerPoint (y por lo
      // tanto la flecha) queda desalineado respecto al DOM real.
      const ro = new ResizeObserver(() => { map.invalidateSize(); drawConnector(); });
      ro.observe(elRef.current);
      (map as any)._ro = ro;
      const onResize = () => { map.invalidateSize(); drawConnector(); };
      window.addEventListener("resize", onResize);
      (map as any)._onResize = onResize;
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition((pos) => {
          if (cancelled || !mapRef.current) return;
          meRef.current = [pos.coords.latitude, pos.coords.longitude];
          const here = L.divIcon({ className: "", html: `<div class="here-dot"></div>`, iconSize: [22, 22], iconAnchor: [11, 11] });
          L.marker(meRef.current, { icon: here, zIndexOffset: 1000 }).addTo(map);
          pintar(); // redibuja por si hay que trazar la línea al local seleccionado
        }, () => {}, { timeout: 5000, maximumAge: 600000 });
      }
    });
    return () => {
      cancelled = true;
      if (mapRef.current?._onResize) window.removeEventListener("resize", mapRef.current._onResize);
      mapRef.current?._ro?.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // repintar marcadores cuando cambian comercios o el seleccionado
  useEffect(() => { pintar(); /* eslint-disable-next-line */ }, [comercios, selectedId, descuentoPorId]);

  function pintar() {
    const L = LRef.current, layer = layerRef.current;
    if (!L || !layer) return;
    layer.clearLayers();
    let selCoords: [number, number] | null = null;
    for (const c of comercios) {
      if (c.lat == null || c.lng == null) continue;
      const isSel = c.id === selectedId;
      if (isSel) selCoords = [c.lat, c.lng];
      const pct = descuentoPorId?.[c.id];
      const size = isSel ? 40 : 32;
      const icon = L.divIcon({
        className: "", html: pinHtml(c.rubro_slug, pct, isSel),
        iconSize: [size, size], iconAnchor: [size / 2, size / 2],
      });
      const m = L.marker([c.lat, c.lng], { icon, zIndexOffset: isSel ? 800 : 0 }).addTo(layer);
      m.on("click", () => {
        onSelRef.current?.(c);
        // mover el pin a la zona alta del mapa para que la tarjeta (abajo) no lo tape
        const map = mapRef.current;
        const size = map.getSize();
        const pt = map.latLngToContainerPoint([c.lat, c.lng]);
        const target = map.containerPointToLatLng([pt.x, pt.y + size.y * 0.30]); // pin queda ~20% desde arriba
        map.panTo(target, { animate: true, duration: 0.4 });
      });
    }
    selCoordRef.current = selCoords;
    drawConnector();
  }

  // Dibuja la flecha punteada desde el pin seleccionado hacia la tarjeta (abajo).
  function drawConnector() {
    const map = mapRef.current, svg = svgRef.current, path = pathRef.current;
    if (!map || !svg || !path) return;
    const sc = selCoordRef.current;
    if (!sc) { svg.style.display = "none"; return; }
    const size = map.getSize();
    const p = map.latLngToContainerPoint(sc);
    svg.setAttribute("width", String(size.x));
    svg.setAttribute("height", String(size.y));
    svg.style.display = "block";
    // del pin (arriba) hacia el borde superior real de la tarjeta (si está montada)
    const cardEl = elRef.current?.closest(".mmap")?.querySelector<HTMLElement>(".mcard");
    const mapTop = elRef.current!.getBoundingClientRect().top;
    const x2 = size.x / 2;
    const y2 = cardEl ? cardEl.getBoundingClientRect().top - mapTop - 8 : size.y * 0.52;
    const c1x = p.x + 14, c1y = p.y + (y2 - p.y) * 0.55;
    const c2x = x2 + 14, c2y = p.y + (y2 - p.y) * 0.75;
    // el pin seleccionado es un círculo de 40px anclado en su centro: arrancar
    // la línea desde su borde inferior (radio 20), no desde el centro.
    path.setAttribute("d", `M ${p.x} ${p.y + 20} C ${c1x} ${c1y} ${c2x} ${c2y} ${x2} ${y2}`);
  }

  return (
    <div className="homemap">
      <div ref={elRef} className="homemap-canvas" />
      <svg ref={svgRef} className="hm-connector" style={{ display: "none" }} aria-hidden>
        <defs>
          <marker id="hmArrow" markerUnits="userSpaceOnUse" markerWidth="13" markerHeight="13" refX="9" refY="6" orient="auto">
            <path d="M1,1 L11,6 L1,11 Z" fill="#39ff9e" />
          </marker>
        </defs>
        <path ref={pathRef} fill="none" stroke="#39ff9e" strokeWidth="2" strokeDasharray="4 6" strokeLinecap="round" markerEnd="url(#hmArrow)" />
      </svg>
      <Link href="/buscar" className="hm-btn hm-full">⛶ Ver mapa completo</Link>
    </div>
  );
}
