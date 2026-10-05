"use client";

import { useEffect, useState } from "react";
import {
  getPreguntasDelAsistente, getRespuestasDelChatbot, crearRespuestaDelChatbot,
  editarRespuestaDelChatbot, borrarRespuestaDelChatbot, type RespuestaDelLocal, type PreguntaDelAsistente,
} from "@/lib/comercio";
import { getFuncionesDePlan } from "@/lib/data";
import { Ic } from "@/components/ic";

/**
 * El chatbot del local, visto desde «Mi comercio» (pestaña Mensajes).
 *
 * Tiene dos mitades que se alimentan entre sí:
 *  1. Lo que los clientes preguntaron y el chatbot NO supo contestar. El
 *     dueño contesta una vez desde acá y desde ese momento el chatbot lo
 *     contesta solo.
 *  2. «Respuestas de tu chatbot»: las preguntas frecuentes del local, que el
 *     dueño también puede cargar de antemano, editar o borrar.
 *
 * Si el plan no trae el chatbot, la sección no ofrece nada que el servidor
 * rechazaría: explica de qué se trata, sin precios.
 */

const CARD: React.CSSProperties = { marginBottom: 18, padding: 14, border: "1px solid var(--stroke)", borderRadius: 12 };
const AYUDA: React.CSSProperties = { margin: "0 0 10px", fontSize: 13, color: "var(--txt-3)" };

/** Lo mismo que hace el chat público: «Failed to fetch» es el navegador
 *  diciendo que no hay señal, y eso no se le muestra a nadie tal cual. Los
 *  mensajes que escribimos nosotros (sesión vencida, validaciones) sí. */
function mensajeDeError(e: unknown): string {
  const crudo = e instanceof Error ? e.message : "";
  const sinRed = (typeof navigator !== "undefined" && !navigator.onLine) || /failed to fetch|load failed|networkerror/i.test(crudo);
  return sinRed ? "Sin conexión. Revisá tu internet y probá de nuevo." : (crudo || "No se pudo completar. Probá de nuevo.");
}

type Carga<T> = { estado: "cargando" } | { estado: "ok"; data: T } | { estado: "error"; msg: string };

/** Carga una lista y permite recargarla sin parpadeo: si ya había datos, se
 *  quedan en pantalla mientras llegan los nuevos. `pedir` tiene que ser una
 *  función de módulo (estable). */
function useCarga<T>(pedir: () => Promise<T>): [Carga<T>, () => void] {
  const [carga, setCarga] = useState<Carga<T>>({ estado: "cargando" });
  const [vuelta, setVuelta] = useState(0);
  useEffect(() => {
    let vivo = true;
    pedir()
      .then((data) => { if (vivo) setCarga({ estado: "ok", data }); })
      .catch((e) => { if (vivo) setCarga({ estado: "error", msg: mensajeDeError(e) }); });
    return () => { vivo = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vuelta]);
  return [carga, () => setVuelta((v) => v + 1)];
}

function ErrorConReintento({ msg, onReintentar }: { msg: string; onReintentar: () => void }) {
  return (
    <div role="alert" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", fontSize: 13.5, color: "var(--pink)" }}>
      <span><Ic n="aviso" s={15} /> {msg}</span>
      <button type="button" className="btn btn-sm" onClick={onReintentar} style={{ border: "1px solid var(--stroke)" }}>Reintentar</button>
    </div>
  );
}

/** El formulario de una respuesta. Con `preguntaFija` (contestar una pregunta
 *  que ya hizo un cliente) sólo se escribe la respuesta; sin ella (agregar o
 *  editar) también se escribe la pregunta. */
function FormRespuesta({ pregunta: p0 = "", respuesta: r0 = "", preguntaFija, ayuda, etiquetaGuardar, onGuardar, onCancelar }: {
  pregunta?: string; respuesta?: string; preguntaFija?: string; ayuda?: string; etiquetaGuardar: string;
  onGuardar: (pregunta: string, respuesta: string) => Promise<void>; onCancelar: () => void;
}) {
  const [pregunta, setPregunta] = useState(p0);
  const [respuesta, setRespuesta] = useState(r0);
  const [guardando, setGuardando] = useState(false);
  const [err, setErr] = useState("");

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    const p = (preguntaFija ?? pregunta).trim();
    const r = respuesta.trim();
    if (!p || !r) { setErr(preguntaFija ? "Escribí la respuesta." : "Completá la pregunta y la respuesta."); return; }
    setErr(""); setGuardando(true);
    try { await onGuardar(p, r); }
    catch (x) { setErr(mensajeDeError(x)); setGuardando(false); }
    // Si salió bien, quien llama cierra el formulario: no hay nada más que soltar.
  }

  return (
    <form onSubmit={enviar} style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
      {preguntaFija === undefined && (
        <input className="adm-input" value={pregunta} onChange={(e) => setPregunta(e.target.value)} maxLength={300}
               placeholder="Pregunta, por ejemplo: ¿Hacen envíos?" aria-label="Pregunta" />
      )}
      <textarea className="adm-input" rows={3} value={respuesta} onChange={(e) => setRespuesta(e.target.value)} maxLength={2000}
                placeholder="Tu respuesta, como se la dirías a un cliente" aria-label="Respuesta" style={{ resize: "vertical" }} />
      {ayuda && <small style={{ color: "var(--txt-3)" }}>{ayuda}</small>}
      {err && <span role="alert" style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={14} /> {err}</span>}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" className="btn btn-primary btn-sm" disabled={guardando}>{guardando ? "Guardando…" : etiquetaGuardar}</button>
        <button type="button" className="btn btn-sm" onClick={onCancelar} disabled={guardando} style={{ border: "1px solid var(--stroke)" }}>Cancelar</button>
      </div>
    </form>
  );
}

