"use client";

import { useCallback, useEffect, useState } from "react";
import { Ic } from "@/components/ic";
import { BTN_GRANDE, Cargando, ErrorConReintento, Insignia } from "@/components/content/content-ui";
import { SubscriberDetail } from "@/components/subscribers/subscriber-detail";
import { SubscriberTaskRow } from "@/components/subscribers/subscriber-task-row";
import { mensajeContent } from "@/lib/content";
import { etiquetaDe, fechaCorta, SUBSCRIPTION_STATE_LABEL } from "@/lib/content-pure";
import {
  listarSuscriptores, listarTareas, type SubscriberCuando, type SubscriberFiltro, type SubscriberListResponse,
  type SubscriberSummaryResponse, type SubscriberTaskListResponse, type SubscriberTaskResponse,
} from "@/lib/subscribers";

const FILTROS: { v: SubscriberFiltro; t: string }[] = [
  { v: "tareas", t: "Con tareas hoy" },
  { v: "por_vencer", t: "Por vencer" },
  { v: "todos", t: "Todos" },
];
const CUANDO: { v: SubscriberCuando; t: string }[] = [
  { v: "hoy", t: "Hoy" },
  { v: "atrasadas", t: "Atrasadas" },
  { v: "semana", t: "Esta semana" },
];

/**
 * Admin › Cuidar suscriptores (§9.4): quién paga, qué tarea toca hoy con cada uno
 * y si autorizó las redes. Cada tarea de mensaje se manda por WhatsApp de la
 * persona (botón que abre `wa.me` con el texto armado); nada sale solo.
 *
 * `ciudadSlug` es la ciudad de la barra de arriba del panel (null = todas).
 */
