"use client";

import { useEffect, useRef, useState } from "react";
import { agregarTiles } from "@/lib/mapa-tiles";
import Link from "next/link";
import type { ComercioMapa } from "@/lib/data";
import { abiertoAhora } from "@/lib/horario";
import { rubroStyle, loadLeaflet, escapeHtml } from "@/lib/mapa-visual";

import { adornoHTML, MEDIDAS, ZOOM_MIN_ADORNOS, type Adorno } from "@/lib/adornos";
import { getAdornosMapa } from "@/lib/data";

const BERMEJO: [number, number] = [-22.7361, -64.3433];

type Tier = "gratis" | "pago" | "destacado";
type Hoja = { titulo: string; portada?: string | null; video?: string | null; items: ComercioMapa[] };

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
  const conFoto = tier === "destacado" && !!c.portada_thumb_url;
  const inner = conFoto
    ? `<img class="ukpin-photo" src="${c.portada_thumb_url}" alt="" loading="lazy" />`
    : `<span class="ukpin-emo">${style.emoji}</span>`;
  const ring = tier === "destacado" ? `<i class="ukpin-ring"></i>` : "";
  return `<div class="${cls}" style="--pc:${style.color}">${ring}${badge}${inner}</div>`;
}

export function HomeMap({ comercios, onSelect, selectedId, descuentoPorId, center, ciudad, mostrarTodos = false }: {
  comercios: ComercioMapa[]; onSelect?: (c: ComercioMapa) => void; selectedId?: string | null;
  /** El comprador buscó o eligió una categoría: ahí quiere ver TODO lo que
   *  coincide, esté donde esté el zoom. */
  mostrarTodos?: boolean;
  descuentoPorId?: Record<string, number>; center?: [number, number] | null;
  /** La ciudad mostrada: decide de dónde salen los tiles (columna en `ciudades`). */
  ciudad?: { tiles_url?: string | null; tiles_atribucion?: string | null } | null;
}) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const clusterRef = useRef<any>(null);
  const polyLayerRef = useRef<any>(null);   // polígonos de las manzanas (mercados)
  const adornoLayerRef = useRef<any>(null); // chalanas y lapachos (pura decoración)
  const adornosRef = useRef<Adorno[]>([]);
  const markerByIdRef = useRef<Map<string, any>>(new Map());
  const LRef = useRef<any>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const pathRef = useRef<SVGPathElement>(null);
  // Los comercios y los descuentos VIGENTES, en refs.
  //
  // `pintar()` se llama desde dos lados: un efecto que corre con cada cambio de
  // props, y el manejador de "zoomend", que se registra UNA sola vez al crear
  // el mapa. Ese manejador se queda con el `pintar` de aquel primer render, y
  // ese `pintar` se quedó con la lista de comercios de entonces — la completa,
  // sin filtrar. Resultado: filtrás por categoría, hacés zoom, y vuelven todos.
  //
  // El adorno ya usaba este patrón (`adornosRef`) por la misma razón; a los
  // comercios les faltaba. Leyendo del ref, las dos vías dibujan lo mismo.
  const comerciosRef = useRef(comercios);
  // Misma razón que `comerciosRef`: el manejador de `zoomend` se registra una
  // sola vez y se queda con el valor del primer render.
  const todosRef = useRef(mostrarTodos);
  const descuentosRef = useRef(descuentoPorId);
  const selIdRef = useRef<string | null | undefined>(selectedId);
  const selRadiusRef = useRef(18);
  const onSelRef = useRef(onSelect);
  const [hoja, setHoja] = useState<Hoja | null>(null);
  // Cuántos comercios quedaron fuera de la vista de descubrimiento. Sin
  // decirlo, un mapa con seis pines sobre una ciudad se lee como "no hay
  // nada acá", que es lo contrario de lo que pasa.
  const [ocultos, setOcultos] = useState(0);
  const hojaRef = useRef<(h: Hoja) => void>(() => {});
  onSelRef.current = onSelect;
  comerciosRef.current = comercios;
  todosRef.current = mostrarTodos;
  descuentosRef.current = descuentoPorId;
  selIdRef.current = selectedId;
  hojaRef.current = setHoja;

  useEffect(() => {
    if (mapRef.current && center) mapRef.current.setView(center, 15);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [center?.[0], center?.[1]]);

  useEffect(() => {
    let cancelled = false;
    loadLeaflet().then((L) => {
      if (cancelled || !elRef.current || mapRef.current) return;
      LRef.current = L;
      // La atribución vuelve a estar: la licencia de OpenStreetMap la exige
      // donde se muestren sus tiles, y no es negociable.
      const map = L.map(elRef.current, { zoomControl: false, attributionControl: true, scrollWheelZoom: false }).setView(center ?? BERMEJO, 15);
      mapRef.current = map;
      L.control.zoom({ position: "topleft" }).addTo(map);
      const isDark = () => document.getElementById("ukroot")?.getAttribute("data-theme") !== "light";
      const tiles = agregarTiles(L, map, { oscuro: isDark(), ciudad });
      // El tema ya no cambia la URL del tile sino una CLASE: OSM publica un
      // solo estilo y el oscuro sale de un filtro CSS. Cambiar la clase no
      // vuelve a descargar nada; cambiar la URL descargaba el mapa entero de
      // nuevo en cada cambio de tema.
      const root = document.getElementById("ukroot");
      if (root) {
        const obs = new MutationObserver(() => {
          const el = tiles.getContainer();
          if (el) el.classList.toggle("uk-tiles-oscuro", isDark());
        });
        obs.observe(root, { attributes: true, attributeFilter: ["data-theme"] });
        (map as any)._themeObs = obs;
      }
      // Panel propio para los adornos, por DEBAJO de todo lo demás y sordo al
      // mouse: el mapa existe para mostrar comercios, así que una chalana nunca
      // puede taparle el clic a un local ni robarle la atención.
      map.createPane("adornos");
      map.getPane("adornos").style.zIndex = "350";      // < overlayPane (400) < markerPane (600)
      map.getPane("adornos").style.pointerEvents = "none";
      adornoLayerRef.current = L.layerGroup().addTo(map);

      polyLayerRef.current = L.layerGroup().addTo(map);   // manzanas por debajo de los pines
      // Locales a la calle: pines INDIVIDUALES (sin agrupador, mapa lleno de puntos por
      // rubro). Los mercados/galerías se muestran como un pin 🏬 que abre el directorio.
      const layer = L.layerGroup().addTo(map);
      clusterRef.current = layer;
      pintar();
      encuadrarTodo(map, L);
      map.on("move zoom moveend", drawConnector);
      // Las etiquetas de mercados aparecen y desaparecen según el zoom, así
      // que hay que repintar cuando termina de hacer zoom.
      map.on("zoomend", () => { pintar(); pintarAdornos(); });

      // Se cargan una sola vez y no bloquean nada: si fallan, el mapa queda sin
      // decoración y con todos sus comercios, que es lo que importa.
      getAdornosMapa().then((items) => {
        adornosRef.current = items;
        pintarAdornos();
      }).catch(() => {});
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
          L.marker([pos.coords.latitude, pos.coords.longitude], { icon: here, zIndexOffset: 1000 })
            .bindTooltip("Estás acá", { direction: "top", offset: [0, -8], className: "here-tip" })
            .addTo(map);
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

  useEffect(() => { pintar(); /* eslint-disable-next-line */ }, [comercios, selectedId, descuentoPorId, mostrarTodos]);

  function marcador(L: any, c: ComercioMapa, tier: Tier, isSel: boolean) {
    const cerrado = abiertoAhora(c.horario).estado === "cerrado";
    const pct = descuentosRef.current?.[c.id];
    const size = sizeDe(tier, isSel);
    const icon = L.divIcon({
      className: "", html: pinHtml(c, tier, isSel, cerrado, pct),
      iconSize: [size, size], iconAnchor: [size / 2, size / 2],
    });
    const m = L.marker([c.lat as number, c.lng as number], {
      icon, zIndexOffset: isSel ? 1200 : tier === "destacado" ? 400 : tier === "pago" ? 100 : 0,
    });
    m.__data = c;
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

  // Los mercados y galerías son una REFERENCIA para ubicarse, no el contenido.
  // Con la píldora violeta tapaban el mapa y escondían justamente lo que la
  // persona vino a ver: los locales. Ahora sólo aparecen de cerca, y como texto
  // discreto.
  /**
   * Dibuja las chalanas y los lapachos. Van en su propio panel, por debajo de
   * los pines y sin recibir clics, así que no pueden competir con un comercio.
   *
   * Se dibujan desde el arranque. Antes aparecían recién al acercarse, con el
   * criterio de que de lejos el mapa tenía que ser comercios y nada más. Pero de
   * lejos ya no hay 886 comercios —hay unos pocos destacados— y sin las chalanas
   * y los lapachos ese primer mapa queda vacío. Son lo que lo hace Bermejo.
   */
  function pintarAdornos() {
    const L = LRef.current, map = mapRef.current, capa = adornoLayerRef.current;
    if (!L || !map || !capa) return;
    capa.clearLayers();
    if (map.getZoom() < ZOOM_MIN_ADORNOS) return;

    adornosRef.current.forEach((a, i) => {
      if (a.lat == null || a.lng == null) return;
      const m = MEDIDAS[a.tipo] ?? MEDIDAS.lapacho;
      const icono = L.divIcon({
        className: "",
        html: adornoHTML(a, i),
        iconSize: [m.w, m.h],
        iconAnchor: [m.w / 2, m.anclaY],
      });
      capa.addLayer(L.marker([a.lat, a.lng], {
        icon: icono,
        pane: "adornos",
        interactive: false,       // no roba el clic al comercio que esté debajo
        keyboard: false,
      }));
    });
  }

  /** El mapa arranca vacío de comercios, a propósito.
   *
   * 886 pines sobre Bermejo no son un mapa, son una mancha — y la mancha
   * aparece justo cuando alguien entra por primera vez y todavía no sabe qué
   * busca. Mostrarlo todo no informa: satura.
   *
   * No se revela por zoom. Se probó y no alcanza: acercarse no es decir qué se
   * quiere, así que a zoom 16 volvía la misma mancha, sólo que de un barrio.
   * Lo que revela los comercios es el FILTRO — buscar, elegir una categoría,
   * pedir sólo ofertas. Recién ahí hay una pregunta que contestar.
   *
   * Mientras tanto quedan los adornos, y los destacados o los que pagan. Eso
   * convierte a la primera vista en un lugar con cupo, que es lo que se vende:
   * hoy está casi vacía y se llena sola a medida que alguien contrate.
   */
  const ZOOM_MIN_LUGARES = 0;

  function iconoLugar(L: any, nombre: string) {
    const html = `<div class="ukpinlugar">${escapeHtml(nombre)}</div>`;
    return L.divIcon({ className: "", html, iconSize: null as any, iconAnchor: [0, 8] });
  }

  /** Encuadra el mapa para que entren TODOS los locales.
   *
   * La primera impresión tiene que ser "acá hay muchos negocios". Con un centro
   * y zoom fijos se veía un pedazo de Bermejo con cuatro pines, aunque hubiera
   * 161 cargados: el trabajo del recorrido quedaba invisible.
   *
   * maxZoom evita el efecto contrario — que con dos comercios muy juntos el mapa
   * se acerque tanto que se pierda la referencia de dónde está uno parado.
   */
  function encuadrarTodo(map: any, L: any) {
    const puntos = comercios
      .filter((c) => c.lat != null && c.lng != null)
      .map((c) => [c.lat as number, c.lng as number] as [number, number]);
    if (puntos.length < 2) return;   // con uno solo, el centro por defecto sirve
    try {
      map.fitBounds(L.latLngBounds(puntos), { padding: [36, 36], maxZoom: 16, animate: false });
    } catch {
      /* si las coordenadas son inválidas se queda con la vista por defecto */
    }
  }

  function pintar() {
    const L = LRef.current, layer = clusterRef.current, map = mapRef.current;
    if (!L || !layer || !map) return;
    // Sin filtro puesto: sólo los destacados y los que pagan. Los adornos van
    // igual — son los que hacen que el mapa se lea como Bermejo y no como una
    // grilla de calles vacía.
    const descubrimiento = !todosRef.current;
    let saltados = 0;
    layer.clearLayers();
    polyLayerRef.current?.clearLayers();
    markerByIdRef.current = new Map();
    // Agrupar los que están dentro de un mercado/galería (pin 🏬 → directorio); el
    // resto se dibujan como pines INDIVIDUALES (sin agrupador).
    const grupos = new Map<string, { nombre: string; lat: number | null; lng: number | null; sumLat: number; sumLng: number; n: number; portada: string | null; video: string | null; poligono: [number, number][] | null; items: ComercioMapa[] }>();

    for (const c of comerciosRef.current) {
      if (c.lat == null || c.lng == null) continue;
      if (c.lugar_id) {
        let g = grupos.get(c.lugar_id);
        if (!g) { g = { nombre: c.lugar_nombre || "Mercado", lat: c.lugar_lat, lng: c.lugar_lng, sumLat: 0, sumLng: 0, n: 0, portada: c.lugar_portada_thumb_url, video: c.lugar_video_url, poligono: c.lugar_poligono, items: [] }; grupos.set(c.lugar_id, g); }
        g.items.push(c); g.sumLat += c.lat; g.sumLng += c.lng; g.n += 1;
        // NO se hace `continue`: el comercio se dibuja igual como pin propio.
        // El pin del mercado queda como REFERENCIA (nombre + conteo), pero los
        // locales tienen que verse en el mapa. Mientras sean pocos esto es lo
        // más útil; si un mercado se llena, conviene volver a esconderlos por
        // debajo de cierto zoom.
      }
      const tier = tierDe(c);
      // El seleccionado se dibuja siempre: si el comprador tocó un resultado y
      // su pin no aparece, el mapa parece roto.
      const isSel = c.id === selIdRef.current;
      if (descubrimiento && tier === "gratis" && !isSel) { saltados++; continue; }
      const m = marcador(L, c, tier, isSel);
      markerByIdRef.current.set(c.id, m);
      if (isSel) selRadiusRef.current = sizeDe(tier, true) / 2;
      layer.addLayer(m);
    }

    for (const g of grupos.values()) {
      const lat = g.lat ?? (g.n ? g.sumLat / g.n : null);
      const lng = g.lng ?? (g.n ? g.sumLng / g.n : null);
      if (lat == null || lng == null) continue;
      const items = g.items;
      if (g.poligono && g.poligono.length >= 3 && polyLayerRef.current) {
        L.polygon(g.poligono, { color: "#8b5cf6", weight: 2, fillColor: "#8b5cf6", fillOpacity: 0.12 }).addTo(polyLayerRef.current);
      }
      // Por debajo del zoom mínimo no se dibuja: de lejos sólo se ven los locales.
      // El pin del mercado lleva su nombre escrito y ocupa más que un punto:
      // con quince galerías la vista de arranque vuelve a llenarse de texto.
      // También espera al filtro.
      if (descubrimiento) continue;
      if ((mapRef.current?.getZoom() ?? 0) < ZOOM_MIN_LUGARES) continue;
      const m = L.marker([lat, lng], { icon: iconoLugar(L, g.nombre), zIndexOffset: 400 });
      m.__data = items[0];
      // Tocar el mercado ENCUADRA sus locales en vez de abrir un listado: los
      // pines ya están en el mapa, así que lo útil es acercarse y verlos.
      m.on("click", () => {
        const map = mapRef.current;
        const puntos = items.filter((c) => c.lat != null && c.lng != null)
                            .map((c) => [c.lat as number, c.lng as number] as [number, number]);
        if (!map || puntos.length === 0) {
          hojaRef.current({ titulo: `🏬 ${g.nombre}`, portada: g.portada, video: g.video, items });
          return;
        }
        if (puntos.length === 1) {
          // Un solo local: acercarse a él y seleccionarlo, sin pasos de más.
          map.setView(puntos[0], Math.max(map.getZoom(), 18), { animate: true });
          onSelRef.current?.(items[0]);
          return;
        }
        map.fitBounds(L.latLngBounds(puntos), { padding: [60, 60], maxZoom: 19, animate: true });
      });
      layer.addLayer(m);
    }

    drawConnector();
    setOcultos(saltados);
  }

  function drawConnector() {
    const map = mapRef.current, svg = svgRef.current, path = pathRef.current, layer = clusterRef.current;
    if (!map || !svg || !path || !layer) return;
    const hide = () => { svg.style.display = "none"; };
    const id = selIdRef.current;
    const marker = id ? markerByIdRef.current.get(id) : null;
    if (!marker || !layer.hasLayer(marker)) return hide();
    const cardEl = document.querySelector<HTMLElement>(".mcard");
    if (!cardEl) return hide();

    const size = map.getSize();
    const sc = marker.getLatLng();
    const p = map.latLngToContainerPoint(sc);
    const mapRect = elRef.current!.getBoundingClientRect();
    const cardRect = cardEl.getBoundingClientRect();
    const x2 = cardRect.left + cardRect.width / 2 - mapRect.left;
    const y2 = cardRect.top - mapRect.top - 8;
    svg.setAttribute("width", String(size.x));
    svg.setAttribute("height", String(size.y));
    svg.style.display = "block";
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

      {/* Directorio del mercado (o "N comercios acá"): portada + video + puestos */}
      {hoja && hoja.items.length > 0 && (
        <div className="mapa-hoja">
          {(hoja.portada || hoja.video) && (
            <div className="mapa-hoja-media">
              {hoja.portada && <img src={hoja.portada} alt="" />}
              {hoja.video && <video src={hoja.video} controls muted playsInline preload="metadata" />}
            </div>
          )}
          <div className="mapa-hoja-head">
            <b>{hoja.titulo} · {hoja.items.length}</b>
            <button type="button" onClick={() => setHoja(null)} aria-label="Cerrar">✕</button>
          </div>
          <div className="mapa-hoja-list">
            {hoja.items.map((c) => {
              const st = rubroStyle(c.rubro_slug);
              const thumb = c.portada_thumb_url || c.portada_url;
              return (
                <button key={c.id} type="button" className="mapa-hoja-row" onClick={() => { onSelect?.(c); setHoja(null); }}>
                  {thumb ? <img className="mh-thumb" src={thumb} alt="" /> : <span className="mh-dot" style={{ background: st.color }}>{st.emoji}</span>}
                  <span className="mh-nom">{c.puesto ? `#${c.puesto} · ` : ""}{c.nombre}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* No dice "acercá": acercarse ya no muestra nada. Dice qué hacer. */}
      {ocultos > 0 && (
        <div className="hm-aviso">
          Buscá o elegí una categoría para ver {ocultos} negocios
        </div>
      )}
    </div>
  );
}
