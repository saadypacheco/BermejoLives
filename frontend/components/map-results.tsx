"use client";

import { useEffect, useRef } from "react";
import { type ResultadoBusqueda, comoLlegarHref, waLink, MODALIDAD_LABEL } from "@/lib/types";
import { registrarLead } from "@/lib/campo";

// Carga Leaflet desde CDN una sola vez (evita sumar dependencia npm / rebuild).
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

const BERMEJO: [number, number] = [-22.7361, -64.3433];

export function MapResults({ results }: { results: ResultadoBusqueda[] }) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const layerRef = useRef<any>(null);

  useEffect(() => {
    let cancelled = false;
    loadLeaflet().then((L) => {
      if (cancelled || !elRef.current) return;
      if (!mapRef.current) {
        mapRef.current = L.map(elRef.current, { zoomControl: true, attributionControl: false }).setView(BERMEJO, 15);
        L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
          maxZoom: 19,
        }).addTo(mapRef.current);
        layerRef.current = L.layerGroup().addTo(mapRef.current);
      }
      renderPins(L);
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [results]);

  // Los popups son HTML crudo (fuera de React): tracking de leads por delegación.
  useEffect(() => {
    const el = elRef.current;
    if (!el) return;
    function onClick(e: MouseEvent) {
      const target = (e.target as HTMLElement)?.closest("[data-lead-comercio]");
      const comercioId = target?.getAttribute("data-lead-comercio");
      if (comercioId) registrarLead(comercioId);
    }
    el.addEventListener("click", onClick);
    return () => el.removeEventListener("click", onClick);
  }, []);

  function renderPins(L: any) {
    const layer = layerRef.current;
    if (!layer) return;
    layer.clearLayers();
    const withCoords = results.filter((r) => r.lat != null && r.lng != null);
    const bounds: [number, number][] = [];
    for (const r of withCoords) {
      const icon = L.divIcon({
        className: "",
        html: `<div class="map-pin">${r.verificado ? "★" : "•"}</div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 30],
      });
      const popup = `
        <div class="map-pop">
          <b>${r.nombre}</b>
          <span>${MODALIDAD_LABEL[r.modalidad] ?? r.modalidad}${r.rubro_nombre ? " · " + r.rubro_nombre : ""}</span>
          <div class="map-pop-act">
            <a href="${waLink(r.whatsapp, "Hola, te vi en Encontralo")}" target="_blank" rel="noopener" data-lead-comercio="${r.id}">WhatsApp</a>
            <a href="${comoLlegarHref(r)}" target="_blank" rel="noopener">Cómo llegar</a>
            <a href="/comercios/${r.slug}">Ver comercio</a>
          </div>
        </div>`;
      L.marker([r.lat, r.lng], { icon }).bindPopup(popup).addTo(layer);
      bounds.push([r.lat as number, r.lng as number]);
    }
    if (bounds.length > 1) mapRef.current.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
    else if (bounds.length === 1) mapRef.current.setView(bounds[0], 16);
  }

  const sinCoords = results.filter((r) => r.lat == null || r.lng == null).length;

  return (
    <div>
      <div ref={elRef} className="map-canvas" />
      {sinCoords > 0 && (
        <p style={{ color: "var(--txt-3)", fontSize: 12.5, marginTop: 10 }}>
          {sinCoords} comercio(s) sin ubicación todavía (la comparten por WhatsApp). Mientras tanto aparecen en la lista.
        </p>
      )}
    </div>
  );
}
