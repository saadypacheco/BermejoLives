"use client";

// Mapa del admin (D): cada comercio es un pin en su ubicación GPS; al tocarlo se
// abre el modal de edición. Útil para los comercios SIN NOMBRE cargados en campo:
// los ubicás por dónde están, no por cómo se llaman. Los incompletos van en ámbar ⚠️.
import { useEffect, useRef } from "react";
import { rubroStyle, loadLeaflet } from "@/lib/mapa-visual";

const BERMEJO: [number, number] = [-22.7361, -64.3433];

export type AdminPin = {
  id: string; nombre: string; lat: number | null; lng: number | null;
  rubro_slug: string | null; incompleto: boolean;
};

export function AdminMap({ comercios, onSelect }: { comercios: AdminPin[]; onSelect: (id: string) => void }) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const clusterRef = useRef<any>(null);
  const onSelRef = useRef(onSelect);
  onSelRef.current = onSelect;

  useEffect(() => {
    let cancelled = false;
    loadLeaflet().then((L) => {
      if (cancelled || !elRef.current) return;
      if (!mapRef.current) {
        const map = L.map(elRef.current, { attributionControl: false }).setView(BERMEJO, 15);
        mapRef.current = map;
        L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", { maxZoom: 19, updateWhenIdle: true, keepBuffer: 2 }).addTo(map);
        clusterRef.current = L.markerClusterGroup({
          maxClusterRadius: 46, showCoverageOnHover: false, spiderfyOnMaxZoom: true, chunkedLoading: true,
          iconCreateFunction: (cl: any) => L.divIcon({ className: "", iconSize: [38, 38], html: `<div class="ukclus">${cl.getChildCount()}</div>` }),
        }).addTo(map);
        setTimeout(() => map.invalidateSize(), 60);   // el contenedor puede asentar su alto tras montar
      }
      render(L);
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [comercios]);

  function render(L: any) {
    const cluster = clusterRef.current;
    if (!cluster) return;
    cluster.clearLayers();
    const bounds: [number, number][] = [];
    const markers: any[] = [];
    for (const c of comercios) {
      if (c.lat == null || c.lng == null) continue;
      const style = rubroStyle(c.rubro_slug);
      const cls = c.incompleto ? "ukpin pago incompleto" : "ukpin pago";
      const emo = c.incompleto ? "⚠️" : style.emoji;
      const html = `<div class="${cls}" style="--pc:${style.color}"><span class="ukpin-emo">${emo}</span></div>`;
      const icon = L.divIcon({ className: "", html, iconSize: [26, 26], iconAnchor: [13, 13] });
      const m = L.marker([c.lat, c.lng], { icon }).bindTooltip(c.nombre || "Sin nombre", { direction: "top", offset: [0, -10] });
      m.on("click", () => onSelRef.current(c.id));
      markers.push(m);
      bounds.push([c.lat, c.lng]);
    }
    cluster.addLayers(markers);
    if (bounds.length > 1) mapRef.current.fitBounds(bounds, { padding: [30, 30], maxZoom: 16 });
    else if (bounds.length === 1) mapRef.current.setView(bounds[0], 16);
  }

  const conCoords = comercios.filter((c) => c.lat != null && c.lng != null).length;

  return (
    <div>
      <div ref={elRef} style={{ height: 460, borderRadius: 12, overflow: "hidden", border: "1px solid var(--border)" }} />
      <p style={{ color: "var(--txt-3)", fontSize: 12.5, padding: "8px 4px 0" }}>
        {conCoords} en el mapa · tocá un pin para editar. Los <b style={{ color: "var(--amber)" }}>⚠️ ámbar</b> están incompletos.
        {comercios.length - conCoords > 0 && ` · ${comercios.length - conCoords} sin ubicación (no aparecen).`}
      </p>
    </div>
  );
}
