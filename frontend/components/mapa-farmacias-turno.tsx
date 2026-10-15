"use client";

/**
 * El mapa de `/farmacias-de-turno`: las farmacias de turno ahora, con el pin
 * destacado y su globo (Llamar, Cómo llegar, Ver ficha).
 *
 * Mismo patrón que los demás mapas: Leaflet se baja aparte (`loadLeaflet`) y
 * sin señal NO rompe la página. Si no baja, se dice y las tarjetas de arriba
 * —que no dependen del mapa— siguen sirviendo con su botón de Cómo llegar.
 */
import { useEffect, useRef, useState } from "react";
import { agregarTiles } from "@/lib/mapa-tiles";
import { loadLeaflet } from "@/lib/mapa-visual";
import { PIN_TURNO, pinTurnoHtml, popupFarmaciaHtml } from "@/lib/mapa-turno";
import { Ic } from "@/components/ic";

export type PinFarmacia = {
  id: string; nombre: string; slug: string;
  direccion: string | null; telefono: string | null;
  lat: number; lng: number;
  /** «hasta mañana 08:00». */
  hasta: string;
};

const BERMEJO: [number, number] = [-22.7361, -64.3433];

export function MapaFarmaciasTurno({ pines, ciudad = null }: {
  pines: PinFarmacia[];
  ciudad?: { tiles_url?: string | null; tiles_atribucion?: string | null; lat?: number | null; lng?: number | null } | null;
}) {
  const elRef = useRef<HTMLDivElement>(null);
  const [estado, setEstado] = useState<"cargando" | "listo" | "falla">("cargando");
  const [sinRed, setSinRed] = useState(false);

  useEffect(() => {
    const act = () => setSinRed(typeof navigator !== "undefined" && navigator.onLine === false);
    act();
    window.addEventListener("online", act);
    window.addEventListener("offline", act);
    return () => { window.removeEventListener("online", act); window.removeEventListener("offline", act); };
  }, []);

  useEffect(() => {
    let cancelado = false;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let map: any = null;
    loadLeaflet()
      .then((L) => {
        if (cancelado || !elRef.current) return;
        const centro: [number, number] = ciudad?.lat != null && ciudad?.lng != null ? [ciudad.lat, ciudad.lng] : BERMEJO;
        map = L.map(elRef.current, { zoomControl: true, attributionControl: true, scrollWheelZoom: false }).setView(centro, 14);
        agregarTiles(L, map, { oscuro: false, ciudad });
        for (const p of pines) {
          const icon = L.divIcon({ className: "", html: pinTurnoHtml(), iconSize: [PIN_TURNO, PIN_TURNO], iconAnchor: [PIN_TURNO / 2, PIN_TURNO / 2] });
          L.marker([p.lat, p.lng], { icon, title: p.nombre, alt: p.nombre, zIndexOffset: 600 })
            .bindPopup(popupFarmaciaHtml(p, p.hasta))
            .addTo(map);
        }
        if (pines.length > 1) map.fitBounds(pines.map((p) => [p.lat, p.lng]), { padding: [50, 50], maxZoom: 16 });
        else if (pines.length === 1) map.setView([pines[0].lat, pines[0].lng], 16);
        setTimeout(() => { if (!cancelado && map) map.invalidateSize(); }, 80);
        setEstado("listo");
      })
      .catch(() => { if (!cancelado) setEstado("falla"); });
    return () => { cancelado = true; if (map) map.remove(); };
    // `pines` llega ya armado desde el servidor: cambia sólo al recargar la página.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (estado === "falla") {
    return (
      <div role="status" className="uk-turno-mapa-falla">
        <Ic n="aviso" s={18} />
        <span>{sinRed ? "Sin conexión: el mapa no se puede cargar." : "El mapa necesita conexión y no se pudo cargar."} Las direcciones y el botón «Cómo llegar» de arriba funcionan igual.</span>
      </div>
    );
  }

  return (
    <div className="uk-turno-mapa">
      <div ref={elRef} className="map-canvas" role="region" aria-label="Mapa con las farmacias de turno ahora" />
      {estado === "cargando" && <p role="status" className="uk-turno-mapa-carga"><Ic n="reloj" s={14} /> Cargando el mapa…</p>}
      {sinRed && estado === "listo" && (
        <p role="status" className="uk-turno-mapa-carga"><Ic n="aviso" s={14} /> Sin conexión: puede que el plano no termine de cargar.</p>
      )}
    </div>
  );
}
