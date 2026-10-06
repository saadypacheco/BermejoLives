"use client";

// Admin › Cargas: cómo trabajó cada agente un día — a qué hora empezó, cuánto
// paró, cuántos comercios cargó por hora y por dónde anduvo.
//
// Lee de `/admin/cargas/dia` y `/admin/cargas/historial` (ver
// docs/cargas-del-dia.md). Respeta el selector de ciudad del panel.
//
// LA HORA
// =======
// Es la del celular (`capturado_en`) cuando existe; si no, la de llegada al
// servidor. Los comercios cargados antes del 6/10/2026 no tienen la del
// celular, así que lo que se subió de golpe al volver la señal aparece
// amontonado. Cada punto trae `hora_del_celular` para decirlo.

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  cargasDia, cargasHistorial,
  type CargaAgente, type CargaHistorialItem, type CargaPunto, type CargasDia,
} from "@/lib/api";
import { useAdminCiudad } from "@/components/admin-ciudad";
import { Ic } from "@/components/ic";
import { agregarTiles } from "@/lib/mapa-tiles";
import { escapeHtml, loadLeaflet } from "@/lib/mapa-visual";

// ── Helpers ────────────────────────────────────────────────────────────────

/** Hoy en Bolivia (UTC−4 fijo, sin horario de verano), como YYYY-MM-DD. */
function hoyBolivia(): string {
  return new Date(Date.now() - 4 * 3600 * 1000).toISOString().slice(0, 10);
}

/** «6 h 35 min», «45 min», «0 min». */
function duracion(min: number): string {
  const m = Math.max(0, Math.round(min));
  const h = Math.floor(m / 60);
  const r = m % 60;
  if (h === 0) return `${r} min`;
  return r === 0 ? `${h} h` : `${h} h ${r} min`;
}

/** Kilómetros con un decimal y coma: «4,2 km». */
function km(metros: number): string {
  return `${(metros / 1000).toLocaleString("es-AR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} km`;
}

/** Distancia corta: «350 m» hasta el kilómetro, después «1,2 km». */
function distanciaCorta(m: number): string {
  return m < 1000 ? `${Math.round(m)} m` : km(m);
}

/** «mar 6/10» a partir de YYYY-MM-DD. Se arma en UTC: es una fecha de
 *  calendario, no un instante, y pasarla por la zona local la corría un día. */
function fechaCorta(fecha: string): string {
  const d = new Date(`${fecha}T12:00:00Z`);
  if (Number.isNaN(d.getTime())) return fecha;
  return d.toLocaleDateString("es-AR", { weekday: "short", day: "numeric", month: "numeric", timeZone: "UTC" });
}

function nombreAgente(a: { agente: string; agente_nombre?: string | null }): string {
  return a.agente_nombre?.trim() || a.agente;
}

/** Un color por tramo. Se repiten si hay más de seis; con una jornada normal
 *  (mañana, tarde, otra zona) no pasa. */
const COLORES_TRAMO = ["#39ff9e", "#2e6bff", "#ffc23d", "#ff4d8d", "#9b5cff", "#ff8a3d"];
const colorTramo = (tramo: number) => COLORES_TRAMO[(Math.max(1, tramo) - 1) % COLORES_TRAMO.length];

const BERMEJO: [number, number] = [-22.7361, -64.3433];

function mensajeError(e: unknown): string {
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return "Sin conexión. Revisá la señal y volvé a intentar.";
  }
  return e instanceof Error && e.message ? e.message : "No se pudo cargar. Probá de nuevo.";
}

// ── Mapa del recorrido ─────────────────────────────────────────────────────
// Leaflet se carga por `loadLeaflet` (CDN, una sola vez), así que acá no hay
// tipos del paquete: sólo lo que se usa, dicho en texto.

type LCapaItem = { addTo(c: LCapa): LCapaItem; bindPopup(html: string, o?: object): LCapaItem };
type LCapa = { clearLayers(): void; addTo(m: LMapa): LCapa };
type LMapa = {
  remove(): void; invalidateSize(): void;
  setView(c: [number, number], z: number): LMapa;
  fitBounds(b: [number, number][], o: { padding: [number, number]; maxZoom: number }): void;
};
type LLeaflet = {
  map(el: HTMLElement, o: object): LMapa;
  layerGroup(): LCapa;
  marker(ll: [number, number], o: object): LCapaItem;
  polyline(ll: [number, number][], o: object): LCapaItem;
  divIcon(o: object): unknown;
};

