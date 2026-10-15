"use client";

/**
 * «Qué hay acá»: la primera pantalla del agente (spec docs/que-hay-aca.md).
 *
 * Parado frente a un local, lo primero que necesita saber es si YA está cargado.
 * Arriba va el mapa con su punto y los locales de alrededor (con la miniatura
 * de la portada); abajo, la lista por distancia con el plan y qué les falta.
 * Tocar uno abre su ficha. Si no está, «+ Cargar un local nuevo acá» abre el
 * alta con el GPS ya tomado.
 *
 * SIN SEÑAL funciona con la lista guardada en el celular (lib/campo-cache.ts):
 * se ve el punto, la lista, el plan y qué falta; la ficha completa y los
 * ejemplos necesitan conexión y la pantalla lo dice. El aviso «Ya cargados acá
 * cerca» del alta queda como red de seguridad.
 *
 * CALLES (spec docs/mapa-calles.md): el interruptor «Calles» pinta en el mapa las
 * calles de la ciudad (verde recorrida, ámbar parcial, rojo pendiente, gris sin
 * comercios) y abajo lista las pendientes más cercanas para ir a la siguiente.
 * Tocar una calle (en el mapa o en la lista) abre su ficha para marcarla. Sin
 * señal se ve la última capa guardada (lib/calles-cache.ts); marcar necesita señal.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import {
  misComercios, ciudadDelAgente, listarLugares, campoCalles, campoMarcarCalle,
  type ComercioAgente, type EstadoPlan, type Lugar,
} from "@/lib/campo";
import { capaGuardada, guardarVerCalles, leerVerCalles, recordarCapa } from "@/lib/calles-cache";
import {
  conMarca, fechaCalle, kmTxt, nombreCalle, pctTxt, pendientesCerca,
  type CapaCalles, type EstadoMarca,
} from "@/lib/calles";
import { aCercanos, cercanosGuardados, listaEnMemoria, recordarLista, type ComercioCercano } from "@/lib/campo-cache";
import { calcularFaltas, etiquetasFaltas } from "@/lib/faltas";
import { geoErrorMsg, metros } from "@/lib/geo";
import { getRubros } from "@/lib/data";
import { listarPendientes } from "@/lib/offline-altas";
import type { Rubro } from "@/lib/types";
import { MapaAca, type PosicionAca, type PinAca } from "@/components/mapa-aca";
import { FichaAgente } from "@/components/ficha-agente";
import { SelloPlan } from "@/components/sello-plan";
import { CallePanel, EstadoCalleTag, LeyendaCalles } from "@/components/calle-panel";
import { PermisoUbicacion } from "@/components/permiso-ubicacion";
import { Ic } from "@/components/ic";
import { Pin } from "@/components/icons";

/** Hasta dónde llega la lista al abrir, y hasta dónde con «Ver más lejos». */
export const RADIO_CERCA_M = 150;
export const RADIO_LEJOS_M = 400;

type EstadoDatos = "cargando" | "fresca" | "guardada" | "sin-datos";

/** Cuántas calles pendientes se listan. Con más, la lista deja de servir para «la siguiente». */
const MAX_PENDIENTES = 8;

/** Un local de la lista, venga de la lista completa o de la guardada en el celular. */
type ItemAca = {
  id: string; nombre: string; lat: number; lng: number;
  rubro: string | null; thumb: string | null;
  plan: EstadoPlan | null;
  /** null = no se sabe (dato viejo guardado antes de «Qué hay acá»). */
  faltan: string[] | null;
  /** El comercio completo; null si sólo hay lo guardado (sin señal). */
  c: ComercioAgente | null;
  d: number;
  /** El punto salió de la dirección, no del GPS en la puerta. */
  aprox: boolean;
};

