"use client";

/**
 * El mapa de «Qué hay acá»: el punto del agente con su precisión, el círculo de
 * 100 m y un pin con la miniatura de la portada de cada local cargado cerca.
 *
 * Leaflet se carga aparte (lib/mapa-visual.ts `loadLeaflet`) y sin SSR, igual
 * que el resto de los mapas. SIN SEÑAL el mapa no puede romper nada: si Leaflet
 * no baja se muestra un aviso y la lista de abajo sigue funcionando; si bajó
 * pero no hay planos (teselas), quedan el punto, el círculo y los pines sobre
 * gris, con un aviso.
 */
import { useEffect, useRef, useState } from "react";
import { agregarTiles } from "@/lib/mapa-tiles";
import { loadLeaflet, escapeHtml } from "@/lib/mapa-visual";
import { SVG_COMERCIOS } from "@/lib/iconos-mapa";
import { PLAN_CFG } from "@/components/sello-plan";
import type { EstadoPlan } from "@/lib/campo";
import { Ic } from "@/components/ic";

const BERMEJO: [number, number] = [-22.7361, -64.3433];
/** El círculo de referencia: «a esta distancia es la puerta de al lado». */
export const RADIO_CIRCULO_M = 100;
const PIN = 46;

export type PinAca = {
  id: string; nombre: string; lat: number; lng: number;
  thumb: string | null; plan?: EstadoPlan | null;
};

export type PosicionAca = { lat: number; lng: number; acc: number };

