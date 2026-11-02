"use client";

import { useCallback, useEffect, useState } from "react";
import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE, Cargando, ErrorConReintento, Insignia } from "@/components/content/content-ui";
import { SocialConsentBox } from "@/components/content/social-consent-box";
import { SubscriberTaskRow } from "@/components/subscribers/subscriber-task-row";
import { apiBancoAdmin, mensajeContent, type SocialConsentResponse } from "@/lib/content";
import { etiquetaDe, fechaConDia, fechaCorta, fechaCortaBo, SUBSCRIPTION_STATE_LABEL } from "@/lib/content-pure";
import {
  getSuscriptor, guardarPerfilSuscriptor, iniciarBienvenida, type SubscriberDetailResponse, type SubscriberTaskResponse,
} from "@/lib/subscribers";

/**
 * Detalle de un suscriptor (§9.4): persona de contacto, qué le falta a su ficha,
 * las tareas con su botón de WhatsApp, las piezas del ciclo y el último reporte.
 * Todo lo que sale hacia el comerciante es un mensaje armado que la persona manda
 * desde SU WhatsApp.
 */
export function SubscriberDetail({ comercioId, onVolver, onCambio }: {
  comercioId: string;
  onVolver: () => void;
  /** Algo cambió (una tarea, la autorización): la lista de afuera se actualiza. */
  onCambio: () => void;
}) {
  const [d, setD] = useState<SubscriberDetailResponse | null>(null);
  const [cargando, setCargando] = useState(true);
  const [err, setErr] = useState("");

  const cargar = useCallback(async (silencioso = false) => {
    if (!silencioso) setCargando(true);
    setErr("");
    try { setD(await getSuscriptor(comercioId)); }
    catch (ex) { setErr(mensajeContent(ex, "No se pudo cargar el suscriptor")); }
    finally { setCargando(false); }
  }, [comercioId]);

  useEffect(() => { setD(null); void cargar(); }, [comercioId, cargar]);

  const volver = (
    <div>
      <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={onVolver}>
        <Ic n="volver" s={15} /> Volver a la lista
      </button>
    </div>
  );

  if (cargando && !d) return <div style={{ display: "grid", gap: 12 }}>{volver}<Cargando texto="Cargando el suscriptor…" /></div>;
  if (err && !d) return <div style={{ display: "grid", gap: 12 }}>{volver}<ErrorConReintento mensaje={err} onReintentar={() => void cargar()} /></div>;
  if (!d) return null;

  const s = d.summary;
  const abiertas = d.tasks.filter((t) => t.status === "open");
  const cerradas = d.tasks.filter((t) => t.status !== "open");

  function tareaCambio(t: SubscriberTaskResponse) {
    setD((x) => (x ? { ...x, tasks: x.tasks.map((y) => (y.id === t.id ? t : y)) } : x));
    onCambio();
    void cargar(true);   // una tarea cerrada puede cambiar el checklist y los contadores
  }

  return (
    <div style={{ display: "grid", gap: 14 }}>
      {volver}
      {err && <ErrorConReintento mensaje={err} onReintentar={() => void cargar(true)} />}

      <div className="panel-card glass" style={{ padding: 14, display: "grid", gap: 8 }}>
        <h3 style={{ margin: 0, fontSize: 17 }}>{s.nombre}</h3>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", fontSize: 13, color: "var(--txt-2)" }}>
          <span>{s.plan_nombre ?? "Sin plan"}{s.plan_cortesia ? " (cortesía)" : ""}</span>
          <EstadoSuscripcion estado={s.subscription_state} graciaDias={s.in_grace} />
          {s.paga_hasta && <span>· vence {fechaCorta(s.paga_hasta)}</span>}
          <span>· piezas {s.pieces.used}/{s.pieces.quota}</span>
          {s.pieces.next_scheduled_for && <span>· próxima {fechaConDia(s.pieces.next_scheduled_for)}</span>}
        </div>
      </div>

      <Perfil s={s} onGuardado={() => { onCambio(); void cargar(true); }} />

      <div className="panel-card glass" style={{ padding: 14 }}>
        <SocialConsentBox compacto consent={s.social_consent} api={apiBancoAdmin.consent(comercioId)}
                          onChange={(c: SocialConsentResponse) => { setD((x) => (x ? { ...x, summary: { ...x.summary, social_consent: c } } : x)); onCambio(); void cargar(true); }} />
      </div>

      <ChecklistFicha items={d.profile_check} />

      <div className="panel-card glass" style={{ padding: 14, display: "grid", gap: 4 }}>
        <b style={{ fontSize: 14.5 }}>Tareas</b>
        {abiertas.length === 0 && <p style={{ margin: "6px 0 0", fontSize: 13.5, color: "var(--txt-3)" }}>No hay tareas abiertas.</p>}
        {abiertas.map((t) => <SubscriberTaskRow key={t.id} t={t} onCambio={tareaCambio} />)}
        {cerradas.length > 0 && (
          <details style={{ marginTop: 8 }}>
            <summary style={{ cursor: "pointer", minHeight: 44, display: "flex", alignItems: "center", fontSize: 13.5 }}>Ya cerradas ({cerradas.length})</summary>
            {cerradas.map((t) => <SubscriberTaskRow key={t.id} t={t} onCambio={tareaCambio} />)}
          </details>
        )}
      </div>

      <div className="panel-card glass" style={{ padding: 14, display: "grid", gap: 6 }}>
        <b style={{ fontSize: 14.5 }}>Piezas del ciclo</b>
        {d.pieces.length === 0 && <p style={{ margin: 0, fontSize: 13.5, color: "var(--txt-3)" }}>Todavía no hay piezas.</p>}
        {d.pieces.map((p) => (
          <div key={p.id} style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", fontSize: 13.5 }}>
            <span>{fechaConDia(p.scheduled_for)} · {p.pillar_label}</span>
            <Insignia tono={p.status === "published" ? "ok" : p.status === "failed" ? "error" : "info"}
                      icono={p.status === "published" ? "listo" : p.status === "failed" ? "aviso" : "reloj"}>{p.status_label}</Insignia>
          </div>
        ))}
        {s.pieces.next_scheduled_for && <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>Próxima: {fechaConDia(s.pieces.next_scheduled_for)}</span>}
      </div>

      <div className="panel-card glass" style={{ padding: 14, display: "grid", gap: 4 }}>
        <b style={{ fontSize: 14.5 }}>Último reporte</b>
        {!d.last_report && <p style={{ margin: 0, fontSize: 13.5, color: "var(--txt-3)" }}>Todavía no se armó ninguno.</p>}
        {d.last_report && (
          <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.5 }}>
            {fechaCorta(d.last_report.period_start)} al {fechaCorta(d.last_report.period_end)}: {d.last_report.data.visits} visitas ·{" "}
            {d.last_report.data.whatsapp} WhatsApp · {d.last_report.data.directions} cómo llegar · {d.last_report.data.calls} llamadas
            {d.last_report.data.terms.length > 0 ? ` · «${d.last_report.data.terms.join("», «")}»` : ""}
          </p>
        )}
      </div>
    </div>
  );
}

