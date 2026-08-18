"use client";

import { useEffect, useRef, useState } from "react";
import { type ResultadoBusqueda, comoLlegarHref, waLink, MODALIDAD_LABEL } from "@/lib/types";
import { registrarLead } from "@/lib/campo";
import { rubroStyle, loadLeaflet, opcionesCluster, manejarClusterClick } from "@/lib/mapa-visual";

const BERMEJO: [number, number] = [-22.7361, -64.3433];

// Pin del mapa de resultados: color por rubro; los verificados resaltan (anillo).
function pinHtml(r: ResultadoBusqueda): string {
  const style = rubroStyle(r.rubro_slug);
  const cls = r.verificado ? "ukpin destacado" : "ukpin pago";
  const ring = r.verificado ? `<i class="ukpin-ring"></i>` : "";
  return `<div class="${cls}" style="--pc:${style.color}">${ring}<span class="ukpin-emo">${style.emoji}</span></div>`;
}

export function MapResults({ results }: { results: ResultadoBusqueda[] }) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const clusterRef = useRef<any>(null);
  const [hoja, setHoja] = useState<ResultadoBusqueda[] | null>(null);
  const hojaRef = useRef<(items: ResultadoBusqueda[]) => void>(() => {});
  hojaRef.current = setHoja;

  useEffect(() => {
    let cancelled = false;
    loadLeaflet().then((L) => {
      if (cancelled || !elRef.current) return;
      if (!mapRef.current) {
        mapRef.current = L.map(elRef.current, { zoomControl: true, attributionControl: false }).setView(BERMEJO, 15);
        L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
          maxZoom: 19, updateWhenIdle: true, keepBuffer: 2,
        }).addTo(mapRef.current);
        const cluster = L.markerClusterGroup(opcionesCluster(L)).addTo(mapRef.current);
        clusterRef.current = cluster;
        cluster.on("clusterclick", (e: any) => {
          const r = manejarClusterClick(mapRef.current, e);
          if (r.accion === "hoja") hojaRef.current(r.comercios as ResultadoBusqueda[]);
        });
      }
      renderPins(L);
    });
    return () => { cancelled = true; };
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
    const cluster = clusterRef.current;
    if (!cluster) return;
    cluster.clearLayers();
    const withCoords = results.filter((r) => r.lat != null && r.lng != null);
    const bounds: [number, number][] = [];
    const markers: any[] = [];
    for (const r of withCoords) {
      const size = r.verificado ? 34 : 22;
      const icon = L.divIcon({
        className: "", html: pinHtml(r), iconSize: [size, size], iconAnchor: [size / 2, size / 2],
      });
      const popup = `
        <div class="map-pop">
          <b>${r.nombre}</b>
          <span>${MODALIDAD_LABEL[r.modalidad] ?? r.modalidad}${r.rubro_nombre ? " · " + r.rubro_nombre : ""}</span>
          <div class="map-pop-act">
            <a href="${waLink(r.whatsapp, "Hola, te vi en URUKU")}" target="_blank" rel="noopener" data-lead-comercio="${r.id}">WhatsApp</a>
            <a href="${comoLlegarHref(r)}" target="_blank" rel="noopener">Cómo llegar</a>
            <a href="/comercios/${r.slug}">Ver comercio</a>
          </div>
        </div>`;
      const m = L.marker([r.lat, r.lng], { icon, zIndexOffset: r.verificado ? 300 : 0 }).bindPopup(popup);
      m.__data = r;
      markers.push(m);
      bounds.push([r.lat as number, r.lng as number]);
    }
    cluster.addLayers(markers);
    if (bounds.length > 1) mapRef.current.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
    else if (bounds.length === 1) mapRef.current.setView(bounds[0], 16);
  }

  const sinCoords = results.filter((r) => r.lat == null || r.lng == null).length;

  return (
    <div style={{ position: "relative" }}>
      <div ref={elRef} className="map-canvas" />

      {hoja && hoja.length > 0 && (
        <div className="mapa-hoja">
          <div className="mapa-hoja-head">
            <b>{hoja.length} comercios acá</b>
            <button type="button" onClick={() => setHoja(null)} aria-label="Cerrar">✕</button>
          </div>
          <div className="mapa-hoja-list">
            {hoja.map((r) => {
              const st = rubroStyle(r.rubro_slug);
              return (
                <a key={r.id} href={`/comercios/${r.slug}`} className="mapa-hoja-row">
                  <span className="mh-dot" style={{ background: st.color }}>{st.emoji}</span>
                  <span className="mh-nom">{r.nombre}{r.rubro_nombre ? ` · ${r.rubro_nombre}` : ""}</span>
                </a>
              );
            })}
          </div>
        </div>
      )}

      {sinCoords > 0 && (
        <p style={{ color: "var(--txt-3)", fontSize: 12.5, marginTop: 10 }}>
          {sinCoords} comercio(s) sin ubicación todavía (la comparten por WhatsApp). Mientras tanto aparecen en la lista.
        </p>
      )}
    </div>
  );
}
