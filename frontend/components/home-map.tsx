"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import type { ComercioMapa } from "@/lib/data";
import { abiertoAhora } from "@/lib/horario";
import { rubroStyle, loadLeaflet } from "@/lib/mapa-visual";

const BERMEJO: [number, number] = [-22.7361, -64.3433];
// Debajo de este zoom (vista de toda la ciudad) los "gratis" se ocultan: solo se
// ven los que pagan (premia el plan). Al acercar aparecen todos. 15 es el zoom
// por defecto, así que en la vista normal se ven todos; solo desaparecen al alejar.
const ZOOM_GRATIS = 14;

type Tier = "gratis" | "pago" | "destacado";
function tierDe(c: ComercioMapa): Tier {
  if (c.destacado) return "destacado";
  if (c.plan && c.plan !== "gratis") return "pago";
  return "gratis";
}
function sizeDe(tier: Tier, isSel: boolean): number {
  if (isSel) return tier === "destacado" ? 46 : 36;
  return tier === "destacado" ? 42 : tier === "pago" ? 20 : 14;
}

function pinHtml(c: ComercioMapa, tier: Tier, isSel: boolean, cerrado: boolean, pct?: number | null): string {
  const style = rubroStyle(c.rubro_slug);
  const cls = ["ukpin", tier, cerrado ? "cerrado" : "", isSel ? "sel" : ""].filter(Boolean).join(" ");
  const badge = pct ? `<b class="ukpin-badge">-${pct}%</b>` : "";
  // El destacado muestra la MINI-FOTO (thumbnail de 20KB) si la tiene; si no, el emoji.
  const conFoto = tier === "destacado" && !!c.portada_thumb_url;
  const inner = conFoto
    ? `<img class="ukpin-photo" src="${c.portada_thumb_url}" alt="" loading="lazy" />`
    : `<span class="ukpin-emo">${style.emoji}</span>`;
  const ring = tier === "destacado" ? `<i class="ukpin-ring"></i>` : "";
  return `<div class="${cls}" style="--pc:${style.color}">${ring}${badge}${inner}</div>`;
}

