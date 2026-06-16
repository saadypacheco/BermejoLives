"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import type { Ciudad } from "@/lib/types";

// Carga Leaflet desde CDN una sola vez.
function loadLeaflet(): Promise<any> {
  if (typeof window === "undefined") return Promise.reject();
  if ((window as any).L) return Promise.resolve((window as any).L);
  if ((window as any).__leafletP) return (window as any).__leafletP;
  (window as any).__leafletP = new Promise((resolve, reject) => {
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
  return (window as any).__leafletP;
}

const BOLIVIA: [number, number] = [-16.8, -64.6];

export function BoliviaMap({ ciudades }: { ciudades: Ciudad[] }) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    loadLeaflet().then((L) => {
      if (cancelled || !elRef.current || mapRef.current) return;
      const map = L.map(elRef.current, {
        zoomControl: false,
        attributionControl: false,
        scrollWheelZoom: false,
        dragging: true,
        doubleClickZoom: false,
      }).setView(BOLIVIA, 5);
      mapRef.current = map;
      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", { maxZoom: 12 }).addTo(map);

      for (const c of ciudades) {
        if (c.lat == null || c.lng == null) continue;
        const activa = c.activa;
        const cls = activa ? "bpin activa" : `bpin${c.es_frontera ? " frontera" : ""}`;
        // Solo la ciudad activa muestra label permanente; el resto muestra tooltip al hover
        const icon = L.divIcon({
          className: "",
          html: `<div class="${cls}">${activa ? `<b>${c.nombre}</b>` : ""}</div>`,
          iconSize: [10, 10],
          iconAnchor: [5, 5],
        });
        const m = L.marker([c.lat, c.lng], { icon, zIndexOffset: activa ? 1000 : 0 }).addTo(map);
        if (activa) {
          m.on("click", () => router.push(`/buscar?ciudad=${c.slug}`));
        } else {
          m.bindTooltip(c.nombre, {
            permanent: false,
            direction: "right",
            className: "map-tip",
            offset: [8, 0],
          });
          m.bindPopup(`<div class="map-pop"><b>${c.nombre}</b><span>${c.departamento}${c.es_frontera ? " · frontera" : ""}</span><div style="color:var(--amber);font-size:12px;margin-top:4px">Próximamente</div></div>`);
        }
      }
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ciudades]);

  return (
    <div className="bolivia-wrap">
      <div ref={elRef} className="bolivia-map" />
      <div className="bolivia-legend">
        <span><i className="lg-on" /> En vivo: Bermejo</span>
        <span><i className="lg-off" /> Próximamente</span>
      </div>
    </div>
  );
}
