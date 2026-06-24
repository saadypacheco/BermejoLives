"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import type { ComercioMapa } from "@/lib/data";

const BERMEJO: [number, number] = [-22.7361, -64.3433];

const RUBRO_MARK: Record<string, { color: string; emoji: string }> = {
  gastronomia: { color: "#ff7a59", emoji: "🍔" },
  mercado: { color: "#39ff9e", emoji: "🛒" },
  servicios: { color: "#5b9dff", emoji: "🔧" },
  farmacia: { color: "#37d67a", emoji: "💊" },
  hogar: { color: "#b07cff", emoji: "🏠" },
  moda: { color: "#ff5d79", emoji: "👕" },
  tecnologia: { color: "#22d3ee", emoji: "📱" },
  importadora: { color: "#ffb020", emoji: "📦" },
  gomeria: { color: "#9aa3af", emoji: "🛞" },
  belleza: { color: "#f472b6", emoji: "💄" },
};
const DEFAULT_MARK = { color: "#39ff9e", emoji: "📍" };

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

export function HomeMap({ comercios }: { comercios: ComercioMapa[] }) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const activos = comercios.filter((c) => c.lat != null && c.lng != null);

  useEffect(() => {
    let cancelled = false;
    loadLeaflet().then((L) => {
      if (cancelled || !elRef.current || mapRef.current) return;
      const map = L.map(elRef.current, { zoomControl: false, attributionControl: false, scrollWheelZoom: false }).setView(BERMEJO, 15);
      mapRef.current = map;
      L.control.zoom({ position: "bottomright" }).addTo(map);
      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", { maxZoom: 19 }).addTo(map);
      const bounds: [number, number][] = [];
      for (const c of activos) {
        const mk = RUBRO_MARK[c.rubro_slug ?? ""] ?? DEFAULT_MARK;
        const icon = L.divIcon({
          className: "",
          html: `<div class="hmark" style="--mc:${mk.color}">${mk.emoji}</div>`,
          iconSize: [32, 32],
          iconAnchor: [16, 16],
        });
        const wa = (c.whatsapp || "").replace(/\D/g, "");
        const popup = `<div class="map-pop"><b>${c.nombre}</b><div class="map-pop-act">${wa ? `<a href="https://wa.me/${wa}" target="_blank" rel="noopener">WhatsApp</a>` : ""}<a href="/comercios/${c.slug}">Ver comercio</a></div></div>`;
        L.marker([c.lat as number, c.lng as number], { icon }).bindPopup(popup).addTo(map);
        bounds.push([c.lat as number, c.lng as number]);
      }
      if (bounds.length > 1) map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="homemap">
      <div ref={elRef} className="homemap-canvas" />
      <Link href="/buscar" className="hm-btn hm-list">☰ Ver en lista</Link>
      <Link href="/buscar" className="hm-btn hm-full">⛶ Ver mapa completo</Link>
      <div className="hm-count"><span className="dot-live" /> <b>{activos.length}</b> negocios activos</div>
    </div>
  );
}
