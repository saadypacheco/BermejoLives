"use client";

// Mapa del finder (admin + publicador). Cada comercio es un pin en su GPS; tocarlo
// abre el editor. Estrategia para la densidad de Bermejo en el celular:
//  - Los comercios DENTRO de un mercado/galería (lugar_id) se colapsan en UN pin
//    "🏬 Nombre (N)"; al tocarlo se abre el DIRECTORIO (lista) de sus puestos.
//  - Los de la calle: pin normal. Tocar un GRUPO por GPS → ZOOM FUERTE (sin patitas).
//  - Al acercar (zoom alto) los pines se agrandan y muestran el nombre → fáciles de tocar.
//  - Si quedan EXACTO en el mismo punto → HOJA con la lista para elegir.
import { useEffect, useRef, useState } from "react";
import { rubroStyle, loadLeaflet, opcionesCluster, manejarClusterClick, escapeHtml } from "@/lib/mapa-visual";

const BERMEJO: [number, number] = [-22.7361, -64.3433];
const ZOOM_LABEL = 17;   // desde acá los pines se agrandan y muestran el nombre

export type AdminPin = {
  id: string; nombre: string; lat: number | null; lng: number | null;
  rubro_slug: string | null; incompleto: boolean;
  lugar_id?: string | null; lugar_nombre?: string | null; lugar_lat?: number | null; lugar_lng?: number | null;
};

type Hoja = { titulo: string; items: AdminPin[] };

export function AdminMap({ comercios, onSelect }: { comercios: AdminPin[]; onSelect: (id: string) => void }) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const clusterRef = useRef<any>(null);
  const comerciosRef = useRef<AdminPin[]>(comercios);
  const labelOnRef = useRef(false);
  const onSelRef = useRef(onSelect);
  const hojaRef = useRef<(h: Hoja) => void>(() => {});
  const [hoja, setHoja] = useState<Hoja | null>(null);
  comerciosRef.current = comercios;
  onSelRef.current = onSelect;
  hojaRef.current = setHoja;

  function iconoComercio(L: any, c: AdminPin, label: boolean) {
    const style = rubroStyle(c.rubro_slug);
    const emo = c.incompleto ? "⚠️" : style.emoji;
    const inc = c.incompleto ? " incompleto" : "";
    if (label) {
      const html = `<div class="ukpinlab${inc}" style="--pc:${style.color}"><span>${emo}</span><b>${escapeHtml(c.nombre || "Sin nombre")}</b></div>`;
      return L.divIcon({ className: "", html, iconSize: null as any, iconAnchor: [15, 16] });
    }
    const html = `<div class="ukpin pago${inc}" style="--pc:${style.color}"><span class="ukpin-emo">${emo}</span></div>`;
    return L.divIcon({ className: "", html, iconSize: [26, 26], iconAnchor: [13, 13] });
  }

  function iconoLugar(L: any, nombre: string, n: number) {
    const html = `<div class="ukpinlugar"><span>🏬</span><b>${escapeHtml(nombre)}</b><i>${n}</i></div>`;
    return L.divIcon({ className: "", html, iconSize: null as any, iconAnchor: [15, 16] });
  }

  function render(L: any, fit: boolean) {
    const cluster = clusterRef.current, map = mapRef.current;
    if (!cluster || !map) return;
    const label = map.getZoom() >= ZOOM_LABEL;
    labelOnRef.current = label;
    cluster.clearLayers();
    const bounds: [number, number][] = [];
    const markers: any[] = [];

    // Agrupar los que están DENTRO de un mercado/galería; el resto van sueltos.
    const grupos = new Map<string, { nombre: string; lat: number | null; lng: number | null; sumLat: number; sumLng: number; n: number; items: AdminPin[] }>();
    const sueltos: AdminPin[] = [];
    for (const c of comerciosRef.current) {
      if (c.lugar_id) {
        let g = grupos.get(c.lugar_id);
        if (!g) { g = { nombre: c.lugar_nombre || "Mercado", lat: c.lugar_lat ?? null, lng: c.lugar_lng ?? null, sumLat: 0, sumLng: 0, n: 0, items: [] }; grupos.set(c.lugar_id, g); }
        g.items.push(c);
        if (c.lat != null && c.lng != null) { g.sumLat += c.lat; g.sumLng += c.lng; g.n += 1; }
      } else if (c.lat != null && c.lng != null) {
        sueltos.push(c);
      }
    }

    for (const c of sueltos) {
      const m = L.marker([c.lat as number, c.lng as number], { icon: iconoComercio(L, c, label) });
      m.__data = c;
      m.on("click", () => onSelRef.current(c.id));
      markers.push(m);
      bounds.push([c.lat as number, c.lng as number]);
    }

    for (const g of grupos.values()) {
      // Posición del lugar: su punto propio, o el centroide de sus puestos.
      const lat = g.lat ?? (g.n ? g.sumLat / g.n : null);
      const lng = g.lng ?? (g.n ? g.sumLng / g.n : null);
      if (lat == null || lng == null) continue;
      const items = g.items;
      const m = L.marker([lat, lng], { icon: iconoLugar(L, g.nombre, items.length), zIndexOffset: 500 });
      m.__data = items[0];   // fallback si llegara a caer en un cluster
      m.on("click", () => hojaRef.current({ titulo: `🏬 ${g.nombre}`, items }));
      markers.push(m);
      bounds.push([lat, lng]);
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
        cluster.on("clusterclick", (e: any) => {
          const r = manejarClusterClick(map, e);
          if (r.accion === "hoja") hojaRef.current({ titulo: `${r.comercios.length} comercios acá`, items: r.comercios as AdminPin[] });
        });
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

  const conCoords = comercios.filter((c) => (c.lat != null && c.lng != null) || c.lugar_id).length;
  const sinCoords = comercios.length - conCoords;

  return (
    <div style={{ position: "relative" }}>
      <div ref={elRef} style={{ height: 460, borderRadius: 12, overflow: "hidden", border: "1px solid var(--border)" }} />

      {hoja && hoja.items.length > 0 && (
        <div className="mapa-hoja">
          <div className="mapa-hoja-head">
            <b>{hoja.titulo} · {hoja.items.length}</b>
            <button type="button" onClick={() => setHoja(null)} aria-label="Cerrar">✕</button>
          </div>
          <div className="mapa-hoja-list">
            {hoja.items.map((c) => {
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
        {conCoords} en el mapa · tocá un pin para editar, un <b>🏬 mercado</b> para ver adentro, o un grupo para acercar. Los <b style={{ color: "var(--amber)" }}>⚠️ ámbar</b> están incompletos.
        {sinCoords > 0 && ` · ${sinCoords} sin ubicación.`}
      </p>
    </div>
  );
}