function desdeComercio(c: ComercioAgente, aqui: PosicionAca | null): ItemAca | null {
  if (c.lat == null || c.lng == null) return null;
  return {
    id: c.id, nombre: c.nombre ?? "", lat: c.lat, lng: c.lng,
    rubro: c.rubros?.nombre ?? null, thumb: c.portada_thumb_url || c.portada_url || null,
    plan: c.estado_plan ?? null,
    faltan: etiquetasFaltas(calcularFaltas(c, c.fotos_count ?? null)),
    c, d: aqui ? metros(aqui.lat, aqui.lng, c.lat, c.lng) : Infinity,
    aprox: c.ubicacion_aproximada === true,
  };
}

function desdeGuardado(x: ComercioCercano, aqui: PosicionAca | null): ItemAca {
  return {
    id: x.id, nombre: x.nombre, lat: x.lat, lng: x.lng, rubro: x.rubro, thumb: x.thumb,
    plan: x.plan ?? null, faltan: x.faltan ?? null, c: null,
    d: aqui ? metros(aqui.lat, aqui.lng, x.lat, x.lng) : Infinity,
    aprox: false,
  };
}

const metrosTxt = (d: number) => `a ${Math.round(d)} m`;

export function QueHayAca({ cabecera, onCargarNuevo, onMisComercios, onSubirPendientes }: {
  /** Los botones de arriba a la derecha (Manual, Salir…): los pone quien la usa. */
  cabecera: React.ReactNode;
  /** «+ Cargar un local nuevo acá»: abre el alta con el GPS ya tomado (o sin él). */
  onCargarNuevo: (gps: PosicionAca | null) => void;
  onMisComercios: () => void;
  /** Hay altas guardadas sin subir: se suben desde la pantalla del alta. */
  onSubirPendientes: () => void;
}) {
  const [aqui, setAqui] = useState<PosicionAca | null>(null);
  const [buscandoGps, setBuscandoGps] = useState(false);
  const [geoMsg, setGeoMsg] = useState("");

  // Arranca con lo último que se vio (memoria) o lo guardado en el celular.
  const [items, setItems] = useState<ComercioAgente[] | null>(() => listaEnMemoria());
  const [guardada, setGuardada] = useState<ComercioCercano[] | null>(() => (typeof window === "undefined" ? null : cercanosGuardados()));
  const [estado, setEstado] = useState<EstadoDatos>("cargando");
  const [radio, setRadio] = useState<number>(RADIO_CERCA_M);
  const [abierto, setAbierto] = useState<string | null>(null);
  const [aviso, setAviso] = useState("");
  const [pendientes, setPendientes] = useState(0);
  const [rubros, setRubros] = useState<Rubro[]>([]);
  const [lugares, setLugares] = useState<Lugar[]>([]);
  const scrollLista = useRef(0);
  const restaurar = useRef(false);

  // Calles: apagadas por defecto; se recuerda si el agente las dejó prendidas.
  const [verCalles, setVerCalles] = useState<boolean>(() => (typeof window === "undefined" ? false : leerVerCalles()));
  const [capa, setCapa] = useState<CapaCalles | null>(null);
  const [estCalles, setEstCalles] = useState<EstadoDatos>("cargando");
  const [calleSel, setCalleSel] = useState<string | null>(null);
  const mapaRef = useRef<HTMLDivElement>(null);

  // ── Ubicación ────────────────────────────────────────────────
  function ubicar() {
    setGeoMsg("");
    if (typeof navigator === "undefined" || !("geolocation" in navigator)) { setGeoMsg("Este dispositivo no tiene GPS disponible."); return; }
    setBuscandoGps(true);
    navigator.geolocation.getCurrentPosition(
      (p) => { setAqui({ lat: p.coords.latitude, lng: p.coords.longitude, acc: Math.round(p.coords.accuracy) }); setBuscandoGps(false); },
      (e) => { setBuscandoGps(false); setGeoMsg(geoErrorMsg(e)); },
      // maximumAge 0: «Actualizar mi ubicación» tiene que dar la de AHORA, no una de hace un rato.
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
    );
  }

  // ── Datos ────────────────────────────────────────────────────
  function traerLista() {
    misComercios()
      .then((xs) => { recordarLista(xs); setItems(xs); setEstado("fresca"); })
      // Sin señal (o sesión vencida): se queda con lo que había.
      .catch(() => setEstado((e) => (e === "fresca" ? e : (listaEnMemoria() || cercanosGuardados()) ? "guardada" : "sin-datos")));
  }
  function traerCalles() {
    campoCalles()
      .then((c) => { recordarCapa(c); setCapa(c); setEstCalles("fresca"); })
      // Sin señal (o sesión vencida): se queda con la capa guardada, si la hay.
      .catch(() => setEstCalles((e) => (e === "fresca" ? e : capaGuardada() ? "guardada" : "sin-datos")));
  }
  function alternarCalles() {
    const v = !verCalles;
    setVerCalles(v); guardarVerCalles(v);
    if (!v) setCalleSel(null);
  }
  // Al prender: primero lo guardado (se ve al instante, también sin señal) y después lo fresco.
  useEffect(() => {
    if (!verCalles) return;
    const g = capaGuardada();
    if (g) setCapa((prev) => prev ?? g);
    setEstCalles("cargando");
    traerCalles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [verCalles]);

  async function marcarCalle(id: string, estado: EstadoMarca, nota: string) {
    await campoMarcarCalle(id, estado, nota);
    if (capa) {
      // Se ve al instante; el servidor recalcula y se vuelve a pedir en segundo plano.
      const nueva: CapaCalles = { ...capa, tramos: capa.tramos.map((t) => (t.id === id ? conMarca(t, estado, nota || null, null) : t)) };
      recordarCapa(nueva); setCapa(nueva);
    }
    traerCalles();
  }
  function elegirCalleDeLaLista(id: string) {
    setCalleSel(id);
    // La lista queda abajo y el mapa arriba: sin esto la calle se elige y no se ve nada.
    requestAnimationFrame(() => mapaRef.current?.scrollIntoView({ block: "start", behavior: "smooth" }));
  }

  useEffect(() => {
    ubicar();
    traerLista();
    listarPendientes().then((xs) => setPendientes(xs.length)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  // Mantiene la lista guardada al día cuando se edita desde la ficha.
  useEffect(() => { if (items) recordarLista(items); }, [items]);

  const base = useMemo<ItemAca[]>(() => {
    if (items) return items.map((c) => desdeComercio(c, aqui)).filter((x): x is ItemAca => x !== null);
    if (guardada) return guardada.map((x) => desdeGuardado(x, aqui));
    return [];
  }, [items, guardada, aqui]);

  const cerca = useMemo(
    () => base.filter((x) => x.d <= radio).sort((a, b) => a.d - b.d),
    [base, radio],
  );
  const nLejos = useMemo(() => base.filter((x) => x.d <= RADIO_LEJOS_M).length, [base]);
  const pendCerca = useMemo(
    () => (verCalles && capa && aqui ? pendientesCerca(capa.tramos, aqui, MAX_PENDIENTES) : []),
    [verCalles, capa, aqui],
  );
  const hayPendientes = !!capa && capa.tramos.some((t) => t.estado === "pendiente" || t.estado === "parcial");
  const tramoSel = calleSel && capa ? capa.tramos.find((t) => t.id === calleSel) ?? null : null;
  const pines = useMemo<PinAca[]>(
    () => cerca.map((x) => ({ id: x.id, nombre: x.nombre, lat: x.lat, lng: x.lng, thumb: x.thumb, plan: x.plan })),
    [cerca],
  );

  // ── Ficha ────────────────────────────────────────────────────
  const itemAbierto = abierto ? base.find((x) => x.id === abierto) ?? null : null;
  const comercioAbierto = abierto && items ? items.find((c) => c.id === abierto) ?? null : null;

  function abrir(id: string) {
    const it = base.find((x) => x.id === id);
    if (!it?.c) {
      // Sólo hay lo guardado: la ficha necesita la lista completa del servidor.
      setAviso(`La ficha de «${it?.nombre || "este local"}» necesita señal: sólo tengo guardado lo básico. Probá de nuevo cuando haya conexión.`);
      traerLista();
      return;
    }
    setAviso("");
    scrollLista.current = window.scrollY;
    setAbierto(id);
  }
  function cerrar() { restaurar.current = true; setAbierto(null); }
  useEffect(() => {
    if (!abierto && restaurar.current) { restaurar.current = false; window.scrollTo(0, scrollLista.current); }
  }, [abierto]);

  // Rubros y mercados, sólo al abrir una ficha (los necesita «Completar»).
  useEffect(() => {
    if (!abierto) return;
    let vivo = true;
    if (rubros.length === 0) getRubros().then((r) => { if (vivo) setRubros(r); }).catch(() => {});
    const slug = comercioAbierto?.ciudades?.slug ?? ciudadDelAgente ?? "bermejo";
    listarLugares(slug).then((l) => { if (vivo) setLugares(l); }).catch(() => {});
    return () => { vivo = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [abierto]);

  // Si el local abierto desaparece de la lista (baja, o llegó una lista nueva sin él), se vuelve.
  useEffect(() => { if (abierto && estado === "fresca" && !comercioAbierto) cerrar(); }, [abierto, estado, comercioAbierto]);

  if (comercioAbierto) {
    return (
      <div className="campo-wrap">
        <FichaAgente
          c={comercioAbierto}
          distancia={itemAbierto && Number.isFinite(itemAbierto.d) ? itemAbierto.d : null}
          rubros={rubros} lugares={lugares}
          onVolver={cerrar}
          onGuardado={(patch) => setItems((prev) => prev?.map((x) => (x.id === comercioAbierto.id ? { ...x, ...patch } : x)) ?? prev)}
        />
      </div>
    );
  }

  const gpsFlojo = aqui && aqui.acc > 50;

  return (
    <div className="campo-wrap" style={{ paddingBottom: 110 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
        <div>
          <span className="eyebrow"><Pin style={{ width: 13, height: 13 }} /> Qué hay acá</span>
          <div style={{ fontSize: 12, color: "var(--txt-3)" }}>¿Ya está cargado el local que tenés enfrente?</div>
        </div>
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap", justifyContent: "flex-end" }}>
          <button className="link-more" onClick={onMisComercios} style={{ padding: "6px 12px" }}>Mis comercios</button>
          {cabecera}
        </div>
      </div>

      {pendientes > 0 && (
        <div role="status" style={{ background: "rgba(240,160,40,.12)", border: "1px solid rgba(240,160,40,.45)", color: "var(--amber)", borderRadius: 12, padding: "10px 12px", marginBottom: 12, fontSize: 13, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
          <span><Ic n="reloj" s={14} /> {pendientes} {pendientes > 1 ? "altas guardadas" : "alta guardada"} sin subir.</span>
          <button type="button" className="btn btn-ghost" style={{ padding: "5px 12px", whiteSpace: "nowrap", minHeight: 44 }} onClick={onSubirPendientes}>Ver y subir</button>
        </div>
      )}

      {/* Capa de calles: el interruptor va arriba del mapa, que es lo que cambia. */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 8 }}>
        <button type="button" role="switch" aria-checked={verCalles} onClick={alternarCalles}
                style={{ minHeight: 44, padding: "6px 14px", borderRadius: 999, cursor: "pointer", fontWeight: 700, fontSize: 14, display: "inline-flex", alignItems: "center", gap: 8,
                         border: `2px solid ${verCalles ? "var(--neon)" : "var(--stroke)"}`, background: verCalles ? "rgba(18,161,95,.12)" : "transparent", color: "var(--txt)" }}>
          <Ic n="ruta" s={17} /> Calles
          <span style={{ fontSize: 12, fontWeight: 800, color: verCalles ? "var(--neon)" : "var(--txt-3)" }}>
            {verCalles ? <><Ic n="si" s={12} /> Sí</> : "No"}
          </span>
        </button>
        {verCalles && capa && capa.tramos.length > 0 && (
          <span style={{ fontSize: 12.5, color: "var(--txt-2)" }}>
            <b>{kmTxt(capa.resumen.km_recorridos)} de {kmTxt(capa.resumen.km_a_recorrer)} km recorridos ({pctTxt(capa.resumen.pct)} %)</b>
          </span>
        )}
      </div>
      {verCalles && capa && capa.tramos.length > 0 && <div style={{ marginBottom: 8 }}><LeyendaCalles /></div>}
      {verCalles && estCalles === "cargando" && !capa && (
        <p role="status" style={{ fontSize: 12.5, color: "var(--txt-3)", margin: "0 0 8px" }}><Ic n="reloj" s={13} /> Trayendo las calles…</p>
      )}
      {verCalles && estCalles === "guardada" && (
        <p role="status" style={{ fontSize: 12.5, color: "var(--amber)", margin: "0 0 8px" }}>
          <Ic n="aviso" s={12} /> Sin conexión: son las calles guardadas{fechaCalle(capaGuardada()?.guardada) ? ` el ${fechaCalle(capaGuardada()?.guardada)}` : ""} en el celular. Para marcar una calle hace falta señal.
        </p>
      )}
      {verCalles && estCalles === "sin-datos" && (
        <p role="alert" style={{ fontSize: 12.5, color: "var(--pink)", margin: "0 0 8px" }}>
          <Ic n="aviso" s={12} /> No se pudieron traer las calles y no hay una capa guardada en el celular.{" "}
          <button type="button" className="link-more" style={{ minHeight: 44 }} onClick={() => { setEstCalles("cargando"); traerCalles(); }}>Reintentar</button>
        </p>
      )}
      {verCalles && capa && capa.tramos.length === 0 && estCalles !== "cargando" && (
        <p role="status" style={{ fontSize: 12.5, color: "var(--txt-3)", margin: "0 0 8px" }}>
          <Ic n="dato" s={12} /> Esta ciudad todavía no tiene calles cargadas. Las trae el panel de administración.
        </p>
      )}

      <div ref={mapaRef} style={{ scrollMarginTop: 76 }}>
        <MapaAca aqui={aqui} pines={pines} encuadreM={radio} onSelect={abrir}
                 calles={verCalles && capa ? capa.tramos : null} calleSel={calleSel} onCalle={setCalleSel} />
        {tramoSel && (
          <div style={{ marginTop: 8 }}>
            <CallePanel tramo={tramoSel} verQuien onCerrar={() => setCalleSel(null)} onMarcar={(e, n) => marcarCalle(tramoSel.id, e, n)} />
          </div>
        )}
      </div>

      {/* Dónde estoy + actualizar */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, margin: "10px 0 6px", flexWrap: "wrap" }}>
        <span style={{ fontSize: 12.5, color: aqui ? "var(--txt-2)" : "var(--txt-3)" }}>
          {aqui
            ? <><Ic n="ubicacion" s={13} /> Tu ubicación, con ±{aqui.acc} m de precisión</>
            : buscandoGps ? <><Ic n="reloj" s={13} /> Tomando tu ubicación…</> : <><Ic n="aviso" s={13} /> Sin ubicación todavía</>}
        </span>
        <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} disabled={buscandoGps} onClick={() => { ubicar(); traerLista(); if (verCalles) traerCalles(); }}>
          <Ic n="actualizar" s={15} /> {buscandoGps ? "Ubicando…" : "Actualizar mi ubicación"}
        </button>
      </div>
      {gpsFlojo && (
        <p style={{ fontSize: 12, color: "var(--amber)", margin: "0 0 8px" }}>
          <Ic n="aviso" s={12} /> El GPS tiene ±{aqui.acc} m: las distancias pueden mostrar de más o de menos. Probá al aire libre.
        </p>
      )}
      {geoMsg && <PermisoUbicacion mensaje={geoMsg} onPedir={ubicar} motivo="Para mostrarte qué locales hay a tu alrededor" />}

      {estado === "guardada" && (
        <p role="status" style={{ fontSize: 12.5, color: "var(--amber)", margin: "0 0 8px" }}>
          <Ic n="aviso" s={12} /> Sin conexión: esta es la lista guardada en el celular, puede no tener lo último.
        </p>
      )}
      {estado === "sin-datos" && (
        <p role="alert" style={{ fontSize: 12.5, color: "var(--pink)", margin: "0 0 8px" }}>
          <Ic n="aviso" s={12} /> No se pudo traer la lista de locales y no hay una guardada en el celular. Podés cargar igual; el alta revisa duplicados cuando vuelva la señal.
        </p>
      )}
      {aviso && (
        <p role="alert" style={{ fontSize: 12.5, color: "var(--amber)", margin: "0 0 8px" }}><Ic n="aviso" s={12} /> {aviso}</p>
      )}

      {/* Calles pendientes cerca: la siguiente a la que ir. */}
      {verCalles && capa && capa.tramos.length > 0 && (
        <section aria-label="Calles pendientes cerca" style={{ margin: "14px 0 4px" }}>
          <h2 style={{ fontSize: 15, fontWeight: 700, margin: "0 0 8px" }}>Calles pendientes cerca</h2>
          {!aqui && (
            <p style={{ color: "var(--txt-3)", fontSize: 13, margin: 0 }}><Ic n="ubicacion" s={13} /> Necesito tu ubicación para decirte cuáles quedan cerca. Tocá «Actualizar mi ubicación».</p>
          )}
          {aqui && !hayPendientes && (
            <div style={vacio}><Ic n="listo" s={16} /> No quedan calles en rojo ni en ámbar en tu ciudad.</div>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {pendCerca.map(({ t, d }) => (
              <button key={t.id} type="button" onClick={() => elegirCalleDeLaLista(t.id)}
                      aria-label={`Ver la calle ${nombreCalle(t)}, ${Math.round(d)} metros`} aria-pressed={calleSel === t.id}
                      style={{ display: "flex", alignItems: "center", gap: 10, textAlign: "left", width: "100%", minHeight: 56, padding: "8px 12px", borderRadius: 12, cursor: "pointer",
                               border: `${calleSel === t.id ? 2 : 1}px solid ${calleSel === t.id ? "var(--neon)" : "var(--stroke)"}`, background: "var(--panel)", color: "inherit", font: "inherit" }}>
                <span style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{ fontWeight: 700, fontSize: 15, overflowWrap: "anywhere", color: t.nombre ? "var(--txt)" : "var(--txt-3)" }}>{nombreCalle(t)}</span>
                  <span style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                    <EstadoCalleTag estado={t.estado} />
                    <span style={{ fontSize: 12, color: "var(--txt-3)" }}>{Math.round(t.cobertura)} % cubierta</span>
                  </span>
                </span>
                <span style={{ fontSize: 13, color: "var(--neon)", fontWeight: 700, whiteSpace: "nowrap" }}>{metrosTxt(d)}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      {/* La lista */}
      <h2 style={{ fontSize: 15, fontWeight: 700, margin: "14px 0 8px" }}>
        {aqui ? `Cargados a menos de ${radio} m (${cerca.length})` : "Cargados cerca"}
      </h2>

      {estado === "cargando" && base.length === 0 && (
        <p style={{ color: "var(--txt-3)", fontSize: 13 }}><Ic n="reloj" s={13} /> Buscando los locales cargados…</p>
      )}
      {!aqui && !buscandoGps && base.length > 0 && !geoMsg && (
        <p style={{ color: "var(--txt-3)", fontSize: 13 }}>Necesito tu ubicación para decirte cuáles quedan cerca. Tocá «Actualizar mi ubicación».</p>
      )}
      {aqui && cerca.length === 0 && estado !== "cargando" && estado !== "sin-datos" && (
        <div style={vacio}>
          <Ic n="si" s={16} /> No hay locales cargados a menos de {radio} m. Si tenés uno enfrente, es nuevo: cargalo con el botón de abajo.
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {aqui && cerca.map((x) => (
          <button key={x.id} type="button" onClick={() => abrir(x.id)} aria-label={`Abrir la ficha de ${x.nombre || "local sin nombre"}`}
                  style={{ display: "flex", gap: 12, alignItems: "stretch", textAlign: "left", width: "100%", padding: 10, borderRadius: 14, cursor: "pointer",
                           border: "1px solid var(--stroke)", background: "var(--panel)", color: "inherit", font: "inherit" }}>
            <span style={{ width: 88, height: 88, borderRadius: 10, overflow: "hidden", flexShrink: 0, background: "#0b1411", display: "grid", placeItems: "center", color: "var(--txt-3)" }}>
              {x.thumb
                // eslint-disable-next-line @next/next/no-img-element
                ? <img src={x.thumb} alt="" loading="lazy" onError={(e) => { e.currentTarget.style.display = "none"; }} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                : <Ic n="comercios" s={30} />}
            </span>
            <span style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 3 }}>
              <span style={{ fontWeight: 700, fontSize: 15, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{x.nombre || "Sin nombre"}</span>
              <span style={{ fontSize: 12, color: "var(--txt-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{x.rubro ?? "Sin rubro"}</span>
              <span style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <span style={{ fontSize: 12.5, color: "var(--neon)", fontWeight: 700 }}>{metrosTxt(x.d)}</span>
                <SelloPlan plan={x.plan} />
              </span>
              {x.aprox && (
                <span style={{ fontSize: 12.5, fontWeight: 600, color: "var(--amber)", lineHeight: 1.3 }}>
                  <Ic n="ubicacion" s={13} /> Ubicación aproximada: confirmala con el GPS en la puerta
                </span>
              )}
              {x.faltan !== null && (
                x.faltan.length === 0
                  ? <span style={{ fontSize: 12.5, fontWeight: 700, color: "var(--neon)" }}><Ic n="listo" s={13} peso="fill" /> Completo</span>
                  : <span style={{ fontSize: 12.5, fontWeight: 600, color: "var(--amber)", lineHeight: 1.3 }}>
                      <Ic n="aviso" s={13} /> Le {x.faltan.length === 1 ? "falta 1" : `faltan ${x.faltan.length}`}: {x.faltan.join(", ")}
                    </span>
              )}
            </span>
          </button>
        ))}
      </div>

      {aqui && radio === RADIO_CERCA_M && (
        <button type="button" className="btn btn-ghost" style={{ width: "100%", minHeight: 48, marginTop: 12 }} onClick={() => setRadio(RADIO_LEJOS_M)}>
          Ver más lejos (hasta {RADIO_LEJOS_M} m){nLejos > cerca.length ? ` · ${nLejos - cerca.length} más` : ""}
        </button>
      )}
      {aqui && radio === RADIO_LEJOS_M && (
        <button type="button" className="link-more" style={{ marginTop: 10, minHeight: 44 }} onClick={() => setRadio(RADIO_CERCA_M)}>
          Volver a {RADIO_CERCA_M} m
        </button>
      )}

      {/* El botón fijo: siempre a mano, aunque la lista sea larga. */}
      <div style={{ position: "fixed", left: 0, right: 0, bottom: 0, zIndex: 700, display: "flex", justifyContent: "center", padding: "10px 18px calc(10px + env(safe-area-inset-bottom))", background: "linear-gradient(to top, var(--bg, #0b1411) 70%, transparent)", pointerEvents: "none" }}>
        <button type="button" className="btn btn-primary" style={{ width: "100%", maxWidth: 424, minHeight: 54, fontSize: 16, pointerEvents: "auto" }} onClick={() => onCargarNuevo(aqui)}>
          <Ic n="mas" s={18} /> Cargar un local nuevo acá
        </button>
      </div>
    </div>
  );
}

const vacio: React.CSSProperties = {
  padding: 12, borderRadius: 12, border: "1px dashed var(--stroke)", color: "var(--txt-2)", fontSize: 13.5, lineHeight: 1.4,
};