export function HomeMap({ comercios, onSelect, selectedId, descuentoPorId, center }: {
  comercios: ComercioMapa[]; onSelect?: (c: ComercioMapa) => void; selectedId?: string | null;
  descuentoPorId?: Record<string, number>; center?: [number, number] | null;
}) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const clusterRef = useRef<any>(null);   // gratis + pagos (clusters con número)
  const destRef = useRef<any>(null);      // destacados (nunca colapsan en número; spiderfy si se enciman)
  const selLayerRef = useRef<any>(null);  // el seleccionado, siempre suelto y visible
  const gratisMarkersRef = useRef<any[]>([]);
  const gratisShownRef = useRef(true);
  const LRef = useRef<any>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const pathRef = useRef<SVGPathElement>(null);
  const selCoordRef = useRef<[number, number] | null>(null);
  const selRadiusRef = useRef(18);
  const onSelRef = useRef(onSelect);
  onSelRef.current = onSelect;

  // Re-centrar si cambia la ciudad seleccionada (el mapa se inicializa una sola vez).
  useEffect(() => {
    if (mapRef.current && center) mapRef.current.setView(center, 15);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [center?.[0], center?.[1]]);

  // init una sola vez
  useEffect(() => {
    let cancelled = false;
    loadLeaflet().then((L) => {
      if (cancelled || !elRef.current || mapRef.current) return;
      LRef.current = L;
      const map = L.map(elRef.current, { zoomControl: false, attributionControl: false, scrollWheelZoom: false }).setView(center ?? BERMEJO, 15);
      mapRef.current = map;
      L.control.zoom({ position: "topleft" }).addTo(map);
      const tileUrl = (dark: boolean) =>
        `https://{s}.basemaps.cartocdn.com/${dark ? "dark_all" : "light_all"}/{z}/{x}/{y}{r}.png`;
      const isDark = () => document.getElementById("ukroot")?.getAttribute("data-theme") !== "light";
      const tiles = L.tileLayer(tileUrl(isDark()), {
        maxZoom: 19, updateWhenIdle: true, updateWhenZooming: false, keepBuffer: 2, crossOrigin: true,
      }).addTo(map);
      const root = document.getElementById("ukroot");
      if (root) {
        const obs = new MutationObserver(() => tiles.setUrl(tileUrl(isDark())));
        obs.observe(root, { attributes: true, attributeFilter: ["data-theme"] });
        (map as any)._themeObs = obs;
      }
      // Cluster de gratis+pagos: se agrupan en un círculo con el número al amontonarse.
      clusterRef.current = L.markerClusterGroup({
        maxClusterRadius: 48, showCoverageOnHover: false, spiderfyOnMaxZoom: true, chunkedLoading: true,
        iconCreateFunction: (cl: any) => L.divIcon({
          className: "", iconSize: [38, 38],
          html: `<div class="ukclus">${cl.getChildCount()}</div>`,
        }),
      }).addTo(map);
      // Cluster de destacados: radio chico (solo se juntan si están casi encimados) y
      // se abren en abanico (spiderfy) al tocarlos; nunca se muestran como número común.
      destRef.current = L.markerClusterGroup({
        maxClusterRadius: 22, showCoverageOnHover: false, spiderfyOnMaxZoom: true,
        iconCreateFunction: (cl: any) => L.divIcon({
          className: "", iconSize: [40, 40],
          html: `<div class="ukclus ukclus-dest">⭐${cl.getChildCount()}</div>`,
        }),
      }).addTo(map);
      selLayerRef.current = L.layerGroup().addTo(map);
      pintar();
      map.on("move zoom moveend", drawConnector);
      map.on("zoomend", aplicarZoomProgresivo);
      const ro = new ResizeObserver(() => { map.invalidateSize(); drawConnector(); });
      ro.observe(elRef.current);
      (map as any)._ro = ro;
      const onResize = () => { map.invalidateSize(); drawConnector(); };
      window.addEventListener("resize", onResize);
      (map as any)._onResize = onResize;
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition((pos) => {
          if (cancelled || !mapRef.current) return;
          const here = L.divIcon({ className: "", html: `<div class="here-dot"></div>`, iconSize: [22, 22], iconAnchor: [11, 11] });
          L.marker([pos.coords.latitude, pos.coords.longitude], { icon: here, zIndexOffset: 1000 }).addTo(map);
        }, () => {}, { timeout: 5000, maximumAge: 600000 });
      }
    });
    return () => {
      cancelled = true;
      if (mapRef.current?._onResize) window.removeEventListener("resize", mapRef.current._onResize);
      mapRef.current?._ro?.disconnect();
      mapRef.current?._themeObs?.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // repintar cuando cambian comercios o el seleccionado
  useEffect(() => { pintar(); /* eslint-disable-next-line */ }, [comercios, selectedId, descuentoPorId]);

  function marcador(L: any, c: ComercioMapa, tier: Tier, isSel: boolean) {
    const cerrado = abiertoAhora(c.horario).estado === "cerrado";
    const pct = descuentoPorId?.[c.id];
    const size = sizeDe(tier, isSel);
    const icon = L.divIcon({
      className: "", html: pinHtml(c, tier, isSel, cerrado, pct),
      iconSize: [size, size], iconAnchor: [size / 2, size / 2],
    });
    const m = L.marker([c.lat as number, c.lng as number], {
      icon, zIndexOffset: isSel ? 1200 : tier === "destacado" ? 400 : tier === "pago" ? 100 : 0,
    });
    m.on("click", () => {
      onSelRef.current?.(c);
      const map = mapRef.current;
      const s = map.getSize();
      const pt = map.latLngToContainerPoint([c.lat, c.lng]);
      const target = map.containerPointToLatLng([pt.x, pt.y + s.y * 0.30]);
      map.panTo(target, { animate: true, duration: 0.4 });
    });
    return m;
  }

  function pintar() {
    const L = LRef.current, cluster = clusterRef.current, dest = destRef.current, sel = selLayerRef.current;
    if (!L || !cluster || !dest || !sel) return;
    cluster.clearLayers(); dest.clearLayers(); sel.clearLayers();
    gratisMarkersRef.current = [];
    const pagos: any[] = [];
    let selCoords: [number, number] | null = null;

    for (const c of comercios) {
      if (c.lat == null || c.lng == null) continue;
      const tier = tierDe(c);
      const isSel = c.id === selectedId;
      const m = marcador(L, c, tier, isSel);
      if (isSel) {
        selCoords = [c.lat, c.lng];
        selRadiusRef.current = sizeDe(tier, true) / 2;
        sel.addLayer(m);                       // el seleccionado, siempre suelto
      } else if (tier === "destacado") {
        dest.addLayer(m);
      } else if (tier === "pago") {
        pagos.push(m);
      } else {
        gratisMarkersRef.current.push(m);      // gratis: sujeto al zoom progresivo
      }
    }
    cluster.addLayers(pagos);
    gratisShownRef.current = false;            // se agregan (o no) según el zoom actual
    aplicarZoomProgresivo();

    selCoordRef.current = selCoords;
    drawConnector();
  }

  // Zoom progresivo: los gratis solo se muestran de ZOOM_GRATIS para arriba.
  function aplicarZoomProgresivo() {
    const map = mapRef.current, cluster = clusterRef.current;
    if (!map || !cluster) return;
    const show = map.getZoom() >= ZOOM_GRATIS;
    const arr = gratisMarkersRef.current;
    if (show && !gratisShownRef.current) { cluster.addLayers(arr); gratisShownRef.current = true; }
    else if (!show && gratisShownRef.current) { cluster.removeLayers(arr); gratisShownRef.current = false; }
  }

  // Flecha punteada desde el pin seleccionado hacia la tarjeta (abajo).
  function drawConnector() {
    const map = mapRef.current, svg = svgRef.current, path = pathRef.current;
    if (!map || !svg || !path) return;
    const sc = selCoordRef.current;
    if (!sc) { svg.style.display = "none"; return; }
    const size = map.getSize();
    const p = map.latLngToContainerPoint(sc);
    svg.setAttribute("width", String(size.x));
    svg.setAttribute("height", String(size.y));
    svg.style.display = "block";
    const cardEl = elRef.current?.closest(".mmap")?.querySelector<HTMLElement>(".mcard");
    const mapTop = elRef.current!.getBoundingClientRect().top;
    const x2 = size.x / 2;
    const y2 = cardEl ? cardEl.getBoundingClientRect().top - mapTop - 8 : size.y * 0.52;
    const c1x = p.x + 14, c1y = p.y + (y2 - p.y) * 0.55;
    const c2x = x2 + 14, c2y = p.y + (y2 - p.y) * 0.75;
    const r = selRadiusRef.current;
    path.setAttribute("d", `M ${p.x} ${p.y + r} C ${c1x} ${c1y} ${c2x} ${c2y} ${x2} ${y2}`);
  }

  return (
    <div className="homemap">
      <div ref={elRef} className="homemap-canvas" />
      <svg ref={svgRef} className="hm-connector" style={{ display: "none" }} aria-hidden>
        <defs>
          <marker id="hmArrow" markerUnits="userSpaceOnUse" markerWidth="13" markerHeight="13" refX="9" refY="6" orient="auto">
            <path d="M1,1 L11,6 L1,11 Z" fill="#39ff9e" />
          </marker>
        </defs>
        <path ref={pathRef} fill="none" stroke="#39ff9e" strokeWidth="2" strokeDasharray="4 6" strokeLinecap="round" markerEnd="url(#hmArrow)" />
      </svg>
      <Link href="/buscar" className="hm-btn hm-full">⛶ Ver mapa completo</Link>
    </div>
  );
}