function EstadoSuscripcion({ estado, graciaDias }: { estado: string; graciaDias: boolean }) {
  const label = etiquetaDe(SUBSCRIPTION_STATE_LABEL, estado);
  const mal = estado === "vencido" || estado === "suspendido";
  const cuidado = estado === "por_vencer" || estado === "sin_plan";
  return (
    <Insignia tono={mal ? "error" : cuidado ? "aviso" : "ok"} icono={mal || cuidado ? "aviso" : "listo"}>
      {label}{graciaDias ? " · en gracia" : ""}
    </Insignia>
  );
}

/** Persona de contacto, notas y el botón de la bienvenida. */
function Perfil({ s, onGuardado }: { s: SubscriberDetailResponse["summary"]; onGuardado: () => void }) {
  const [persona, setPersona] = useState(s.contact_person ?? "");
  // El resumen no trae las notas guardadas: sólo se mandan si la persona las escribió
  // (si no, guardar el nombre podría borrarlas).
  const [notas, setNotas] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [ok, setOk] = useState("");
  const [err, setErr] = useState("");
  const [forzable, setForzable] = useState(false);

  async function guardar() {
    setOcupado(true); setErr(""); setOk("");
    try {
      await guardarPerfilSuscriptor(s.comercio_id, {
        contact_person: persona.trim() || null,
        ...(notas !== null ? { notes: notas.trim() || null } : {}),
      });
      setOk("Guardado"); onGuardado();
    } catch (ex) { setErr(mensajeContent(ex, "No se pudo guardar")); }
    finally { setOcupado(false); }
  }

  async function bienvenida(force: boolean) {
    if (force && !window.confirm("La bienvenida ya arrancó. ¿Iniciarla de nuevo igual? Se crean las tareas otra vez.")) return;
    if (!force && !window.confirm("¿Iniciar la bienvenida? Se crean las tareas de los primeros días (mensaje, fotos, primera pieza).")) return;
    setOcupado(true); setErr(""); setOk(""); setForzable(false);
    try {
      const r = await iniciarBienvenida(s.comercio_id, force);
      setOk(`Bienvenida iniciada: ${r.created === 1 ? "1 tarea" : `${r.created} tareas`}.`);
      onGuardado();
    } catch (ex) {
      const e = ex as { status?: number };
      setErr(mensajeContent(ex, "No se pudo iniciar la bienvenida"));
      if (e.status === 409) setForzable(true);
    } finally { setOcupado(false); }
  }

  return (
    <div className="panel-card glass" style={{ padding: 14, display: "grid", gap: 10 }}>
      <label style={{ display: "grid", gap: 3, fontSize: 12.5 }}>
        <span style={{ color: "var(--txt-3)" }}>Persona de contacto (así se le habla en los mensajes)</span>
        <input className="adm-input" maxLength={80} style={{ minHeight: 48 }} value={persona} onChange={(e) => setPersona(e.target.value)} placeholder={s.nombre} />
      </label>
      <label style={{ display: "grid", gap: 3, fontSize: 12.5 }}>
        <span style={{ color: "var(--txt-3)" }}>Notas nuevas (sólo las ve el equipo; si no escribís nada, las que ya hay quedan como están)</span>
        <textarea className="adm-input" rows={2} maxLength={1000} value={notas ?? ""} onChange={(e) => setNotas(e.target.value)} />
      </label>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} disabled={ocupado} onClick={() => void guardar()}>
          <Ic n="si" s={15} /> {ocupado ? "Guardando…" : "Guardar"}
        </button>
        <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={ocupado}
                onClick={() => void bienvenida(!!s.onboarding_started_at)}>
          <Ic n="enviar" s={15} /> {s.onboarding_started_at ? "Iniciar la bienvenida de nuevo" : "Iniciar bienvenida"}
        </button>
        {s.onboarding_started_at && <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>Arrancó el {fechaCortaBo(s.onboarding_started_at)}</span>}
      </div>
      {ok && <Aviso tono="ok">{ok}</Aviso>}
      {err && (
        <Aviso tono="error" accion={forzable ? (
          <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => void bienvenida(true)}>Iniciarla igual</button>
        ) : undefined}>{err}</Aviso>
      )}
    </div>
  );
}