/** La foto sólo si es una URL normal: va a un atributo de HTML armado a mano. */
function fotoSegura(url: string | null): string | null {
  return url && /^(https?:\/\/|\/)/.test(url) ? url : null;
}

function htmlPopup(p: CargaPunto): string {
  const foto = fotoSegura(p.foto);
  return `<div style="max-width:210px">`
    + `<b>${p.orden}. ${escapeHtml(p.nombre || "Sin nombre")}</b><br>`
    + `<span style="opacity:.75">${escapeHtml(p.hora)}${p.hora_del_celular ? "" : " (llegada al servidor)"}</span>`
    + (foto ? `<img src="${escapeHtml(foto)}" alt="" loading="lazy" style="display:block;width:100%;max-height:140px;object-fit:cover;border-radius:8px;margin-top:6px">` : "")
    + `</div>`;
}

function iconoNumero(L: LLeaflet, p: CargaPunto) {
  const c = colorTramo(p.tramo);
  const html = `<div style="width:26px;height:26px;border-radius:50%;background:${c};color:#060911;`
    + `font:800 12px/24px system-ui,sans-serif;text-align:center;border:2px solid #fff;`
    + `box-shadow:0 1px 6px rgba(0,0,0,.55)">${p.orden}</div>`;
  return L.divIcon({ className: "", html, iconSize: [26, 26], iconAnchor: [13, 13], popupAnchor: [0, -14] });
}

function RecorridoMapa({ puntos }: { puntos: CargaPunto[] }) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LMapa | null>(null);
  const capaRef = useRef<LCapa | null>(null);
  const [falloMapa, setFalloMapa] = useState(false);

  useEffect(() => {
    let cancelado = false;
    loadLeaflet().then((L: LLeaflet) => {
      if (cancelado || !elRef.current) return;
      if (!mapRef.current) {
        const map = L.map(elRef.current, { attributionControl: false }).setView(BERMEJO, 15);
        mapRef.current = map;
        agregarTiles(L, map, { oscuro: true });
        capaRef.current = L.layerGroup().addTo(map);
        setTimeout(() => map.invalidateSize(), 60);
      }
      const map = mapRef.current;
      const capa = capaRef.current;
      if (!map || !capa) return;
      capa.clearLayers();

      const conGps = puntos.filter((p) => p.lat != null && p.lng != null);
      const bounds: [number, number][] = [];

      // Una línea por tramo, de su color; entre un tramo y el siguiente, una
      // línea punteada y tenue: el salto existe, pero no es recorrido de trabajo.
      const tramos = new Map<number, CargaPunto[]>();
      for (const p of conGps) tramos.set(p.tramo, [...(tramos.get(p.tramo) ?? []), p]);
      const ordenados = [...tramos.entries()].sort((a, b) => a[0] - b[0]);
      ordenados.forEach(([n, lista], i) => {
        const ll = lista.map((p) => [p.lat as number, p.lng as number] as [number, number]);
        if (ll.length > 1) L.polyline(ll, { color: colorTramo(n), weight: 4, opacity: 0.85 }).addTo(capa);
        const sig = ordenados[i + 1];
        if (sig) {
          const a = ll[ll.length - 1];
          const b: [number, number] = [sig[1][0].lat as number, sig[1][0].lng as number];
          L.polyline([a, b], { color: "#aab3c8", weight: 2, opacity: 0.6, dashArray: "4 8" }).addTo(capa);
        }
      });

      for (const p of conGps) {
        const ll: [number, number] = [p.lat as number, p.lng as number];
        L.marker(ll, { icon: iconoNumero(L, p), title: `${p.orden}. ${p.nombre}`, keyboard: true })
          .bindPopup(htmlPopup(p), { maxWidth: 230 })
          .addTo(capa);
        bounds.push(ll);
      }

      if (bounds.length > 1) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 17 });
      else if (bounds.length === 1) map.setView(bounds[0], 16);
    }).catch(() => { if (!cancelado) setFalloMapa(true); });
    return () => { cancelado = true; };
  }, [puntos]);

  // Al desmontar se suelta el mapa entero (si no, Leaflet deja escuchas sobre
  // un nodo que ya no existe).
  useEffect(() => () => {
    mapRef.current?.remove();
    mapRef.current = null;
    capaRef.current = null;
  }, []);

  const sinGps = puntos.filter((p) => p.lat == null || p.lng == null).length;

  return (
    <div>
      {falloMapa && (
        <p style={{ color: "var(--amber)", fontSize: 13, marginBottom: 8 }}>
          <Ic n="aviso" s={14} /> No se pudo cargar el mapa. La lista de abajo tiene todo igual.
        </p>
      )}
      <div ref={elRef} role="region" aria-label="Mapa del recorrido del día, con los comercios numerados en orden"
           style={{ height: "clamp(280px, 55vh, 440px)", borderRadius: 12, overflow: "hidden", border: "1px solid var(--border)" }} />
      <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 14px", marginTop: 8, fontSize: 12, color: "var(--txt-3)" }}>
        <span>Un color por tramo; la línea punteada une un tramo con el siguiente.</span>
        {sinGps > 0 && <span style={{ color: "var(--amber)" }}><Ic n="aviso" s={12} /> {sinGps} sin ubicación (no se dibujan)</span>}
      </div>
    </div>
  );
}

