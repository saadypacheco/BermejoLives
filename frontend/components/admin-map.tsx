"use client";

// Mapa del finder (admin + publicador). Cada comercio es un pin en su GPS; tocarlo
// abre el editor. Estrategia para la densidad de Bermejo en el celular:
//  - Tocar un GRUPO → ZOOM FUERTE (vuela a nivel calle, se separan). Sin "patitas".
//  - Al acercar (zoom alto) los pines se AGRANDAN y muestran el NOMBRE → fáciles de tocar.
//  - Si quedan EXACTO en el mismo punto (el zoom no los separa) → HOJA con la lista.
// Los incompletos van en ámbar ⚠️.
import { useEffect, useRef, useState } from "react";
import { rubroStyle, loadLeaflet, opcionesCluster, manejarClusterClick, escapeHtml } from "@/lib/mapa-visual";

const BERMEJO: [number, number] = [-22.7361, -64.3433];
const ZOOM_LABEL = 17;   // desde acá los pines se agrandan y muestran el nombre

export type AdminPin = {
  id: string; nombre: string; lat: number | null; lng: number | null;
  rubro_slug: string | null; incompleto: boolean;
};

export function AdminMap({ comercios, onSelect }: { comercios: AdminPin[]; onSelect: (id: string) => void }) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const clusterRef = useRef<any>(null);
  const comerciosRef = useRef<AdminPin[]>(comercios);
  const labelOnRef = useRef(false);
  const onSelRef = useRef(onSelect);
  const [hoja, setHoja] = useState<AdminPin[] | null>(null);
  comerciosRef.current = comercios;
  onSelRef.current = onSelect;

  function iconoDe(L: any, c: AdminPin, label: boolean) {
    const style = rubroStyle(c.rubro_slug);
    const emo = c.incompleto ? "⚠️" : style.emoji;
    const inc = c.incompleto ? " incompleto" : "";
    if (label) {
      // pill grande con el nombre: blanco de tap amplio, se lee qué es antes de tocar
      const html = `<div class="ukpinlab${inc}" style="--pc:${style.color}"><span>${emo}</span><b>${escapeHtml(c.nombre || "Sin nombre")}</b></div>`;
      return L.divIcon({ className: "", html, iconSize: null as any, iconAnchor: [15, 16] });
    }
    const html = `<div class="ukpin pago${inc}" style="--pc:${style.color}"><span class="ukpin-emo">${emo}</span></div>`;
    return L.divIcon({ className: "", html, iconSize: [26, 26], iconAnchor: [13, 13] });
  }

  function render(L: any, fit: boolean) {
    const cluster = clusterRef.current, map = mapRef.current;
    if (!cluster || !map) return;
    const label = map.getZoom() >= ZOOM_LABEL;
    labelOnRef.current = label;
    cluster.clearLayers();
    const bounds: [number, number][] = [];
    const markers: any[] = [];
    for (const c of comerciosRef.current) {
      if (c.lat == null || c.lng == null) continue;
      const m = L.marker([c.lat, c.lng], { icon: iconoDe(L, c, label) });
      m.__data = c;
      m.on("click", () => onSelRef.current(c.id));
      markers.push(m);
      bounds.push([c.lat, c.lng]);
    }
    cluster.addLayers(markers);
    if (fit) {
      if (bounds.length > 1) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 16 });
      else if (bounds.length === 1) map.setView(bounds[0], 16);
    }
  }

  useEffect(() => {
    let cancelled = false;
    loadLeaflet().then((L) => {
      if (cancelled || !elRef.current) return;
      if (!mapRef.current) {
        const map = L.map(elRef.current, { attributionControl: false }).setView(BERMEJO, 15);
        mapRef.current = map;
        L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", { maxZoom: 19, updateWhenIdle: true, keepBuffer: 2 }).addTo(map);
        const cluster = L.markerClusterGroup(opcionesCluster(L)).addTo(map);
        clusterRef.current = cluster;
        // Tocar un grupo: zoom fuerte, o hoja si están casi en el mismo punto.
        cluster.on("clusterclick", (e: any) => {
          const r = manejarClusterClick(map, e);
          if (r.accion === "hoja") setHoja(r.comercios as AdminPin[]);
        });
        // Re-render solo al CRUZAR el umbral de etiqueta (no en cada micro-zoom).
        map.on("zoomend", () => {
          if ((map.getZoom() >= ZOOM_LABEL) !== labelOnRef.current) render(L, false);
        });
        setTimeout(() => map.invalidateSize(), 60);
      }
      render(L, true);
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [comercios]);

  const conCoords = comercios.filter((c) => c.lat != null && c.lng != null).length;
  const sinCoords = comercios.length - conCoords;

  return (
    <div style={{ position: "relative" }}>
      <div ref={elRef} style={{ height: 460, borderRadius: 12, overflow: "hidden", border: "1px solid var(--border)" }} />

      {/* Hoja: comercios en el mismo punto (elegís sin fallar el click) */}
      {hoja && hoja.length > 0 && (
        <div className="mapa-hoja">
          <div className="mapa-hoja-head">
            <b>{hoja.length} comercios acá</b>
            <button type="button" onClick={() => setHoja(null)} aria-label="Cerrar">✕</button>
          </div>
          <div className="mapa-hoja-list">
            {hoja.map((c) => {
              const st = rubroStyle(c.rubro_slug);
              return (
                <button key={c.id} type="button" className="mapa-hoja-row" onClick={() => { onSelect(c.id); setHoja(null); }}>
                  <span className="mh-dot" style={{ background: c.incompleto ? "#7a5a12" : st.color }}>{c.incompleto ? "⚠️" : st.emoji}</span>
                  <span className="mh-nom">{c.nombre || "Sin nombre"}</span>
                  {c.incompleto && <span className="mh-inc">incompleto</span>}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <p style={{ color: "var(--txt-3)", fontSize: 12.5, padding: "8px 4px 0" }}>
        {conCoords} en el mapa · tocá un pin para editar (o un grupo para acercar). Los <b style={{ color: "var(--amber)" }}>⚠️ ámbar</b> están incompletos.
        {sinCoords > 0 && ` · ${sinCoords} sin ubicación (no aparecen).`}
      </p>
    </div>
  );
}