/** «Ficha lista»: lo automático se tilda solo; lo que el backend no puede leer se
 *  tilda a mano acá (sólo en esta pantalla: el contrato no guarda ese tilde). */
function ChecklistFicha({ items }: { items: SubscriberDetailResponse["profile_check"] }) {
  const [manual, setManual] = useState<Record<string, boolean>>({});
  const listos = items.filter((i) => i.ok || manual[i.key]).length;
  return (
    <div className="panel-card glass" style={{ padding: 14, display: "grid", gap: 6 }}>
      <b style={{ fontSize: 14.5 }}>Ficha lista: {listos}/{items.length}</b>
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 2 }}>
        {items.map((i) => {
          const ok = i.ok || !!manual[i.key];
          return (
            <li key={i.key} style={{ display: "flex", gap: 8, alignItems: "center", minHeight: 36, fontSize: 13.5 }}>
              {!i.ok && !i.auto ? (
                <label style={{ display: "flex", gap: 8, alignItems: "center", minHeight: 44 }}>
                  <input type="checkbox" checked={!!manual[i.key]} onChange={(e) => setManual((m) => ({ ...m, [i.key]: e.target.checked }))} style={{ width: 20, height: 20 }} />
                  <span>{i.label} <span style={{ color: "var(--txt-3)" }}>(se revisa a mano)</span></span>
                </label>
              ) : (
                <>
                  <span style={{ color: ok ? "var(--neon)" : "var(--amber)" }}><Ic n={ok ? "listo" : "aviso"} s={16} /></span>
                  <span>{i.label}</span>
                  <span style={{ color: "var(--txt-3)", fontSize: 12 }}>{ok ? "Listo" : "Falta"}</span>
                </>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
