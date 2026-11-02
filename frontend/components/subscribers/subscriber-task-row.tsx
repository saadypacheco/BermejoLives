"use client";

import { useState } from "react";
import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE, EnvioWhatsapp, Insignia } from "@/components/content/content-ui";
import { mensajeContent } from "@/lib/content";
import { fechaCorta, fechaCortaBo, linkWhatsappTarea } from "@/lib/content-pure";
import { cerrarTarea, saltarTarea, type SubscriberTaskResponse } from "@/lib/subscribers";

/**
 * Una tarea de cuidado de un suscriptor (§9.4). Los mensajes los arma el backend
 * (M1..M6) y salen SIEMPRE por WhatsApp de la persona: [Abrir WhatsApp] deja el
 * texto escrito en el chat y, al volver, se pregunta «¿Lo mandaste?». WAHA no
 * manda nada.
 *
 * Las tareas de checklist (revisar la ficha, primera oferta…) se cierran solas
 * cuando se cumple la condición; acá se pueden marcar a mano igual.
 */
export function SubscriberTaskRow({ t, onCambio, mostrarComercio }: {
  t: SubscriberTaskResponse;
  onCambio: (t: SubscriberTaskResponse) => void;
  /** En la lista del día hay tareas de varios comercios: se dice de cuál. */
  mostrarComercio?: boolean;
}) {
  const [outcome, setOutcome] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [err, setErr] = useState("");

  const abierta = t.status === "open";
  const tieneMensaje = !!t.message_text;
  const hayLink = linkWhatsappTarea(t.whatsapp, t.message_text) !== null;
  const sinPasos = !tieneMensaje && !t.needs_outcome && !t.call_script;

  async function cerrar(sent: boolean) {
    if (t.needs_outcome && !outcome.trim()) { setErr("Contá qué te dijo antes de marcarla como hecha"); return; }
    setOcupado(true); setErr("");
    try { onCambio(await cerrarTarea(t.id, sent, outcome.trim() || null)); }
    catch (ex) { setErr(mensajeContent(ex, "No se pudo cerrar la tarea")); }
    finally { setOcupado(false); }
  }

  async function saltar() {
    if (!window.confirm("¿Saltar esta tarea? No se vuelve a mostrar.")) return;
    setOcupado(true); setErr("");
    try { onCambio(await saltarTarea(t.id, null)); }
    catch (ex) { setErr(mensajeContent(ex, "No se pudo saltar la tarea")); }
    finally { setOcupado(false); }
  }

  return (
    <div style={{ display: "grid", gap: 8, padding: "10px 0", borderTop: "1px solid var(--stroke)" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        {abierta && t.overdue && <Insignia tono="error" icono="aviso">ATRASADA · {fechaCorta(t.due_on)}</Insignia>}
        {abierta && !t.overdue && <Insignia tono="info" icono="calendario">{fechaCorta(t.due_on)}</Insignia>}
        {t.status === "done" && <Insignia tono="ok" icono="listo">HECHA{t.done_at ? ` ${fechaCortaBo(t.done_at)}` : ""}</Insignia>}
        {t.status === "skipped" && <Insignia tono="info" icono="cerrar">SALTADA</Insignia>}
        <b style={{ fontSize: 14 }}>
          {t.kind_label}{t.message_template ? ` (${t.message_template})` : ""}
          {mostrarComercio ? <span style={{ fontWeight: 400, color: "var(--txt-3)" }}> · {t.comercio_nombre}</span> : null}
        </b>
      </div>

      {t.status === "done" && (
        <p style={{ margin: 0, fontSize: 12.5, color: "var(--txt-3)" }}>
          {t.auto_closed ? "Se cerró sola: la condición ya se cumplió." : t.done_by ? `La cerró ${t.done_by}.` : ""}
          {t.outcome ? ` Te dijo: «${t.outcome}».` : ""}
        </p>
      )}

      {abierta && (
        <>
          {tieneMensaje && (
            <>
              <p style={{ margin: 0, fontSize: 13, color: "var(--txt-2)", lineHeight: 1.45, whiteSpace: "pre-wrap" }}>{t.message_text}</p>
              <EnvioWhatsapp whatsapp={t.whatsapp} texto={t.message_text as string}
                             onMandado={t.needs_outcome ? undefined : async () => { onCambio(await cerrarTarea(t.id, true, null)); }} />
              {!hayLink && !t.needs_outcome && (
                <div>
                  <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={ocupado} onClick={() => void cerrar(true)}>
                    <Ic n="si" s={15} /> Ya lo mandé por otro lado
                  </button>
                </div>
              )}
            </>
          )}

          {t.call_script && (
            <div style={{ display: "grid", gap: 4 }}>
              <span style={{ fontSize: 13, fontWeight: 700 }}><Ic n="telefono" s={14} /> Llamada. Preguntale:</span>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "var(--txt-2)" }}>
                {t.call_script.map((l, i) => <li key={i}>{l}</li>)}
              </ul>
              {t.whatsapp && <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>Número: {t.whatsapp}</span>}
            </div>
          )}

          {t.needs_outcome && (
            <label style={{ display: "grid", gap: 3, fontSize: 12.5 }}>
              <span style={{ color: "var(--txt-3)" }}>Qué te dijo</span>
              <textarea className="adm-input" rows={2} maxLength={500} value={outcome} onChange={(e) => setOutcome(e.target.value)} />
            </label>
          )}

          {sinPasos && <p style={{ margin: 0, fontSize: 12.5, color: "var(--txt-3)" }}>Se cierra sola cuando se cumple. Si ya lo hiciste, marcala.</p>}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {(t.needs_outcome || sinPasos) && (
              <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} disabled={ocupado} onClick={() => void cerrar(tieneMensaje)}>
                <Ic n="si" s={15} /> {ocupado ? "Guardando…" : "Hecha"}
              </button>
            )}
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={ocupado} onClick={() => void saltar()}>Saltar</button>
          </div>
        </>
      )}

      {err && <Aviso tono="error">{err}</Aviso>}
    </div>
  );
}
