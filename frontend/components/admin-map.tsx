"use client";

// Mapa del finder (admin + publicador). Cada comercio es un pin en su GPS; tocarlo
// abre el editor. Estrategia para la densidad de Bermejo en el celular:
//  - Los comercios DENTRO de un mercado/galería (lugar_id) se colapsan en UN pin
//    "🏬 Nombre (N)"; al tocarlo se abre el DIRECTORIO (lista) de sus puestos.
//  - Los de la calle: pin normal. Tocar un GRUPO por GPS → ZOOM FUERTE (sin patitas).
//  - Al acercar (zoom alto) los pines se agrandan y muestran el nombre → fáciles de tocar.
//  - Si quedan EXACTO en el mismo punto → HOJA con la lista para elegir.
import { agregarTiles } from "@/lib/mapa-tiles";
import { useEffect, useRef, useState } from "react";
import { rubroStyle, loadLeaflet, escapeHtml, FAMILIAS } from "@/lib/mapa-visual";

const BERMEJO: [number, number] = [-22.7361, -64.3433];
const ZOOM_LABEL = 17;   // desde acá los pines se agrandan y muestran el nombre
const PIN = 20;          // chico a propósito: el casco de Bermejo entra mil veces en 460 px de alto

export type AdminPin = {
  id: string; nombre: string; lat: number | null; lng: number | null;
  rubro_slug: string | null; incompleto: boolean;
  lugar_id?: string | null; lugar_nombre?: string | null; lugar_lat?: number | null; lugar_lng?: number | null; lugar_portada_thumb?: string | null;
};

type Hoja = { titulo: string; items: AdminPin[] };

export function AdminMap({ comercios, onSelect }: { comercios: AdminPin[]; onSelect: (id: string) => void }) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  // Sin clusters: en el panel el mapa se usa para IR a un comercio concreto, y
  // un globo que dice "17" obliga a un clic más para descubrir cuál es cuál.
  // El costo es que en zoom bajo los pines se pisan.
  const capaRef = useRef<any>(null);
  const comerciosRef = useRef<AdminPin[]>(comercios);
  const labelOnRef = useRef(false);
  const onSelRef = useRef(onSelect);
  const hojaRef = useRef<(h: Hoja) => void>(() => {});
  const [hoja, setHoja] = useState<Hoja | null>(null);
  comerciosRef.current = comercios;
  onSelRef.current = onSelect;
  hojaRef.current = setHoja;

  // El color y el emoji SIEMPRE son los del rubro, esté completo o no: con
  // 1.126 de 1.248 incompletos, pintarlos a todos de ámbar con un ⚠️ dejaba el
  // mapa de un solo color y sin decir de qué era cada negocio. Lo que falta se
  // avisa con un punto ámbar en la esquina (ver `.ukpin.incompleto` en el CSS).
  function iconoComercio(L: any, c: AdminPin, label: boolean) {
    const style = rubroStyle(c.rubro_slug);
    const inc = c.incompleto ? " incompleto" : "";
    if (label) {
      const html = `<div class="ukpinlab${inc}" style="--pc:${style.color}"><span>${style.emoji}</span><b>${escapeHtml(c.nombre || "Sin nombre")}</b></div>`;
      return L.divIcon({ className: "", html, iconSize: null as any, iconAnchor: [15, 16] });
    }
    const html = `<div class="ukpin mini${inc}" style="--pc:${style.color}"><span class="ukpin-emo">${style.emoji}</span></div>`;
    return L.divIcon({ className: "", html, iconSize: [PIN, PIN], iconAnchor: [PIN / 2, PIN / 2] });
  }

  function iconoLugar(L: any, nombre: string, n: number, portada?: string | null) {
    const head = portada ? `<img class="ukpinlugar-foto" src="${portada}" alt="" loading="lazy" />` : `<span>🏬</span>`;
    const html = `<div class="ukpinlugar">${head}<b>${escapeHtml(nombre)}</b><i>${n}</i></div>`;
    return L.divIcon({ className: "", html, iconSize: null as any, iconAnchor: [15, 16] });
  }

  function render(L: any, fit: boolean) {
    const capa = capaRef.current, map = mapRef.current;
    if (!capa || !map) return;
    const label = map.getZoom() >= ZOOM_LABEL;
    labelOnRef.current = label;
    capa.clearLayers();
    const bounds: [number, number][] = [];
    const markers: any[] = [];

    // Agrupar los que están DENTRO de un mercado/galería; el resto van sueltos.
    const grupos = new Map<string, { nombre: string; lat: number | null; lng: number | null; sumLat: number; sumLng: number; n: number; portada: string | null; items: AdminPin[] }>();
    const sueltos: AdminPin[] = [];
    for (const c of comerciosRef.current) {
      if (c.lugar_id) {
        let g = grupos.get(c.lugar_id);
        if (!g) { g = { nombre: c.lugar_nombre || "Mercado", lat: c.lugar_lat ?? null, lng: c.lugar_lng ?? null, sumLat: 0, sumLng: 0, n: 0, portada: c.lugar_portada_thumb ?? null, items: [] }; grupos.set(c.lugar_id, g); }
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
      const m = L.marker([lat, lng], { icon: iconoLugar(L, g.nombre, items.length, g.portada), zIndexOffset: 500 });
      m.__data = items[0];
      m.on("click", () => hojaRef.current({ titulo: `🏬 ${g.nombre}`, items }));
      markers.push(m);
      bounds.push([lat, lng]);
    }

    // `addLayers` (plural) es de markercluster; un LayerGroup agrega de a uno.
    for (const m of markers) capa.addLayer(m);
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
        agregarTiles(L, map, { oscuro: true });
        capaRef.current = L.layerGroup().addTo(map);
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
  const familiasPresentes = new Set(comercios.map((c) => rubroStyle(c.rubro_slug).color));

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
                  <span className="mh-dot" style={{ background: st.color }}>{st.emoji}</span>
                  <span className="mh-nom">{c.nombre || "Sin nombre"}</span>
                  {c.incompleto && <span className="mh-inc">incompleto</span>}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Referencia de colores: el pin dice el rubro por el emoji, y la FAMILIA
          por el color. Sin esta lista el color es lindo y no significa nada.
          Sólo se muestran las familias que están en el mapa ahora mismo. */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 10px", padding: "8px 4px 0", alignItems: "center" }}>
        {FAMILIAS.filter((f) => familiasPresentes.has(f.color)).map((f) => (
          <span key={f.color} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11.5, color: "var(--txt-3)", whiteSpace: "nowrap" }}>
            <i style={{ width: 9, height: 9, borderRadius: "50%", background: f.color, display: "inline-block" }} />
            {f.nombre}
          </span>
        ))}
        <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11.5, color: "var(--txt-3)", whiteSpace: "nowrap" }}>
          <i style={{ width: 9, height: 9, borderRadius: "50%", background: "transparent", border: "1.5px solid #FFC94D", display: "inline-block" }} />
          punto ámbar = falta completarlo
        </span>
      </div>

      <p style={{ color: "var(--txt-3)", fontSize: 12.5, padding: "6px 4px 0" }}>
        {conCoords} en el mapa · tocá un pin para editar, un <b>🏬 mercado</b> para ver adentro, o un grupo para acercar.
        {sinCoords > 0 && ` · ${sinCoords} sin ubicación.`}
      </p>
    </div>
  );
}
