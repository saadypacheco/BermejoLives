"use client";

/**
 * Importados › Mapa: todos los importados de una ciudad como puntos, con los mismos filtros de la lista
 * (estado y fuente; la ciudad la elige el panel). Con ~19.000 puntos en Santa Cruz: Leaflet con
 * `preferCanvas` y `circleMarker` (un dibujo por punto, sin un nodo del DOM cada uno), sin clustering.
 *
 * Los nombres vienen de páginas de terceros: el popup se arma con `createElement` + `textContent`, nunca con HTML
 * armado a mano (hay un test que lo vigila).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE, SinConexion, useOnline } from "@/components/content/content-ui";
import { puntosImportados, type PuntoImportado, type PuntosImportados } from "@/lib/api";
import type { Ciudad } from "@/lib/types";
import { loadLeaflet } from "@/lib/mapa-visual";
import { agregarTiles } from "@/lib/mapa-tiles";
import { esRutaAusente, mensajeError, nombreFuente, paramFuente, paramRubroImportados, type FuenteFiltro } from "@/lib/tarjetas-pure";
import {
  BORDE_NORMAL, BORDE_REPETIDO, MSG_MAPA_VACIO, MSG_SIN_MAPA, alternarFuente, colorFuente, contarPorFuente,
  etiquetaFuente, filtrarPorFuentes, limitesDe, lineasPopup, puntoValido, resumenMapa,
} from "@/lib/importados-mapa-pure";

const CENTRO_PAIS: [number, number] = [-17.0, -64.5];

export function ImportadosMapa({ ciudad, estado, fuente, onVerFicha }: {
  ciudad: Ciudad;
  estado: string;
  fuente: FuenteFiltro;
  /** «Ver la ficha» del popup: el panel vuelve a la lista con la búsqueda y la fuente de ese punto. */
  onVerFicha: (punto: PuntoImportado) => void;
}) {
  const online = useOnline();
  const el = useRef<HTMLDivElement>(null);
  // Leaflet se carga por CDN y no trae tipos: los objetos del mapa van como `any`, sólo acá adentro.
  const mapa = useRef<any>(null);
  const L = useRef<any>(null);
  const capa = useRef<any>(null);
  const datosAjustados = useRef<PuntosImportados | null>(null);
  const alVer = useRef(onVerFicha);
  alVer.current = onVerFicha;
  // Una consulta vieja que llega tarde no pisa a la nueva (cambio de ciudad o de filtro).
  const pedido = useRef(0);

  const [datos, setDatos] = useState<PuntosImportados | null>(null);
  const [cargando, setCargando] = useState(true);
  const [err, setErr] = useState("");
  const [intento, setIntento] = useState(0);
  const [listo, setListo] = useState(false);
  const [falloMapa, setFalloMapa] = useState(false);
  const [intentoMapa, setIntentoMapa] = useState(0);
  const [ocultas, setOcultas] = useState<ReadonlySet<string>>(new Set());

  const ciudadId = ciudad.id;
  const subFuente = paramFuente(fuente);
  const subRubro = paramRubroImportados(fuente);

  // Los puntos. Al cambiar un filtro se vacía en el acto: no se ven puntos de la consulta anterior bajo los filtros nuevos.
  useEffect(() => {
    const mio = ++pedido.current;
    setDatos(null); setErr(""); setCargando(true);
    puntosImportados(ciudadId, estado, subFuente, subRubro)
      .then((r) => { if (mio === pedido.current) setDatos(r); })
      .catch((e: unknown) => {
        if (mio !== pedido.current) return;
        setErr(esRutaAusente(e) ? MSG_SIN_MAPA : `No se pudo cargar el mapa: ${mensajeError(e, "error desconocido")}`);
      })
      .finally(() => { if (mio === pedido.current) setCargando(false); });
  }, [ciudadId, estado, subFuente, subRubro, intento]);

  // Las fuentes destildadas valen para la consulta actual: con otros filtros arranca todo tildado.
  useEffect(() => { setOcultas(new Set()); }, [ciudadId, estado, subFuente, subRubro]);

  // El mapa: se arma una vez y se desarma al salir (o al reintentar la carga de Leaflet).
  useEffect(() => {
    let cancelado = false;
    setFalloMapa(false);
    loadLeaflet().then((Lf) => {
      if (cancelado || !el.current || mapa.current) return;
      L.current = Lf;
      const m = Lf.map(el.current, { attributionControl: true, preferCanvas: true }).setView(CENTRO_PAIS, 5);
      mapa.current = m;
      agregarTiles(Lf, m, { ciudad });
      setTimeout(() => m.invalidateSize(), 60);
      setListo(true);
    }).catch(() => { if (!cancelado) setFalloMapa(true); });
    return () => {
      cancelado = true;
      if (mapa.current) { mapa.current.remove(); mapa.current = null; }
      capa.current = null; L.current = null; datosAjustados.current = null;
      setListo(false);
    };
    // La ciudad sólo cambia el centro cuando no hay puntos; el mapa no se rearma por eso.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intentoMapa]);

  // El popup, con nodos y `textContent`: el nombre es texto ajeno.
  const armarPopup = useCallback((p: PuntoImportado): HTMLElement => {
    const caja = document.createElement("div");
    caja.style.cssText = "display:flex;flex-direction:column;gap:4px;min-width:200px;max-width:260px;font-size:13px;line-height:1.4";
    lineasPopup(p).forEach((t, i) => {
      const linea = document.createElement(i === 0 ? "strong" : "span");
      linea.textContent = t;
      if (i === 0) linea.style.fontSize = "14px";
      caja.appendChild(linea);
    });
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = "Ver la ficha";
    b.className = "btn btn-primary btn-sm";
    b.style.cssText = "margin-top:6px;min-height:40px;cursor:pointer";
    b.addEventListener("click", () => {
      mapa.current?.closePopup();
      alVer.current(p);
    });
    caja.appendChild(b);
    return caja;
  }, []);

  const conteo = useMemo(() => contarPorFuente(datos?.items ?? []), [datos]);
  const visibles = useMemo(() => filtrarPorFuentes((datos?.items ?? []).filter(puntoValido), ocultas), [datos, ocultas]);

  // Dibujar: se saca la capa anterior y se arma la nueva (al llegar datos nuevos o al tildar una fuente).
  useEffect(() => {
    const Lf = L.current, m = mapa.current;
    if (!listo || !Lf || !m) return;
    if (capa.current) { m.removeLayer(capa.current); capa.current = null; }
    if (!datos) return;
    const grupo = Lf.featureGroup();
    for (const p of visibles) {
      const rep = p.repetido ? BORDE_REPETIDO : BORDE_NORMAL;
      const c = colorFuente(p.fuente);
      const marca = Lf.circleMarker([p.lat, p.lng], {
        radius: 5, color: rep.color, weight: rep.peso, fillColor: c, fillOpacity: 0.9, opacity: 1,
      });
      marca.punto = p;
      grupo.addLayer(marca);
    }
    grupo.on("click", (e: any) => {
      const p = e.layer?.punto as PuntoImportado | undefined;
      if (!p) return;
      Lf.popup({ maxWidth: 280 }).setLatLng([p.lat, p.lng]).setContent(armarPopup(p)).openOn(m);
    });
    grupo.addTo(m);
    capa.current = grupo;

    // Se encuadra una vez por consulta: destildar una fuente no tiene que mover el mapa.
    if (datosAjustados.current !== datos) {
      datosAjustados.current = datos;
      const lim = limitesDe(datos.items);
      if (lim) m.fitBounds(lim, { padding: [24, 24], maxZoom: 16 });
      else if (ciudad.lat != null && ciudad.lng != null) m.setView([ciudad.lat, ciudad.lng], 13);
      else m.setView(CENTRO_PAIS, 5);
    }
  }, [listo, datos, visibles, armarPopup, ciudad.lat, ciudad.lng]);

  const vacio = !cargando && !err && datos !== null && datos.items.length === 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <SinConexion />

      <div role="status" aria-live="polite" style={{ fontSize: 13, color: "var(--txt-3)", minHeight: 20 }}>
        {cargando && <><Ic n="reloj" s={14} /> Cargando el mapa…</>}
        {datos && !cargando && <><Ic n="mapa" s={14} /> {resumenMapa(datos, datos.items.length)}</>}
      </div>

      {err && (
        <Aviso tono="error" accion={
          <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={!online} onClick={() => setIntento((n) => n + 1)}>
            <Ic n="actualizar" s={15} /> Reintentar
          </button>}>
          {err}
        </Aviso>
      )}
      {vacio && <Aviso tono="info">{MSG_MAPA_VACIO}</Aviso>}
      {falloMapa && (
        <Aviso tono="error" accion={
          <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => setIntentoMapa((n) => n + 1)}>
            <Ic n="actualizar" s={15} /> Reintentar
          </button>}>
          No se pudo cargar el mapa. Revisá la conexión.
        </Aviso>
      )}

      {conteo.length > 0 && (
        <fieldset style={{ border: "1px solid var(--border)", borderRadius: 10, padding: "8px 12px", margin: 0 }}>
          <legend style={{ fontSize: 12.5, color: "var(--txt-3)", padding: "0 6px" }}>Fuentes en el mapa</legend>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 16px", alignItems: "center" }}>
            {conteo.map((c) => {
              const tildada = !ocultas.has(c.fuente);
              return (
                <label key={c.fuente} title={nombreFuente({ fuente: c.fuente })}
                       style={{ display: "inline-flex", alignItems: "center", gap: 8, minHeight: 36, fontSize: 13.5, cursor: "pointer" }}>
                  <input type="checkbox" checked={tildada} onChange={() => setOcultas((o) => alternarFuente(o, c.fuente))}
                         style={{ width: 18, height: 18 }} />
                  <span aria-hidden="true" style={{ width: 14, height: 14, borderRadius: "50%", background: colorFuente(c.fuente),
                                                      border: "1px solid #fff", boxShadow: "0 0 0 1px var(--border)", opacity: tildada ? 1 : 0.35 }} />
                  <span>{etiquetaFuente(c.fuente)} <b>{c.n}</b></span>
                </label>
              );
            })}
            <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 12.5, color: "var(--txt-3)" }}>
              <span aria-hidden="true" style={{ width: 14, height: 14, borderRadius: "50%", background: "#bbb",
                                                  border: `${BORDE_REPETIDO.peso}px solid ${BORDE_REPETIDO.color}`, boxSizing: "border-box" }} />
              Borde oscuro grueso: repetido (ya hay uno parecido en URUKU)
            </span>
          </div>
        </fieldset>
      )}

      <div ref={el} role="region" aria-label={`Mapa de importados de ${ciudad.nombre}`}
           style={{ width: "100%", height: "min(70vh, 640px)", minHeight: 360, borderRadius: 10, border: "1px solid var(--border)",
                    background: "var(--panel)" }} />
    </div>
  );
}
