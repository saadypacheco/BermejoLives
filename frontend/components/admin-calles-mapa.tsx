"use client";

/**
 * Admin › Calles y horarios › Mapa (spec docs/mapa-calles.md).
 *
 * Las calles de la ciudad elegida arriba, pintadas por estado: verde recorrida,
 * ámbar parcial, rojo pendiente, gris sin comercios. Tocar una calle abre su
 * ficha (cobertura, comercios, último paso) con los botones de marca. Si la
 * ciudad todavía no tiene tramos, «Traer calles de OpenStreetMap» los baja.
 *
 * Estados: cargando, vacío (sin tramos), error con «Reintentar» y sin conexión.
 * Estilos inline: el panel no carga `uruku.css`.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { adminImportarCalles, adminMapaCalles, adminMarcarCalle, puedo } from "@/lib/api";
import { agregarTiles } from "@/lib/mapa-tiles";
import { loadLeaflet } from "@/lib/mapa-visual";
import { calcularZonas, clasificarCalles, crearRendererCalles, grosorPorZoom, pintarCalles, pintarZonas, reestilarCalles, resaltarCalle } from "@/lib/calles-mapa";
import {
  conMarca, contarPorEstado, kmTxt, pctTxt,
  type CapaCalles, type EstadoMarca, type TramoCalle,
} from "@/lib/calles";
import { CallePanel, LeyendaCalles } from "@/components/calle-panel";
import { Ic } from "@/components/ic";
import type { Ciudad } from "@/lib/types";

const BERMEJO: [number, number] = [-22.7361, -64.3433];

type Carga = "cargando" | "listo" | "error";

export function AdminCallesMapa({ ciudad }: { ciudad: Ciudad }) {
  const slug = ciudad.slug;
  const [carga, setCarga] = useState<Carga>("cargando");
  const [capa, setCapa] = useState<CapaCalles | null>(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  // Zonas primero: con una ciudad recién empezada, la vista por cuadras es casi
  // toda gris; las zonas muestran de un vistazo qué barrios ya se hicieron.
  const [vista, setVista] = useState<"zonas" | "calles">("zonas");
  const [importando, setImportando] = useState(false);
  const [errImport, setErrImport] = useState("");
  const [okImport, setOkImport] = useState("");
  const pedido = useRef(0);

  const cargar = useCallback(async (silencioso = false) => {
    const n = ++pedido.current;
    if (!silencioso) { setCarga("cargando"); setErr(""); }
    try {
      const c = await adminMapaCalles(slug);
      if (n !== pedido.current) return;       // llegó tarde: ya se cambió de ciudad
      setCapa(c); setCarga("listo");
    } catch (e) {
      if (n !== pedido.current) return;
      if (silencioso) return;                 // el mapa que ya se ve sigue valiendo
      const sinRed = typeof navigator !== "undefined" && navigator.onLine === false;
      setErr(sinRed ? "Sin conexión. Cuando vuelva la señal, tocá «Reintentar»." : e instanceof Error && e.message ? e.message : "No se pudieron traer las calles.");
      setCarga("error");
    }
  }, [slug]);

  // Otra ciudad: se descarta todo lo de la anterior.
  useEffect(() => {
    setCapa(null); setSel(null); setOkImport(""); setErrImport("");
    void cargar();
    return () => { pedido.current++; };
  }, [cargar]);

  async function importar() {
    setErrImport(""); setOkImport(""); setImportando(true);
    try {
      const r = await adminImportarCalles(slug);
      setOkImport(`Listo: ${r.tramos.toLocaleString("es-BO")} tramos, ${kmTxt(r.km)} km.`);
      await cargar();
    } catch (e) {
      const sinRed = typeof navigator !== "undefined" && navigator.onLine === false;
      setErrImport(sinRed ? "Sin conexión: no se pudo consultar OpenStreetMap." : e instanceof Error && e.message ? e.message : "No se pudieron traer las calles.");
    } finally {
      setImportando(false);
    }
  }

  async function marcar(id: string, estado: EstadoMarca, nota: string) {
    await adminMarcarCalle(id, estado, nota);
    // Se ve al instante; el servidor recalcula el resto y se vuelve a pedir en segundo plano.
    setCapa((c) => c && { ...c, tramos: c.tramos.map((t) => (t.id === id ? conMarca(t, estado, nota || null, "vos") : t)) });
    void cargar(true);
  }

  const tramo = useMemo(() => capa?.tramos.find((t) => t.id === sel) ?? null, [capa, sel]);
  const puedeImportar = puedo("lugares");

  if (carga === "cargando" && !capa) {
    return <p role="status" style={{ padding: 16, color: "var(--txt-3)", fontSize: 14 }}><Ic n="reloj" s={15} /> Cargando las calles de {ciudad.nombre}…</p>;
  }

  if (carga === "error" && !capa) {
    return (
      <div role="alert" style={{ padding: 16, display: "grid", gap: 10, justifyItems: "start" }}>
        <p style={{ margin: 0, color: "var(--pink)", fontSize: 14 }}><Ic n="aviso" s={15} /> {err}</p>
        <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} onClick={() => { void cargar(); }}>
          <Ic n="actualizar" s={15} /> Reintentar
        </button>
      </div>
    );
  }

  const tramos = capa?.tramos ?? [];

  if (tramos.length === 0) {
    return (
      <div style={{ padding: 16, display: "grid", gap: 12, justifyItems: "start" }}>
        <p style={{ margin: 0, color: "var(--txt-2)", fontSize: 14, maxWidth: 560 }}>
          <Ic n="mapa" s={16} /> {ciudad.nombre} todavía no tiene calles cargadas. Traelas de OpenStreetMap y el mapa
          se pinta solo según dónde hay comercios cargados.
        </p>
        {puedeImportar ? (
          <button type="button" className="btn btn-primary" style={{ minHeight: 48 }} disabled={importando} onClick={importar}>
            <Ic n={importando ? "actualizar" : "descargar"} s={16} /> {importando ? "Trayendo las calles…" : "Traer calles de OpenStreetMap"}
          </button>
        ) : (
          <p style={{ margin: 0, color: "var(--amber)", fontSize: 13 }}><Ic n="seguridad" s={14} /> No tenés permiso para traer calles. Pedíselo a quien administra el equipo.</p>
        )}
        {importando && <p role="status" style={{ margin: 0, color: "var(--txt-3)", fontSize: 13 }}><Ic n="reloj" s={13} /> Puede tardar hasta un minuto: se consulta OpenStreetMap.</p>}
        {okImport && <p role="status" style={{ margin: 0, color: "var(--neon)", fontSize: 13 }}><Ic n="listo" s={14} /> {okImport}</p>}
        {errImport && (
          <div role="alert" style={{ display: "grid", gap: 8, justifyItems: "start" }}>
            <p style={{ margin: 0, color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={14} /> {errImport}</p>
            <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} onClick={importar}><Ic n="actualizar" s={15} /> Reintentar</button>
          </div>
        )}
      </div>
    );
  }

  const resumen = capa!.resumen;
  const porEstado = contarPorEstado(tramos);
  const visual = clasificarCalles(tramos);
  const siguientes = tramos.reduce((a, t) => (visual.get(t.id) === "siguiente" ? { n: a.n + 1, km: a.km + t.longitud_m / 1000 } : a), { n: 0, km: 0 });

  return (
    <div style={{ padding: 12, display: "grid", gap: 10 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "baseline", flexWrap: "wrap", justifyContent: "space-between" }}>
        <p style={{ margin: 0, fontSize: 15 }}>
          <b>{kmTxt(resumen.km_recorridos)} de {kmTxt(resumen.km_a_recorrer)} km recorridos ({pctTxt(resumen.pct)} %)</b>
          {resumen.km_sin_comercios > 0 && (
            <span style={{ color: "var(--txt-3)", fontSize: 13 }}> · {kmTxt(resumen.km_sin_comercios)} km sin comercios</span>
          )}
        </p>
        <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} disabled={carga === "cargando"} onClick={() => { void cargar(true); }}>
          <Ic n="actualizar" s={15} /> Actualizar
        </button>
      </div>

      <div role="group" aria-label="Cómo ver el mapa" style={{ display: "flex", gap: 6 }}>
        {(["zonas", "calles"] as const).map((v) => (
          <button key={v} type="button" className={`btn btn-sm ${vista === v ? "btn-primary" : "btn-ghost"}`} style={{ minHeight: 40 }}
                  aria-pressed={vista === v} onClick={() => setVista(v)}>
            <Ic n={v === "zonas" ? "mapa" : "ruta"} s={15} /> {v === "zonas" ? "Zonas" : "Calles"}
          </button>
        ))}
      </div>

      {vista === "calles" && <LeyendaCalles porEstado={porEstado} siguientes={siguientes} />}

      <MapaCallesLeaflet tramos={tramos} centro={ciudad.lat != null && ciudad.lng != null ? [ciudad.lat, ciudad.lng] : null}
                         ajusteKey={slug} sel={sel} onSel={setSel} vista={vista} onVista={setVista} />

      <p style={{ margin: 0, color: "var(--txt-3)", fontSize: 12.5 }}>
        {vista === "zonas"
          ? "Cada cuadrado son unas cuatro cuadras: cuanto más verde, más recorrido. Tocá uno para acercarte y ver sus calles."
          : "Verde: ya recorrida. Ámbar: a medias. Naranja: pendiente pegada a lo recorrido, por donde conviene seguir. Gris finito: pendiente más lejos. Punteado: sin comercios. Tocá una calle para ver su ficha y marcarla."}
      </p>

      {tramo && (
        <CallePanel tramo={tramo} onCerrar={() => setSel(null)} onMarcar={(e, n) => marcar(tramo.id, e, n)} />
      )}

      {carga === "error" && (
        <p role="alert" style={{ margin: 0, color: "var(--amber)", fontSize: 13 }}><Ic n="aviso" s={14} /> {err}</p>
      )}
    </div>
  );
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function MapaCallesLeaflet({ tramos, centro, ajusteKey, sel, onSel, vista, onVista }: {
  tramos: TramoCalle[];
  centro: [number, number] | null;
  /** Cambia cuando hay que volver a encuadrar (otra ciudad); marcar una calle no lo cambia. */
  ajusteKey: string;
  sel: string | null;
  onSel: (id: string | null) => void;
  vista: "zonas" | "calles";
  onVista: (v: "zonas" | "calles") => void;
}) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const LRef = useRef<any>(null);
  const rendererRef = useRef<any>(null);
  const grupoRef = useRef<any>(null);
  const lineasRef = useRef<Map<string, any>>(new Map());
  const haloRef = useRef<any>(null);
  const ajustadoRef = useRef("");
  const tramosRef = useRef(tramos); tramosRef.current = tramos;
  const selRef = useRef(sel); selRef.current = sel;
  const onSelRef = useRef(onSel); onSelRef.current = onSel;
  const onVistaRef = useRef(onVista); onVistaRef.current = onVista;
  const centroRef = useRef(centro); centroRef.current = centro;
  const [listo, setListo] = useState(false);
  const [falla, setFalla] = useState(false);
  const [sinPlano, setSinPlano] = useState(false);

  // Alta del mapa, una vez.
  useEffect(() => {
    let cancelado = false;
    loadLeaflet().then((L) => {
      if (cancelado || !elRef.current || mapRef.current) return;
      const map = L.map(elRef.current, { attributionControl: false, zoomControl: true }).setView(centroRef.current ?? BERMEJO, 15);
      L.control.attribution({ prefix: false }).addTo(map);
      const tiles = agregarTiles(L, map, { oscuro: true });
      tiles.on("tileerror", () => setSinPlano(true));
      tiles.on("tileload", () => setSinPlano(false));
      rendererRef.current = crearRendererCalles(L, map);
      grupoRef.current = L.layerGroup().addTo(map);
      mapRef.current = map; LRef.current = L;
      setTimeout(() => { if (mapRef.current === map) map.invalidateSize(); }, 60);
      setListo(true);
    }).catch(() => { if (!cancelado) setFalla(true); });
    return () => {
      cancelado = true;
      if (mapRef.current) { mapRef.current.remove(); mapRef.current = null; }
      setListo(false);
    };
  }, []);

  // Dibujo de las calles (también tras marcar una: se repinta todo, es un canvas).
  useEffect(() => {
    const L = LRef.current, map = mapRef.current, grupo = grupoRef.current, renderer = rendererRef.current;
    if (!listo || !L || !map || !grupo) return;
    grupo.clearLayers();
    haloRef.current = null;
    lineasRef.current = new Map();
    if (vista === "zonas") {
      // Tocar una zona: acercarse a ella y pasar a ver sus calles.
      pintarZonas(L, renderer, grupo, calcularZonas(tramos), (b) => {
        map.fitBounds(b, { padding: [10, 10], animate: true });
        onVistaRef.current("calles");
      });
    } else {
      lineasRef.current = pintarCalles(L, renderer, grupo, tramos, grosorPorZoom(map.getZoom()), (id) => onSelRef.current(id));
      const s = selRef.current;
      const t = s ? tramos.find((x) => x.id === s) ?? null : null;
      haloRef.current = resaltarCalle(L, renderer, grupo, null, t ? lineasRef.current.get(t.id) ?? null : null, t, grosorPorZoom(map.getZoom()));
    }

    // Encuadre: sólo la primera vez para esta ciudad.
    if (ajustadoRef.current !== ajusteKey) {
      ajustadoRef.current = ajusteKey;
      const puntos: [number, number][] = [];
      for (const x of tramos) for (const p of x.geom) puntos.push(p);
      if (puntos.length > 1) map.fitBounds(puntos, { padding: [20, 20], animate: false });
      else if (centroRef.current) map.setView(centroRef.current, 15);
    }
  }, [listo, tramos, ajusteKey, vista]);

  // Calle elegida: halo blanco debajo y la línea encima.
  useEffect(() => {
    const L = LRef.current, map = mapRef.current, grupo = grupoRef.current, renderer = rendererRef.current;
    if (!listo || !L || !map || !grupo) return;
    const t = sel ? tramosRef.current.find((x) => x.id === sel) ?? null : null;
    haloRef.current = resaltarCalle(L, renderer, grupo, haloRef.current, t ? lineasRef.current.get(t.id) ?? null : null, t, grosorPorZoom(map.getZoom()));
  }, [listo, sel]);

  // Al acercar o alejar, el trazo cambia de grosor.
  useEffect(() => {
    const L = LRef.current, map = mapRef.current;
    if (!listo || !L || !map) return;
    const alZoom = () => {
      const g = grosorPorZoom(map.getZoom());
      reestilarCalles(lineasRef.current, g);
      if (haloRef.current) haloRef.current.setStyle({ weight: g + 7 });
    };
    map.on("zoomend", alZoom);
    return () => { map.off("zoomend", alZoom); };
  }, [listo]);

  // Otra ciudad con el mapa abierto y sin tramos todavía: va al centro nuevo.
  const [cLat, cLng] = centro ?? [null, null];
  useEffect(() => {
    if (listo && cLat != null && cLng != null && ajustadoRef.current !== ajusteKey) mapRef.current?.setView([cLat, cLng], 15);
  }, [listo, cLat, cLng, ajusteKey]);

  if (falla) {
    return (
      <div role="status" style={{ minHeight: 160, borderRadius: 12, border: "1px dashed var(--border, var(--stroke))", display: "grid", placeItems: "center", textAlign: "center", padding: 16, color: "var(--txt-3)", fontSize: 13 }}>
        <span><Ic n="aviso" s={16} /> El mapa necesita conexión y no se pudo cargar. Probá de nuevo cuando haya señal.</span>
      </div>
    );
  }

  return (
    <div style={{ position: "relative" }}>
      <div ref={elRef} aria-label="Mapa de calles recorridas"
           style={{ height: "min(62vh, 520px)", minHeight: 340, borderRadius: 12, overflow: "hidden", border: "1px solid var(--border, var(--stroke))", background: "#e5e7eb" }} />
      {!listo && (
        <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", color: "#475569", fontSize: 13, pointerEvents: "none" }}>
          <span><Ic n="reloj" s={14} /> Cargando el mapa…</span>
        </div>
      )}
      {sinPlano && (
        <div role="status" style={{ position: "absolute", left: 8, right: 8, bottom: 8, zIndex: 500, padding: "6px 10px", borderRadius: 10, background: "rgba(10,13,20,.88)", color: "var(--amber)", fontSize: 12 }}>
          <Ic n="aviso" s={13} /> Sin conexión o con tiles caídos: el mapa base no baja, pero las calles siguen acá.
        </div>
      )}
    </div>
  );
}