export function SubscribersPanel({ ciudadSlug }: { ciudadSlug: string | null }) {
  const [vista, setVista] = useState<"suscriptores" | "tareas">("suscriptores");
  const [filtro, setFiltro] = useState<SubscriberFiltro>("tareas");
  const [cuando, setCuando] = useState<SubscriberCuando>("hoy");
  const [lista, setLista] = useState<SubscriberListResponse | null>(null);
  const [tareas, setTareas] = useState<SubscriberTaskListResponse | null>(null);
  const [cargando, setCargando] = useState(true);
  const [err, setErr] = useState("");
  const [abierto, setAbierto] = useState<string | null>(null);

  const cargar = useCallback(async (silencioso = false) => {
    if (!silencioso) setCargando(true);
    setErr("");
    try {
      if (vista === "suscriptores") setLista(await listarSuscriptores(filtro, ciudadSlug));
      else setTareas(await listarTareas(cuando));
    } catch (ex) { setErr(mensajeContent(ex, "No se pudo cargar")); }
    finally { setCargando(false); }
  }, [vista, filtro, cuando, ciudadSlug]);

  useEffect(() => { void cargar(); }, [cargar]);

  if (abierto) {
    return (
      <div style={{ maxWidth: 760 }}>
        <SubscriberDetail comercioId={abierto} onVolver={() => setAbierto(null)} onCambio={() => void cargar(true)} />
      </div>
    );
  }

  const items = lista?.items ?? [];
  const paraHoy = items.reduce((n, s) => n + s.tasks.due_today, 0);
  const atrasadas = items.reduce((n, s) => n + s.tasks.overdue, 0);

  function tareaCambio(t: SubscriberTaskResponse) {
    setTareas((x) => (x ? { ...x, items: x.items.map((y) => (y.id === t.id ? t : y)) } : x));
  }

  return (
    <div style={{ display: "grid", gap: 14, maxWidth: 760 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <div role="tablist" aria-label="Vista" style={{ display: "flex", gap: 8 }}>
          <button type="button" role="tab" aria-selected={vista === "suscriptores"} className={`btn btn-sm ${vista === "suscriptores" ? "btn-primary" : "btn-ghost"}`} style={BTN_GRANDE} onClick={() => setVista("suscriptores")}>
            <Ic n="gente" s={15} /> Suscriptores
          </button>
          <button type="button" role="tab" aria-selected={vista === "tareas"} className={`btn btn-sm ${vista === "tareas" ? "btn-primary" : "btn-ghost"}`} style={BTN_GRANDE} onClick={() => setVista("tareas")}>
            <Ic n="listo" s={15} /> Tareas
          </button>
        </div>
        {vista === "suscriptores" ? (
          <select className="adm-input" aria-label="Filtro" style={{ minHeight: 48, width: "auto" }} value={filtro} onChange={(e) => setFiltro(e.target.value as SubscriberFiltro)}>
            {FILTROS.map((f) => <option key={f.v} value={f.v}>{f.t}</option>)}
          </select>
        ) : (
          <select className="adm-input" aria-label="Cuándo" style={{ minHeight: 48, width: "auto" }} value={cuando} onChange={(e) => setCuando(e.target.value as SubscriberCuando)}>
            {CUANDO.map((f) => <option key={f.v} value={f.v}>{f.t}</option>)}
          </select>
        )}
        <button type="button" className="btn btn-ghost btn-sm" style={{ ...BTN_GRANDE, marginLeft: "auto" }} onClick={() => void cargar()} disabled={cargando}>
          <Ic n="actualizar" s={15} /> Actualizar
        </button>
      </div>

      {vista === "suscriptores" && lista && (
        <b style={{ fontSize: 14 }}>Para hacer hoy: {paraHoy} · atrasadas: {atrasadas}</b>
      )}

      {cargando && !(vista === "suscriptores" ? lista : tareas) && <Cargando texto="Cargando…" />}
      {err && <ErrorConReintento mensaje={err} onReintentar={() => void cargar()} />}

      {vista === "suscriptores" && lista && !err && (
        <>
          {items.length === 0 && (
            <p style={{ margin: 0, fontSize: 14, color: "var(--txt-3)", lineHeight: 1.5 }}>
              {filtro === "tareas" ? "No hay tareas para hoy. Podés mirar «Todos» para ver a todos los suscriptores." : "No hay suscriptores para mostrar."}
            </p>
          )}
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8 }}>
            {items.map((s) => <li key={s.comercio_id}><FilaSuscriptor s={s} onAbrir={() => setAbierto(s.comercio_id)} /></li>)}
          </ul>
        </>
      )}

      {vista === "tareas" && tareas && !err && (
        <>
          {tareas.items.length === 0 && <p style={{ margin: 0, fontSize: 14, color: "var(--txt-3)" }}>No hay tareas para este período.</p>}
          {tareas.items.map((t) => (
            <div key={t.id} className="panel-card glass" style={{ padding: "4px 14px 10px" }}>
              <SubscriberTaskRow t={t} onCambio={tareaCambio} mostrarComercio />
              <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => setAbierto(t.comercio_id)}>
                <Ic n="seguir" s={15} /> Ver a {t.comercio_nombre}
              </button>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

function FilaSuscriptor({ s, onAbrir }: { s: SubscriberSummaryResponse; onAbrir: () => void }) {
  const mal = s.subscription_state === "vencido" || s.subscription_state === "suspendido";
  const cuidado = s.subscription_state === "por_vencer" || s.subscription_state === "sin_plan";
  const sinAutorizar = s.social_consent.granted !== true;
  return (
    <button type="button" onClick={onAbrir} className="glass"
            style={{ ...BTN_GRANDE, width: "100%", textAlign: "left", padding: "12px 14px", borderRadius: 12, cursor: "pointer", border: "1px solid var(--stroke)", display: "grid", gap: 6, color: "inherit" }}>
      <span style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <b style={{ fontSize: 15 }}>{s.nombre}</b>
        <span style={{ fontSize: 13, color: "var(--txt-2)" }}>{s.plan_nombre ?? "Sin plan"}{s.plan_cortesia ? " (cortesía)" : ""}</span>
        <Insignia tono={mal ? "error" : cuidado ? "aviso" : "ok"} icono={mal || cuidado ? "aviso" : "listo"}>
          {etiquetaDe(SUBSCRIPTION_STATE_LABEL, s.subscription_state)}{s.paga_hasta ? ` · ${fechaCorta(s.paga_hasta)}` : ""}
        </Insignia>
      </span>
      <span style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", fontSize: 12.5, color: "var(--txt-2)" }}>
        <span>Piezas {s.pieces.used}/{s.pieces.quota}</span>
        {sinAutorizar
          ? <Insignia tono="error" icono="aviso">Redes: SIN AUTORIZAR</Insignia>
          : <Insignia tono="ok" icono="listo">Redes: autorizado</Insignia>}
        {s.tasks.overdue > 0 && <Insignia tono="error" icono="aviso">{s.tasks.overdue} atrasadas</Insignia>}
        {s.tasks.due_today > 0 && <Insignia tono="aviso" icono="calendario">{s.tasks.due_today} hoy</Insignia>}
        <span style={{ marginLeft: "auto" }}><Ic n="seguir" s={16} /></span>
      </span>
    </button>
  );
}