/* ------------------------- 1. Lo que no supo contestar ------------------------ */
function PreguntasDelChatbot({ onRespondida }: { onRespondida: () => void }) {
  const [carga, recargar] = useCarga(getPreguntasDelAsistente);
  const [abierta, setAbierta] = useState<string | null>(null);

  if (carga.estado === "cargando") return <div style={CARD}><span style={{ color: "var(--txt-3)", fontSize: 14 }}>Cargando las preguntas…</span></div>;
  if (carga.estado === "error") return <div style={CARD}><ErrorConReintento msg={carga.msg} onReintentar={recargar} /></div>;

  const { items } = carga.data;
  // Pendiente = el chatbot no supo Y el dueño todavía no la contestó. Una
  // pregunta contestada conserva `sin_respuesta` (así quedó registrada) pero
  // trae `resuelta_en`: ya no se le pide nada al dueño.
  const esPendiente = (i: PreguntaDelAsistente) => i.sin_respuesta && !i.resuelta_en;
  // El contador es el del servidor (ya descuenta las resueltas); si por algún
  // motivo no viniera, se cuenta acá.
  const nPendientes = typeof carga.data.sin_respuesta === "number" ? carga.data.sin_respuesta : items.filter(esPendiente).length;
  // Las pendientes primero, después las ya respondidas.
  const lista = [...items.filter(esPendiente), ...items.filter((i) => !esPendiente(i))].slice(0, 15);

  return (
    <div style={CARD}>
      <b style={{ display: "block", marginBottom: 4 }}>Preguntas al chatbot de tu local</b>
      {items.length === 0 ? (
        <p style={{ ...AYUDA, margin: 0 }}>Todavía nadie le preguntó nada a tu chatbot. Cuando pase, lo que no sepa contestar aparece acá para que lo respondas.</p>
      ) : (
        <>
          <p style={AYUDA}>
            {items.length} en total · {nPendientes} sin responder. Respondé una vez y desde ahora el chatbot lo contesta solo.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 13.5 }}>
            {lista.map((i) => (
              <div key={i.id}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
                  <span><Ic n={esPendiente(i) ? "ayuda" : "si"} s={14} /> {i.pregunta}</span>
                  <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ color: "var(--txt-3)", whiteSpace: "nowrap", fontSize: 12 }}>{new Date(i.created_at).toLocaleDateString("es-BO")}</span>
                    {esPendiente(i) && abierta !== i.id && (
                      <button type="button" className="btn btn-sm" onClick={() => setAbierta(i.id)}
                              style={{ border: "1px solid var(--neon)", color: "var(--neon)" }}>
                        <Ic n="editar" s={14} /> Responder
                      </button>
                    )}
                  </span>
                </div>
                {esPendiente(i) && abierta === i.id && (
                  <FormRespuesta preguntaFija={i.pregunta} etiquetaGuardar="Guardar respuesta"
                                 ayuda="Desde ahora el chatbot contesta esto solo."
                                 onGuardar={async (p, r) => {
                                   await crearRespuestaDelChatbot({ pregunta: p, respuesta: r, conversacion_id: i.id });
                                   // El servidor ya marcó la pregunta como resuelta (por el
                                   // conversacion_id): se refresca esta lista, y la de
                                   // respuestas, que ahora tiene una más.
                                   setAbierta(null); recargar(); onRespondida();
                                 }}
                                 onCancelar={() => setAbierta(null)} />
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/* --------------------------- 2. Respuestas de tu chatbot --------------------------- */
function RespuestasDelChatbot({ version }: { version: number }) {
  const [carga, recargar] = useCarga(getRespuestasDelChatbot);
  const [agregando, setAgregando] = useState(false);
  const [editando, setEditando] = useState<string | null>(null);
  const [errAccion, setErrAccion] = useState("");

  // Una pregunta contestada desde la otra mitad crea una respuesta nueva: hay
  // que volver a pedir la lista. `version` cambia cada vez que eso pasa.
  useEffect(() => { if (version > 0) recargar(); }, [version]); // eslint-disable-line react-hooks/exhaustive-deps

  async function borrar(r: RespuestaDelLocal) {
    // Borrar corta una respuesta que el chatbot daba sola: se pide confirmación.
    if (!window.confirm(`¿Borrar la respuesta a «${r.pregunta}»? El chatbot deja de contestarla.`)) return;
    setErrAccion("");
    try { await borrarRespuestaDelChatbot(r.id); recargar(); }
    catch (e) { setErrAccion(mensajeDeError(e)); }
  }

  return (
    <div style={CARD}>
      <b style={{ display: "block", marginBottom: 4 }}>Respuestas de tu chatbot</b>
      <p style={AYUDA}>
        Son las preguntas frecuentes de tu local que el chatbot contesta solo, por ejemplo «¿hacen envíos?» o «¿aceptan pesos?».
        Cargalas una vez y no tenés que repetirlas.
      </p>

      {carga.estado === "cargando" && <span style={{ color: "var(--txt-3)", fontSize: 14 }}>Cargando tus respuestas…</span>}
      {carga.estado === "error" && <ErrorConReintento msg={carga.msg} onReintentar={recargar} />}

      {carga.estado === "ok" && (
        <>
          {carga.data.items.length === 0 && !agregando && (
            <p style={{ ...AYUDA, margin: "0 0 10px" }}>Todavía no cargaste ninguna respuesta.</p>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {carga.data.items.map((r) => (
              <div key={r.id} style={{ border: "1px solid var(--stroke)", borderRadius: 10, padding: 10, fontSize: 13.5 }}>
                {editando === r.id ? (
                  <FormRespuesta pregunta={r.pregunta} respuesta={r.respuesta} etiquetaGuardar="Guardar cambios"
                                 onGuardar={async (p, resp) => {
                                   await editarRespuestaDelChatbot(r.id, { pregunta: p, respuesta: resp });
                                   setEditando(null); recargar();
                                 }}
                                 onCancelar={() => setEditando(null)} />
                ) : (
                  <>
                    <b style={{ display: "block" }}>{r.pregunta}</b>
                    <p style={{ margin: "4px 0 8px", color: "var(--txt-2)", whiteSpace: "pre-wrap" }}>{r.respuesta}</p>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button type="button" className="btn btn-sm" onClick={() => { setEditando(r.id); setAgregando(false); }}
                              style={{ border: "1px solid var(--stroke)" }}>
                        <Ic n="editar" s={14} /> Editar
                      </button>
                      <button type="button" className="btn btn-sm" onClick={() => borrar(r)}
                              style={{ border: "1px solid var(--pink)", color: "var(--pink)" }}>
                        <Ic n="cerrar" s={14} /> Borrar
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>

          {errAccion && <p role="alert" style={{ color: "var(--pink)", fontSize: 13, margin: "10px 0 0" }}><Ic n="aviso" s={14} /> {errAccion}</p>}

          {agregando ? (
            <FormRespuesta etiquetaGuardar="Agregar respuesta"
                           onGuardar={async (p, r) => {
                             await crearRespuestaDelChatbot({ pregunta: p, respuesta: r });
                             setAgregando(false); recargar();
                           }}
                           onCancelar={() => setAgregando(false)} />
          ) : (
            <button type="button" className="btn btn-sm" onClick={() => { setAgregando(true); setEditando(null); }}
                    style={{ border: "1px solid var(--neon)", color: "var(--neon)", marginTop: 12 }}>
              <Ic n="mas" s={14} /> Agregar una respuesta
            </button>
          )}
        </>
      )}
    </div>
  );
}

/* ------------------------------------ Entrada ------------------------------------ */
/** Lo que depende del plan: «Respuestas de tu chatbot» (si el plan trae el
 *  chatbot) o la tarjeta que explica que viene con Destacado (si no). */
function SeccionSegunPlan({ plan, errorPlan, onReintentarPlan, version }: {
  plan: string | undefined; errorPlan: string; onReintentarPlan: () => void; version: number;
}) {
  const [funciones, setFunciones] = useState<Record<string, boolean> | null | undefined>(undefined);
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    if (!plan) return;
    let vivo = true;
    setFunciones(undefined);
    getFuncionesDePlan(plan).then((f) => { if (vivo) setFunciones(f); });
    return () => { vivo = false; };
  }, [plan, intento]);

  // No se pudo leer la suscripción: no se afirma que no tiene el chatbot, se
  // dice que no se vio. Las preguntas de arriba no dependen de esto.
  if (!plan) {
    if (errorPlan) {
      return (
        <div style={CARD}>
          <ErrorConReintento msg={`No pudimos ver tu plan: ${errorPlan}`} onReintentar={onReintentarPlan} />
        </div>
      );
    }
    return <p style={{ color: "var(--txt-3)", fontSize: 14 }}>Cargando tu chatbot…</p>;
  }
  if (funciones === undefined) return <p style={{ color: "var(--txt-3)", fontSize: 14 }}>Cargando tu chatbot…</p>;

  if (funciones === null) {
    return (
      <div style={CARD}>
        <ErrorConReintento msg="No pudimos ver qué incluye tu plan. Probá de nuevo." onReintentar={() => setIntento((n) => n + 1)} />
      </div>
    );
  }

  if (funciones.asistente_24_7 !== true) {
    return (
      <div style={CARD}>
        <b style={{ display: "block", marginBottom: 4 }}><Ic n="dax" s={16} /> Chatbot para tu ficha</b>
        <p style={{ ...AYUDA, margin: 0 }}>
          El chatbot viene con el plan Destacado. Contesta las preguntas de tus clientes en tu ficha a cualquier hora y,
          cuando no sabe algo, los manda a tu WhatsApp. Podés cambiar de plan desde Suscripción.
        </p>
      </div>
    );
  }

  return <RespuestasDelChatbot version={version} />;
}

/** `plan` es el slug del plan del comercio (el de la suscripción); `errorPlan`
 *  trae el motivo si la suscripción no se pudo leer. La lista de preguntas se
 *  muestra siempre, con o sin plan. */
export function ChatbotDelLocal({ plan, errorPlan = "", onReintentarPlan }: {
  plan: string | undefined; errorPlan?: string; onReintentarPlan: () => void;
}) {
  const [version, setVersion] = useState(0);
  return (
    <>
      <PreguntasDelChatbot onRespondida={() => setVersion((v) => v + 1)} />
      <SeccionSegunPlan plan={plan} errorPlan={errorPlan} onReintentarPlan={onReintentarPlan} version={version} />
    </>
  );
}