export function MapaAca({ aqui, pines, encuadreM, onSelect }: {
  aqui: PosicionAca | null;
  pines: PinAca[];
  /** Hasta dónde se acerca el mapa al ubicarse (150 m, o 400 al ampliar). */
  encuadreM: number;
  onSelect: (id: string) => void;
}) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);       // eslint-disable-line @typescript-eslint/no-explicit-any
  const Lref = useRef<any>(null);         // eslint-disable-line @typescript-eslint/no-explicit-any
  const capaRef = useRef<any>(null);      // eslint-disable-line @typescript-eslint/no-explicit-any
  const ajusteRef = useRef("");
  const onSelRef = useRef(onSelect);
  onSelRef.current = onSelect;
  const [listo, setListo] = useState(false);
  const [falla, setFalla] = useState(false);
  const [sinPlano, setSinPlano] = useState(false);

  // Alta del mapa, una sola vez.
  useEffect(() => {
    let cancelado = false;
    loadLeaflet()
      .then((L) => {
        if (cancelado || !elRef.current || mapRef.current) return;
        const map = L.map(elRef.current, { attributionControl: false, zoomControl: true }).setView(BERMEJO, 16);
        L.control.attribution({ prefix: false }).addTo(map);
        const tiles = agregarTiles(L, map, { oscuro: true });
        tiles.on("tileerror", () => setSinPlano(true));
        tiles.on("tileload", () => setSinPlano(false));
        capaRef.current = L.layerGroup().addTo(map);
        mapRef.current = map; Lref.current = L;
        setTimeout(() => { if (mapRef.current === map) map.invalidateSize(); }, 60);
        setListo(true);
      })
      .catch(() => { if (!cancelado) setFalla(true); });
    return () => {
      cancelado = true;
      if (mapRef.current) { mapRef.current.remove(); mapRef.current = null; capaRef.current = null; }
    };
  }, []);

  // Dibujo: tu punto, la precisión, el círculo y los pines.
  useEffect(() => {
    const L = Lref.current, map = mapRef.current, capa = capaRef.current;
    if (!listo || !L || !map || !capa) return;
    capa.clearLayers();

    if (aqui) {
      if (aqui.acc > 0 && aqui.acc <= 1500) {
        L.circle([aqui.lat, aqui.lng], { radius: aqui.acc, color: "#2563eb", weight: 1, dashArray: "4 4", fillColor: "#3b82f6", fillOpacity: 0.12, interactive: false }).addTo(capa);
      }
      L.circle([aqui.lat, aqui.lng], { radius: RADIO_CIRCULO_M, color: "#15985e", weight: 2, dashArray: "6 6", fillOpacity: 0, interactive: false }).addTo(capa);
      L.marker([aqui.lat, aqui.lng], {
        interactive: false, zIndexOffset: 900, keyboard: false,
        icon: L.divIcon({ className: "", html: '<div class="qha-yo" role="img" aria-label="Tu ubicación"></div>', iconSize: [20, 20], iconAnchor: [10, 10] }),
      }).addTo(capa);
    }

    for (const p of pines) {
      const color = p.plan && PLAN_CFG[p.plan] ? PLAN_CFG[p.plan].color : "var(--neon)";
      const cuerpo = p.thumb
        ? `<img src="${escapeHtml(p.thumb)}" alt="" onerror="this.style.display='none'" />`
        : `<span class="qha-pin-ic">${SVG_COMERCIOS}</span>`;
      const icon = L.divIcon({
        className: "",
        html: `<div class="qha-pin" style="--pc:${color}">${cuerpo}</div>`,
        iconSize: [PIN, PIN], iconAnchor: [PIN / 2, PIN / 2],
      });
      const m = L.marker([p.lat, p.lng], { icon, title: p.nombre || "Sin nombre", alt: p.nombre || "Sin nombre", riseOnHover: true });
      m.on("click", () => onSelRef.current(p.id));
      m.addTo(capa);
    }
  }, [listo, aqui, pines]);

  // Encuadre: sólo cuando cambia dónde estoy o cuánto quiero ver. Si se refrescara
  // con cada actualización de la lista, el mapa saltaría mientras el agente lo mueve.
  useEffect(() => {
    const L = Lref.current, map = mapRef.current;
    if (!listo || !L || !map) return;
    const clave = aqui ? `${aqui.lat.toFixed(5)},${aqui.lng.toFixed(5)},${encuadreM}` : `sin,${pines.length > 0}`;
    if (ajusteRef.current === clave) return;
    ajusteRef.current = clave;
    if (aqui) {
      // Un cuadrado de lado 2×encuadreM centrado en el agente. (No se usa
      // `L.circle().getBounds()`: ese necesita que el círculo ya esté en el mapa.)
      // Con 30% de margen: un pin tiene tamaño y el de la orilla no tiene que quedar cortado.
      const r = encuadreM * 1.3;
      const dLat = r / 110540;
      const dLng = r / (111320 * Math.cos((aqui.lat * Math.PI) / 180));
      map.fitBounds([[aqui.lat - dLat, aqui.lng - dLng], [aqui.lat + dLat, aqui.lng + dLng]], { padding: [8, 8], animate: false });
    } else if (pines.length > 0) {
      map.fitBounds(pines.map((p) => [p.lat, p.lng]), { padding: [30, 30], maxZoom: 16, animate: false });
    }
  }, [listo, aqui, pines, encuadreM]);

  if (falla) {
    return (
      <div role="status" style={{ height: 150, borderRadius: 14, border: "1px dashed var(--stroke)", display: "grid", placeItems: "center", textAlign: "center", padding: 16, color: "var(--txt-3)", fontSize: 13 }}>
        <span><Ic n="aviso" s={16} /> El mapa necesita conexión y no se pudo cargar. La lista de abajo funciona igual.</span>
      </div>
    );
  }

  return (
    <div style={{ position: "relative" }}>
      <div ref={elRef} style={{ height: 300, borderRadius: 14, overflow: "hidden", border: "1px solid var(--stroke)", background: "#e5e7eb" }}
           aria-label="Mapa de los locales cargados cerca" />
      {!listo && (
        <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", color: "#475569", fontSize: 13, pointerEvents: "none" }}>
          <span><Ic n="reloj" s={14} /> Cargando el mapa…</span>
        </div>
      )}
      {sinPlano && (
        <div role="status" style={{ position: "absolute", left: 8, right: 8, bottom: 8, zIndex: 500, padding: "6px 10px", borderRadius: 10, background: "rgba(10,13,20,.88)", color: "var(--amber)", fontSize: 12 }}>
          <Ic n="aviso" s={13} /> Sin señal: el mapa no baja los planos, pero tu punto y los locales siguen acá.
        </div>
      )}
    </div>
  );
}