// ── Barras por hora ────────────────────────────────────────────────────────

function BarrasPorHora({ porHora }: { porHora: { hora: string; comercios: number }[] }) {
  const mapa = new Map(porHora.map((h) => [Number(h.hora), h.comercios]));
  const horas = [...mapa.keys()].filter((h) => Number.isFinite(h));
  if (horas.length === 0) return null;
  // Se rellenan las horas vacías entre la primera y la última: una pausa tiene
  // que verse como un hueco, no desaparecer.
  const desde = Math.min(...horas);
  const hasta = Math.max(...horas);
  const serie: { hora: number; n: number }[] = [];
  for (let h = desde; h <= hasta; h++) serie.push({ hora: h, n: mapa.get(h) ?? 0 });
  const max = Math.max(1, ...serie.map((s) => s.n));

  return (
    <div style={{ overflowX: "auto" }}>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 6, height: 120, minWidth: serie.length * 34, paddingTop: 4 }}>
        {serie.map((s) => (
          <div key={s.hora} style={{ flex: "1 0 28px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end", height: "100%" }}
               title={`${String(s.hora).padStart(2, "0")}:00 — ${s.n} ${s.n === 1 ? "comercio" : "comercios"}`}>
            <span style={{ fontSize: 11, fontWeight: 700, color: s.n ? "var(--txt)" : "var(--txt-3)", marginBottom: 2 }}>{s.n}</span>
            <div style={{
              width: "100%", maxWidth: 28, borderRadius: "5px 5px 0 0",
              height: s.n ? `${Math.max(6, (s.n / max) * 80)}%` : 2,
              background: s.n ? "var(--neon)" : "var(--stroke-2)", opacity: s.n ? 0.85 : 1,
            }} />
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 6, minWidth: serie.length * 34, borderTop: "1px solid var(--stroke-2)", paddingTop: 3 }}>
        {serie.map((s) => (
          <span key={s.hora} style={{ flex: "1 0 28px", textAlign: "center", fontSize: 10.5, color: "var(--txt-3)" }}>
            {String(s.hora).padStart(2, "0")}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Pieza reutilizable: estado de una carga (cargando / error) ──────────────

function EstadoCarga({ cargando, error, onReintentar, textoCargando }: {
  cargando: boolean; error: string | null; onReintentar: () => void; textoCargando: string;
}) {
  if (error) {
    return (
      <div role="alert" style={{ color: "var(--pink)", fontSize: 14, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10 }}>
        <span><Ic n="aviso" s={16} /> {error}</span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onReintentar}>Reintentar</button>
      </div>
    );
  }
  if (cargando) {
    return <p role="status" style={{ color: "var(--txt-3)", fontSize: 14 }}><Ic n="reloj" s={15} /> {textoCargando}</p>;
  }
  return null;
}

const th: React.CSSProperties = { padding: "6px 8px", textAlign: "right", whiteSpace: "nowrap", fontWeight: 600 };
const td: React.CSSProperties = { padding: "8px 8px", textAlign: "right", whiteSpace: "nowrap" };

// ── El panel ───────────────────────────────────────────────────────────────

export function CargasPanel() {
  const { slug, listo } = useAdminCiudad();

  const [historial, setHistorial] = useState<CargaHistorialItem[] | null>(null);
  const [errHist, setErrHist] = useState<string | null>(null);
  const [reintentoHist, setReintentoHist] = useState(0);

  const [fecha, setFecha] = useState(hoyBolivia);
  const [agente, setAgente] = useState<string | null>(null);
  const [dia, setDia] = useState<CargasDia | null>(null);
  const [errDia, setErrDia] = useState<string | null>(null);
  const [reintentoDia, setReintentoDia] = useState(0);

  const diaRef = useRef<HTMLDivElement>(null);
  const hoy = hoyBolivia();

  // Historial: se pide de nuevo al cambiar la ciudad.
  useEffect(() => {
    if (!listo) return;
    let vivo = true;
    setHistorial(null);
    setErrHist(null);
    cargasHistorial(60, slug)
      .then((r) => { if (vivo) setHistorial(r.items ?? []); })
      .catch((e) => { if (vivo) setErrHist(mensajeError(e)); });
    return () => { vivo = false; };
  }, [slug, listo, reintentoHist]);

  // El día: al cambiar la fecha o la ciudad. `vivo` evita que una respuesta
  // lenta de un día pise a la del día que se eligió después.
  useEffect(() => {
    if (!listo) return;
    let vivo = true;
    setDia(null);
    setErrDia(null);
    cargasDia(fecha, slug)
      .then((r) => { if (vivo) setDia({ ...r, agentes: r.agentes ?? [] }); })
      .catch((e) => { if (vivo) setErrDia(mensajeError(e)); });
    return () => { vivo = false; };
  }, [fecha, slug, listo, reintentoDia]);

  // Agente elegido: el que ya estaba si cargó ese día; si no, el primero.
  const agentes = dia?.agentes ?? [];
  const actual: CargaAgente | null = agentes.find((a) => a.agente === agente) ?? agentes[0] ?? null;

  const abrirDia = useCallback((item: CargaHistorialItem) => {
    setFecha(item.fecha);
    setAgente(item.agente);
    // En el celular el día queda debajo de la pantalla: se lleva la vista.
    setTimeout(() => diaRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <h2 style={{ fontSize: 20, marginBottom: 4 }}><Ic n="ruta" s={20} tono="marca" /> Cargas del día</h2>
        <p style={{ fontSize: 13, color: "var(--txt-3)" }}>
          Qué cargó cada agente, cuándo y por dónde anduvo.
        </p>
      </div>

      <p style={{ fontSize: 12.5, color: "var(--amber)", display: "flex", gap: 6, alignItems: "flex-start" }}>
        <Ic n="aviso" s={14} style={{ marginTop: 2 }} />
        <span>
          Antes del 6/10/2026 la hora es la de llegada al servidor, así que lo
          cargado sin señal puede aparecer amontonado. Desde entonces es la del
          celular: si un agente tiene el reloj atrasado, sus cargas salen corridas
          y marcadas como «subido más tarde» aunque haya tenido señal.
        </span>
      </p>

      {/* ── Historial ── */}
      <section className="panel-card glass" style={{ padding: 16 }} aria-labelledby="cargas-hist">
        <h3 id="cargas-hist" style={{ marginBottom: 4 }}>Historial</h3>
        <p style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 12 }}>
          Últimos 60 días. Tocá una fila para abrir ese día y ese agente.
        </p>
        <EstadoCarga cargando={historial === null && !errHist} error={errHist}
                     onReintentar={() => setReintentoHist((n) => n + 1)} textoCargando="Cargando el historial…" />
        {historial !== null && historial.length === 0 && (
          <p style={{ color: "var(--txt-3)", fontSize: 14 }}><Ic n="dato" s={15} /> Nadie cargó comercios en los últimos 60 días.</p>
        )}
        {historial !== null && historial.length > 0 && (
          <div style={{ overflowX: "auto", maxHeight: 360, overflowY: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ color: "var(--txt-3)", fontSize: 11 }}>
                  <th style={{ ...th, textAlign: "left" }}>Fecha</th>
                  <th style={{ ...th, textAlign: "left" }}>Agente</th>
                  <th style={th}>Comercios</th>
                  <th style={th}>Desde–hasta</th>
                  <th style={th}>Trabajado</th>
                  <th style={th}>Km</th>
                </tr>
              </thead>
              <tbody>
                {historial.map((h) => {
                  const abierta = h.fecha === fecha && actual?.agente === h.agente;
                  return (
                    <tr key={`${h.fecha}|${h.agente}`} onClick={() => abrirDia(h)}
                        style={{ borderTop: "1px solid var(--border)", cursor: "pointer", background: abierta ? "rgba(57,255,158,.08)" : undefined }}>
                      <td style={{ ...td, textAlign: "left" }}>
                        <button type="button" onClick={(e) => { e.stopPropagation(); abrirDia(h); }}
                                aria-label={`Abrir el ${h.fecha} de ${nombreAgente(h)}`}
                                style={{ background: "none", border: 0, padding: "4px 0", color: abierta ? "var(--neon)" : "var(--txt)", fontWeight: 700, cursor: "pointer", font: "inherit" }}>
                          {fechaCorta(h.fecha)}
                        </button>
                      </td>
                      <td style={{ ...td, textAlign: "left", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis" }}>{nombreAgente(h)}</td>
                      <td style={{ ...td, fontWeight: 700 }}>{h.comercios}</td>
                      <td style={td}>{h.desde}–{h.hasta}</td>
                      <td style={td}>{duracion(h.minutos_trabajados)}</td>
                      <td style={{ ...td, color: "var(--txt-3)" }}>{(h.metros / 1000).toLocaleString("es-AR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── El día ── */}
      <section ref={diaRef} className="panel-card glass" style={{ padding: 16, scrollMarginTop: 12 }} aria-labelledby="cargas-dia">
        <h3 id="cargas-dia" style={{ marginBottom: 12 }}>El día</h3>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "flex-end", marginBottom: 14 }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12, color: "var(--txt-3)" }}>
            <span><Ic n="calendario" s={13} /> Fecha</span>
            <input type="date" className="adm-input" style={{ width: "auto" }} value={fecha} max={hoy}
                   onChange={(e) => { if (e.target.value) { setFecha(e.target.value); setAgente(null); } }} />
          </label>
          {fecha !== hoy && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setFecha(hoy); setAgente(null); }}>Hoy</button>
          )}
          {agentes.length > 0 && (
            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12, color: "var(--txt-3)", minWidth: 0 }}>
              <span><Ic n="usuario" s={13} /> Agente</span>
              <select className="adm-input" style={{ width: "auto", maxWidth: "100%" }}
                      value={actual?.agente ?? ""} onChange={(e) => setAgente(e.target.value)}>
                {agentes.map((a) => (
                  <option key={a.agente} value={a.agente}>{nombreAgente(a)} ({a.comercios})</option>
                ))}
              </select>
            </label>
          )}
        </div>

        <EstadoCarga cargando={dia === null && !errDia} error={errDia}
                     onReintentar={() => setReintentoDia((n) => n + 1)} textoCargando="Cargando el día…" />

        {dia !== null && agentes.length === 0 && (
          <p style={{ color: "var(--txt-3)", fontSize: 14 }}><Ic n="dato" s={15} /> Nadie cargó comercios ese día.</p>
        )}

        {dia !== null && actual && <DiaDelAgente key={`${dia.fecha}|${actual.agente}`} a={actual} />}
      </section>
    </div>
  );
}

// ── Resumen + barras + mapa + lista de un agente ───────────────────────────

function Dato({ etiqueta, valor, nota }: { etiqueta: string; valor: string; nota?: string }) {
  return (
    <div style={{ padding: "10px 12px", borderRadius: 12, background: "var(--panel)", border: "1px solid var(--stroke)", minWidth: 0 }}>
      <div style={{ fontSize: 11, color: "var(--txt-3)" }}>{etiqueta}</div>
      <div style={{ fontSize: 20, fontWeight: 700 }}>{valor}</div>
      {nota && <div style={{ fontSize: 11, color: "var(--txt-3)" }}>{nota}</div>}
    </div>
  );
}

function DiaDelAgente({ a }: { a: CargaAgente }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {/* Resumen */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 10 }}>
        <Dato etiqueta="Comercios" valor={String(a.comercios)} />
        <Dato etiqueta="Desde–hasta" valor={`${a.desde}–${a.hasta}`} />
        <Dato etiqueta="Tiempo trabajado" valor={duracion(a.minutos_trabajados)} />
        <Dato etiqueta="Recorrido" valor={km(a.metros)} nota="en línea recta" />
        <Dato etiqueta="Tramos" valor={String(a.tramos.length)} nota="pausa de más de 30 min" />
      </div>

      {a.tramos.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 14px", fontSize: 12.5 }}>
          {a.tramos.map((t) => (
            <span key={t.n} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <span aria-hidden style={{ width: 10, height: 10, borderRadius: "50%", background: colorTramo(t.n), display: "inline-block" }} />
              <span><b>Tramo {t.n}</b> {t.desde}–{t.hasta} · {duracion(t.minutos)} · {t.comercios} {t.comercios === 1 ? "comercio" : "comercios"}</span>
            </span>
          ))}
        </div>
      )}

      {/* Barras por hora */}
      <div>
        <h4 style={{ fontSize: 13, marginBottom: 6 }}>Comercios por hora</h4>
        <BarrasPorHora porHora={a.por_hora} />
      </div>

      {/* Recorrido */}
      <div>
        <h4 style={{ fontSize: 13, marginBottom: 6 }}>El recorrido</h4>
        <RecorridoMapa puntos={a.puntos} />
      </div>

      {/* Lista */}
      <div>
        <h4 style={{ fontSize: 13, marginBottom: 6 }}>Uno por uno</h4>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ color: "var(--txt-3)", fontSize: 11 }}>
                <th style={{ ...th, textAlign: "left" }}>#</th>
                <th style={{ ...th, textAlign: "left" }}>Hora</th>
                <th style={{ ...th, textAlign: "left" }}>Comercio</th>
                <th style={th}>Desde el anterior</th>
              </tr>
            </thead>
            <tbody>
              {a.puntos.map((p) => (
                <tr key={p.id} style={{ borderTop: "1px solid var(--border)" }}>
                  <td style={{ ...td, textAlign: "left", fontWeight: 700 }}>
                    <span aria-hidden style={{ width: 8, height: 8, borderRadius: "50%", background: colorTramo(p.tramo), display: "inline-block", marginRight: 6 }} />
                    {p.orden}
                  </td>
                  <td style={{ ...td, textAlign: "left" }}>
                    {p.hora}
                    {!p.hora_del_celular && (
                      <span title="Esta hora es la de llegada al servidor, no la del celular"
                            style={{ fontSize: 10.5, color: "var(--txt-3)", marginLeft: 4 }}>(servidor)</span>
                    )}
                  </td>
                  <td style={{ ...td, textAlign: "left", whiteSpace: "normal", minWidth: 150 }}>
                    {p.slug ? (
                      <Link href={`/comercios/${encodeURIComponent(p.slug)}`} style={{ color: "var(--neon)" }}>
                        {p.nombre || "Sin nombre"}
                      </Link>
                    ) : (p.nombre || "Sin nombre")}
                    {p.subido_tarde && (
                      <div style={{ fontSize: 11, color: "var(--amber)", marginTop: 2 }}>
                        <Ic n="reloj" s={12} /> subido más tarde (sin señal)
                      </div>
                    )}
                    {p.lat == null || p.lng == null ? (
                      <div style={{ fontSize: 11, color: "var(--txt-3)", marginTop: 2 }}>sin ubicación</div>
                    ) : null}
                  </td>
                  <td style={{ ...td, color: "var(--txt-2)" }}>
                    {p.min_desde_anterior === null && p.m_desde_anterior === null
                      ? "—"
                      : [
                          p.min_desde_anterior !== null ? duracion(p.min_desde_anterior) : null,
                          p.m_desde_anterior !== null ? distanciaCorta(p.m_desde_anterior) : null,
                        ].filter(Boolean).join(" · ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
