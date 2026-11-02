"use client";

import { useCallback, useEffect, useState } from "react";
import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE, Cargando, ErrorConReintento, Insignia } from "@/components/content/content-ui";
import {
  armarSemana, getSemana, mensajeContent, type ContentPieceSummary, type ContentWeekResponse,
} from "@/lib/content";
import {
  fechaCorta, hoyBolivia, lunesDe, PIECE_STATUS_LABEL, resumenDePlan, sumarDias, etiquetaDe,
} from "@/lib/content-pure";
import type { NombreIcono } from "@/components/ic";
import type { Tono } from "@/components/content/content-ui";

const ESTADO_VISUAL: Record<string, { icono: NombreIcono; tono: Tono }> = {
  queued: { icono: "reloj", tono: "info" },
  rendering: { icono: "reloj", tono: "info" },
  ready_for_review: { icono: "dato", tono: "aviso" },
  approved: { icono: "si", tono: "ok" },
  published: { icono: "listo", tono: "ok" },
  skipped: { icono: "cerrar", tono: "info" },
  failed: { icono: "aviso", tono: "error" },
};

/**
 * Admin › Contenido para redes › Semana (§9.3): qué piezas hay cada día y en qué
 * estado. En la PC son siete columnas; en el celular, una lista por día (la
 * grilla se acomoda sola según el ancho). [Armar la semana] corre el selector a
 * mano, sin esperar al domingo a las 20:00.
 */
export function ContentWeek({ onCambioCola }: { onCambioCola?: () => void }) {
  const [inicio, setInicio] = useState(lunesDe(hoyBolivia()));
  const [data, setData] = useState<ContentWeekResponse | null>(null);
  const [cargando, setCargando] = useState(true);
  const [err, setErr] = useState("");
  const [armando, setArmando] = useState(false);
  const [resultado, setResultado] = useState("");
  const [errPlan, setErrPlan] = useState("");

  const cargar = useCallback(async (lunes: string, silencioso = false) => {
    if (!silencioso) setCargando(true);
    setErr("");
    try { setData(await getSemana(lunes)); }
    catch (ex) { setErr(mensajeContent(ex, "No se pudo cargar la semana")); }
    finally { setCargando(false); }
  }, []);

  useEffect(() => { setResultado(""); setErrPlan(""); void cargar(inicio); }, [inicio, cargar]);

  const pasada = sumarDias(inicio, 6) < hoyBolivia();   // una semana que ya terminó no se arma

  async function armar() {
    setArmando(true); setResultado(""); setErrPlan("");
    try {
      const r = await armarSemana(inicio);
      setResultado(resumenDePlan(r.created, r.slots_left_empty) + (r.tasks_created > 0 ? ` Se crearon ${r.tasks_created} tareas de cuidado.` : ""));
      await cargar(inicio, true);
      onCambioCola?.();
    } catch (ex) { setErrPlan(mensajeContent(ex, "No se pudo armar la semana")); }
    finally { setArmando(false); }
  }

  const q = data?.queue;
  return (
    <div style={{ display: "grid", gap: 14 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} aria-label="Semana anterior" onClick={() => setInicio(sumarDias(inicio, -7))}>
          <Ic n="volver" s={15} />
        </button>
        <b style={{ fontSize: 15 }}>Semana del {fechaCorta(inicio)} al {fechaCorta(sumarDias(inicio, 6))}</b>
        <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} aria-label="Semana siguiente" onClick={() => setInicio(sumarDias(inicio, 7))}>
          <Ic n="seguir" s={15} />
        </button>
        {inicio !== lunesDe(hoyBolivia()) && (
          <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => setInicio(lunesDe(hoyBolivia()))}>Esta semana</button>
        )}
        <button type="button" className="btn btn-primary btn-sm" style={{ ...BTN_GRANDE, marginLeft: "auto" }} onClick={() => void armar()} disabled={armando || pasada}
                title={pasada ? "Esa semana ya pasó" : undefined}>
          <Ic n="destacado" s={15} /> {armando ? "Armando…" : "Armar la semana"}
        </button>
      </div>

      {pasada && <p style={{ margin: 0, fontSize: 13, color: "var(--txt-3)" }}>Esa semana ya pasó: sólo se puede mirar.</p>}
      {resultado && <Aviso tono="ok">{resultado}</Aviso>}
      {errPlan && <Aviso tono="error">{errPlan}</Aviso>}

      {q && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Insignia tono="info" icono="reloj">En cola: {q.queued + q.rendering}</Insignia>
          <Insignia tono={q.ready_for_review > 0 ? "aviso" : "info"} icono="dato">Para revisar: {q.ready_for_review}</Insignia>
          <Insignia tono={q.failed > 0 ? "error" : "info"} icono={q.failed > 0 ? "aviso" : "listo"}>Con problemas: {q.failed}</Insignia>
        </div>
      )}

      {cargando && !data && <Cargando texto="Cargando la semana…" />}
      {err && <ErrorConReintento mensaje={err} onReintentar={() => void cargar(inicio)} />}

      {data && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 150px), 1fr))", gap: 10 }}>
          {data.days.map((d) => (
            <section key={d.date} aria-label={`${d.weekday_label} ${fechaCorta(d.date)}`}
                     className="glass" style={{ padding: 10, borderRadius: 12, border: `1px solid ${d.date === hoyBolivia() ? "var(--neon)" : "var(--stroke)"}`, display: "grid", gap: 8, alignContent: "start" }}>
              <b style={{ fontSize: 13.5 }}>{d.weekday_label} {fechaCorta(d.date)}{d.date === hoyBolivia() ? " · hoy" : ""}</b>
              {d.pieces.length === 0 && <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>Sin piezas</span>}
              {d.pieces.map((p) => <PiezaDelDia key={p.id} p={p} />)}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

function PiezaDelDia({ p }: { p: ContentPieceSummary }) {
  const v = ESTADO_VISUAL[p.status] ?? { icono: "dato" as NombreIcono, tono: "info" as Tono };
  return (
    <div style={{ display: "grid", gap: 4, fontSize: 12.5, lineHeight: 1.35 }}>
      <span style={{ fontWeight: 700 }}>{p.pillar_label}</span>
      <span style={{ color: "var(--txt-2)", overflowWrap: "anywhere" }}>{p.comercio ? p.comercio.nombre : p.ciudad_nombre ?? "Compilado"}</span>
      <span><Insignia tono={v.tono} icono={v.icono}>{p.status_label || etiquetaDe(PIECE_STATUS_LABEL, p.status)}</Insignia></span>
      {p.counts_for_quota && <span style={{ color: "var(--txt-3)" }}>Cuenta para el plan</span>}
      {p.status === "failed" && p.render_error && <span style={{ color: "var(--pink)" }}>{p.render_error}</span>}
    </div>
  );
}
