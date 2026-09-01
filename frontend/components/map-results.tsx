"use client";

import { agregarTiles } from "@/lib/mapa-tiles";
import { useEffect, useRef } from "react";
import { type ResultadoBusqueda, comoLlegarHref, waLink, MODALIDAD_LABEL } from "@/lib/types";
import { registrarLead, type TipoLead } from "@/lib/campo";
import { rubroStyle, loadLeaflet } from "@/lib/mapa-visual";
import { adornoHTML, MEDIDAS, ZOOM_MIN_ADORNOS, type Adorno } from "@/lib/adornos";
import { getAdornosMapa } from "@/lib/data";

const BERMEJO: [number, number] = [-22.7361, -64.3433];

/** El popup se arma con texto, no con React: una comilla en una URL rompía el
 *  atributo y de ahí en adelante el HTML es del que puso la URL. */
function escapeAttr(v: string): string {
  return v.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Pin del mapa de resultados: color por rubro; los verificados resaltan (anillo).
function pinHtml(r: ResultadoBusqueda): string {
  const style = rubroStyle(r.rubro_slug);
  const cls = r.verificado ? "ukpin destacado" : "ukpin pago";
  const ring = r.verificado ? `<i class="ukpin-ring"></i>` : "";
  return `<div class="${cls}" style="--pc:${style.color}">${ring}<span class="ukpin-emo">${style.emoji}</span></div>`;
}

export function MapResults({ results, hayFiltro = true }: {
  results: ResultadoBusqueda[];
  /** Sin filtro puesto el mapa muestra los adornos y nada más, salvo los
   *  destacados y los que pagan. 887 pines sobre Bermejo no son un mapa, son
   *  una mancha — y aparece justo cuando alguien todavía no sabe qué busca. */
  hayFiltro?: boolean;
}) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const clusterRef = useRef<any>(null);
  const adornoLayerRef = useRef<any>(null);
  const adornosRef = useRef<Adorno[]>([]);
  const temaObsRef = useRef<MutationObserver | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadLeaflet().then((L) => {
      if (cancelled || !elRef.current) return;
      if (!mapRef.current) {
        mapRef.current = L.map(elRef.current, { zoomControl: true, attributionControl: true }).setView(BERMEJO, 15);
        // El tema, no un valor fijo. Estaba clavado en oscuro, y al unificar las
        // pantallas eso pasó a ser el único mapa del sitio: un sitio en claro
        // con un mapa negro adentro. Antes /mapa lo respetaba y /buscar no.
        const esOscuro = () => document.getElementById("ukroot")?.getAttribute("data-theme") !== "light";
        const tiles = agregarTiles(L, mapRef.current, { oscuro: esOscuro() });
        // El tema cambia una CLASE, no la URL: OSM publica un solo estilo y el
        // oscuro sale de un filtro CSS. Cambiar la URL volvería a descargar el
        // mapa entero en cada toque del interruptor.
        const root = document.getElementById("ukroot");
        if (root) {
          const obs = new MutationObserver(() => {
            tiles.getContainer()?.classList.toggle("uk-tiles-oscuro", esOscuro());
          });
          obs.observe(root, { attributes: true, attributeFilter: ["data-theme"] });
          temaObsRef.current = obs;
        }
        // Sin agrupador: mapa lleno de puntos individuales por rubro.
        clusterRef.current = L.layerGroup().addTo(mapRef.current);

        // Panel propio para los adornos, por DEBAJO de los pines y sordo al
        // mouse: una chalana nunca puede robarle el clic a un comercio.
        const map = mapRef.current;
        map.createPane("adornos");
        map.getPane("adornos").style.zIndex = "350";
        map.getPane("adornos").style.pointerEvents = "none";
        adornoLayerRef.current = L.layerGroup().addTo(map);
        map.on("zoomend", () => pintarAdornos(L));

        // Llegan después de la primera pintada, a propósito: el mapa se dibuja
        // con los comercios y la decoración aparece cuando esté.
        getAdornosMapa().then((items) => {
          adornosRef.current = items;
          pintarAdornos(L);
        }).catch(() => { /* sin adornos el mapa sigue sirviendo */ });
      }
      renderPins(L);
      pintarAdornos(L);
      // Leaflet mide el contenedor al crearse y pide sólo las tiles que entran
      // en esa medida. Si el ancho todavía no era el definitivo —y no lo es:
      // esta vista aparece al cambiar de Lista a Mapa, y /mapa llega por una
      // redirección— las columnas que faltan quedan como franjas blancas y no
      // se piden nunca más, porque el mapa no se entera de que creció.
      mapRef.current?.invalidateSize();
    });
    return () => { cancelled = true; temaObsRef.current?.disconnect(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [results]);

  // Y si el contenedor cambia de tamaño después —girar el teléfono, abrir el
  // teclado, el navegador escondiendo su barra al hacer scroll— hay que
  // avisarle igual. Un solo `invalidateSize` al montar cubre el arranque, no la
  // vida del mapa.
  useEffect(() => {
    const el = elRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const obs = new ResizeObserver(() => mapRef.current?.invalidateSize());
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Los popups son HTML crudo (fuera de React): tracking de leads por delegación.
  useEffect(() => {
    const el = elRef.current;
    if (!el) return;
    function onClick(e: MouseEvent) {
      const target = (e.target as HTMLElement)?.closest("[data-lead-comercio]");
      const comercioId = target?.getAttribute("data-lead-comercio");
      // Sin leer el tipo, los tres enlaces del popup se registraban como
      // "whatsapp" — y "Cómo llegar" ni siquiera tenía el atributo.
      const tipo = (target?.getAttribute("data-lead-tipo") as TipoLead) || "whatsapp";
      if (comercioId) registrarLead(comercioId, tipo);
    }
    el.addEventListener("click", onClick);
    return () => el.removeEventListener("click", onClick);
  }, []);

  function pintarAdornos(L: any) {
    const map = mapRef.current, capa = adornoLayerRef.current;
    if (!map || !capa) return;
    capa.clearLayers();
    if (map.getZoom() < ZOOM_MIN_ADORNOS) return;
    adornosRef.current.forEach((a, i) => {
      if (a.lat == null || a.lng == null) return;
      const m = MEDIDAS[a.tipo] ?? MEDIDAS.lapacho;
      capa.addLayer(L.marker([a.lat, a.lng], {
        icon: L.divIcon({ className: "", html: adornoHTML(a, i), iconSize: [m.w, m.h], iconAnchor: [m.w / 2, m.anclaY] }),
        pane: "adornos", interactive: false, keyboard: false,
      }));
    });
  }

  function renderPins(L: any) {
    const layer = clusterRef.current;
    if (!layer) return;
    layer.clearLayers();
    const visibles = hayFiltro
      ? results
      // `plan` y `destacado` los agrega la 0077. Sin filtro, la primera vista
      // es un lugar con cupo — y el cupo es lo que se vende.
      : results.filter((r) => r.destacado || (r.plan && r.plan !== "gratis"));
    const withCoords = visibles.filter((r) => r.lat != null && r.lng != null);
    const bounds: [number, number][] = [];
    for (const r of withCoords) {
      const size = r.verificado ? 34 : 22;
      const icon = L.divIcon({
        className: "", html: pinHtml(r), iconSize: [size, size], iconAnchor: [size / 2, size / 2],
      });
      // La foto va PRIMERO y adentro del globo.
      //
      // En el celular el globo del mapa es todo lo que se ve de un comercio: no
      // hay tarjeta al costado como en la compu. Sin la foto, tocar un pin
      // devolvía un nombre y dos enlaces — y en rubros como calzado o ropa la
      // vidriera dice más que el nombre, que muchas veces es "Comercio".
      //
      // Se usa la miniatura si está: el globo la muestra a 220px de ancho y la
      // grande pesa diez veces más para verse igual.
      const foto = r.portada_thumb_url ?? r.portada_url ?? r.logo_url;
      const popup = `
        <div class="map-pop">
          ${foto ? `<img class="map-pop-img" src="${escapeAttr(foto)}" alt="" loading="lazy">` : ""}
          <b>${r.nombre}</b>
          <span>${MODALIDAD_LABEL[r.modalidad] ?? r.modalidad}${r.rubro_nombre ? " · " + r.rubro_nombre : ""}</span>
          <div class="map-pop-act">
            <a href="${waLink(r.whatsapp, "Hola, te vi en URUKU")}" target="_blank" rel="noopener" data-lead-comercio="${r.id}" data-lead-tipo="whatsapp">WhatsApp</a>
            <a href="${comoLlegarHref(r)}" target="_blank" rel="noopener" data-lead-comercio="${r.id}" data-lead-tipo="mapa">Cómo llegar</a>
            <a href="/comercios/${r.slug}">Ver comercio</a>
          </div>
        </div>`;
      const m = L.marker([r.lat, r.lng], { icon, zIndexOffset: r.verificado ? 300 : 0 }).bindPopup(popup);
      m.__data = r;
      layer.addLayer(m);
      bounds.push([r.lat as number, r.lng as number]);
    }
    if (bounds.length > 1) mapRef.current.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
    else if (bounds.length === 1) mapRef.current.setView(bounds[0], 16);
  }

  const sinCoords = results.filter((r) => r.lat == null || r.lng == null).length;
  const ocultos = hayFiltro ? 0 : results.filter((r) => !r.destacado && (!r.plan || r.plan === "gratis")).length;

  return (
    <div style={{ position: "relative" }}>
      <div ref={elRef} className="map-canvas" />

      {/* Sin esto, un mapa con dos pines sobre una ciudad se lee como "acá no
          hay nada", que es lo contrario de lo que pasa. */}
      {ocultos > 0 && (
        <div className="hm-aviso">Buscá o elegí una categoría para ver {ocultos} negocios</div>
      )}

      {sinCoords > 0 && (
        <p style={{ color: "var(--txt-3)", fontSize: 12.5, marginTop: 10 }}>
          {sinCoords} comercio(s) sin ubicación todavía (la comparten por WhatsApp). Mientras tanto aparecen en la lista.
        </p>
      )}
    </div>
  );
}
