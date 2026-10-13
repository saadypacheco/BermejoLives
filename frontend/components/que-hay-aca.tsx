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
 */
import { useEffect, useMemo, useRef, useState } from "react";
import {
  misComercios, ciudadDelAgente, listarLugares, type ComercioAgente, type EstadoPlan, type Lugar,
} from "@/lib/campo";
import { aCercanos, cercanosGuardados, listaEnMemoria, recordarLista, type ComercioCercano } from "@/lib/campo-cache";
import { calcularFaltas, etiquetasFaltas } from "@/lib/faltas";
import { geoErrorMsg, metros } from "@/lib/geo";
import { getRubros } from "@/lib/data";
import { listarPendientes } from "@/lib/offline-altas";
import type { Rubro } from "@/lib/types";
import { MapaAca, type PosicionAca, type PinAca } from "@/components/mapa-aca";
import { FichaAgente } from "@/components/ficha-agente";
import { SelloPlan } from "@/components/sello-plan";
import { PermisoUbicacion } from "@/components/permiso-ubicacion";
import { Ic } from "@/components/ic";
import { Pin } from "@/components/icons";

/** Hasta dónde llega la lista al abrir, y hasta dónde con «Ver más lejos». */
export const RADIO_CERCA_M = 150;
export const RADIO_LEJOS_M = 400;

type EstadoDatos = "cargando" | "fresca" | "guardada" | "sin-datos";

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
};

function desdeComercio(c: ComercioAgente, aqui: PosicionAca | null): ItemAca | null {
  if (c.lat == null || c.lng == null) return null;
  return {
    id: c.id, nombre: c.nombre ?? "", lat: c.lat, lng: c.lng,
    rubro: c.rubros?.nombre ?? null, thumb: c.portada_thumb_url || c.portada_url || null,
    plan: c.estado_plan ?? null,
    faltan: etiquetasFaltas(calcularFaltas(c, c.fotos_count ?? null)),
    c, d: aqui ? metros(aqui.lat, aqui.lng, c.lat, c.lng) : Infinity,
  };
}

function desdeGuardado(x: ComercioCercano, aqui: PosicionAca | null): ItemAca {
  return {
    id: x.id, nombre: x.nombre, lat: x.lat, lng: x.lng, rubro: x.rubro, thumb: x.thumb,
    plan: x.plan ?? null, faltan: x.faltan ?? null, c: null,
    d: aqui ? metros(aqui.lat, aqui.lng, x.lat, x.lng) : Infinity,
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

      <MapaAca aqui={aqui} pines={pines} encuadreM={radio} onSelect={abrir} />

      {/* Dónde estoy + actualizar */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, margin: "10px 0 6px", flexWrap: "wrap" }}>
        <span style={{ fontSize: 12.5, color: aqui ? "var(--txt-2)" : "var(--txt-3)" }}>
          {aqui
            ? <><Ic n="ubicacion" s={13} /> Tu ubicación, con ±{aqui.acc} m de precisión</>
            : buscandoGps ? <><Ic n="reloj" s={13} /> Tomando tu ubicación…</> : <><Ic n="aviso" s={13} /> Sin ubicación todavía</>}
        </span>
        <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} disabled={buscandoGps} onClick={() => { ubicar(); traerLista(); }}>
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
