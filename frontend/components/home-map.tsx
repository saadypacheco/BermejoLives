"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import type { ComercioMapa } from "@/lib/data";

const BERMEJO: [number, number] = [-22.7361, -64.3433];

const GOLDPIN = `<div class="goldpin"><svg viewBox="0 0 24 32" width="28" height="37"><path d="M12 0C5.37 0 0 5.37 0 12c0 8.4 12 20 12 20s12-11.6 12-20C24 5.37 18.63 0 12 0z" fill="#FFB020"/><circle cx="12" cy="12" r="5" fill="#3a2600"/></svg></div>`;
const GOLDPIN_SEL = `<div class="goldpin sel"><svg viewBox="0 0 24 32" width="34" height="45"><path d="M12 0C5.37 0 0 5.37 0 12c0 8.4 12 20 12 20s12-11.6 12-20C24 5.37 18.63 0 12 0z" fill="#39ff9e" stroke="#04240f" stroke-width="0"/><circle cx="12" cy="12" r="5" fill="#04240f"/></svg></div>`;

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

export function HomeMap({ comercios, onSelect, selectedId }: {
  comercios: ComercioMapa[]; onSelect?: (c: ComercioMapa) => void; selectedId?: string | null;
}) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const layerRef = useRef<any>(null);
  const LRef = useRef<any>(null);
  const meRef = useRef<[number, number] | null>(null);
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
      L.control.zoom({ position: "bottomright" }).addTo(map);
      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", { maxZoom: 19 }).addTo(map);
      layerRef.current = L.layerGroup().addTo(map);
      pintar();
      // reajustar al tamaño real del contenedor flex y ante cambios de viewport
      setTimeout(() => map.invalidateSize(), 150);
      const onResize = () => map.invalidateSize();
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
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // repintar marcadores cuando cambian comercios o el seleccionado
  useEffect(() => { pintar(); /* eslint-disable-next-line */ }, [comercios, selectedId]);

  function pintar() {
    const L = LRef.current, layer = layerRef.current;
    if (!L || !layer) return;
    layer.clearLayers();
    let selCoords: [number, number] | null = null;
    for (const c of comercios) {
      if (c.lat == null || c.lng == null) continue;
      const isSel = c.id === selectedId;
      if (isSel) selCoords = [c.lat, c.lng];
      const icon = L.divIcon({
        className: "", html: isSel ? GOLDPIN_SEL : GOLDPIN,
        iconSize: isSel ? [34, 45] : [28, 37], iconAnchor: isSel ? [17, 45] : [14, 37],
      });
      const m = L.marker([c.lat, c.lng], { icon, zIndexOffset: isSel ? 800 : 0 }).addTo(layer);
      m.on("click", () => { onSelRef.current?.(c); mapRef.current.panTo([c.lat, c.lng]); });
    }
    // línea punteada desde "estás acá" hasta el local seleccionado
    if (selCoords && meRef.current) {
      L.polyline([meRef.current, selCoords], { color: "#39ff9e", weight: 2, opacity: .85, dashArray: "5 8" }).addTo(layer);
    }
  }

  return (
    <div className="homemap">
      <div ref={elRef} className="homemap-canvas" />
      <Link href="/buscar" className="hm-btn hm-full">⛶ Ver mapa completo</Link>
    </div>
  );
}
