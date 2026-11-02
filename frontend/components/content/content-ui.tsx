"use client";

// Piezas chicas que comparten el Banco de contenido, el Contenido para redes y el
// Cuidado de suscriptores: avisos, insignias de estado, «copiar texto» y el botón
// que abre WhatsApp con el mensaje armado.
//
// Regla de accesibilidad de todo este módulo: un estado nunca se dice SÓLO con
// color. Siempre lleva un ícono y una palabra («Publicada», «Falta»), y los
// botones miden al menos 44 px de alto (se usan con una mano, en la calle).

import { useEffect, useRef, useState } from "react";
import { Ic, type NombreIcono } from "@/components/ic";
import { linkWhatsappTarea } from "@/lib/content-pure";

export type Tono = "ok" | "error" | "aviso" | "info";

const COLOR: Record<Tono, string> = {
  ok: "var(--neon)",
  error: "var(--pink)",
  aviso: "var(--amber)",
  info: "var(--txt-3)",
};
const ICONO: Record<Tono, NombreIcono> = { ok: "listo", error: "aviso", aviso: "aviso", info: "dato" };

/** Alto mínimo de un botón táctil. */
export const BTN_GRANDE: React.CSSProperties = { minHeight: 48 };

/** Una franja con ícono y texto. `role="alert"` para errores y avisos; el resto
 *  es informativo y no interrumpe al lector de pantalla. */
export function Aviso({ tono = "info", children, accion }: { tono?: Tono; children: React.ReactNode; accion?: React.ReactNode }) {
  return (
    <div role={tono === "error" || tono === "aviso" ? "alert" : "status"}
         style={{ display: "flex", gap: 8, alignItems: "flex-start", flexWrap: "wrap", fontSize: 13.5, lineHeight: 1.45,
                  padding: "10px 12px", borderRadius: 10, border: `1px solid ${COLOR[tono]}`, color: "var(--txt)" }}>
      <span style={{ color: COLOR[tono], flex: "none", marginTop: 1 }}><Ic n={ICONO[tono]} s={16} /></span>
      <span style={{ flex: 1, minWidth: 180 }}>{children}</span>
      {accion}
    </div>
  );
}

/** Estado en una píldora: ícono + palabra, con el color de apoyo. */
export function Insignia({ icono, tono = "info", children }: { icono?: NombreIcono; tono?: Tono; children: React.ReactNode }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12, fontWeight: 700, padding: "3px 10px",
                   borderRadius: 999, border: `1px solid ${COLOR[tono]}`, color: COLOR[tono], whiteSpace: "nowrap" }}>
      <Ic n={icono ?? ICONO[tono]} s={13} /> {children}
    </span>
  );
}

/** «Cargando…» con aria-live (los estados de carga son obligatorios en cada vista). */
export function Cargando({ texto = "Cargando…" }: { texto?: string }) {
  return (
    <div role="status" aria-live="polite" style={{ display: "flex", gap: 8, alignItems: "center", color: "var(--txt-3)", fontSize: 14, padding: "12px 2px" }}>
      <Ic n="actualizar" s={15} /> {texto}
    </div>
  );
}

/** Copia al portapapeles. Devuelve false si el navegador no deja (iOS viejo, http). */
export async function copiarTexto(texto: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(texto); return true; }
  } catch { /* se prueba el camino viejo */ }
  try {
    const ta = document.createElement("textarea");
    ta.value = texto;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch { return false; }
}

/** Botón «Copiar texto»: confirma con palabras («Copiado») y, si el navegador no
 *  deja copiar, muestra el texto para copiarlo a mano. */
export function BotonCopiar({ texto, etiqueta = "Copiar texto", className = "btn btn-ghost btn-sm" }: {
  texto: string; etiqueta?: string; className?: string;
}) {
  const [estado, setEstado] = useState<"" | "ok" | "no">("");
  const t = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (t.current) clearTimeout(t.current); }, []);
  async function copiar() {
    const ok = await copiarTexto(texto);
    setEstado(ok ? "ok" : "no");
    if (t.current) clearTimeout(t.current);
    if (ok) t.current = setTimeout(() => setEstado(""), 2500);
  }
  return (
    <>
      <button type="button" className={className} style={BTN_GRANDE} onClick={copiar}>
        <Ic n={estado === "ok" ? "si" : "copiar"} s={15} /> {estado === "ok" ? "Copiado" : etiqueta}
      </button>
      {estado === "no" && (
        <div role="alert" style={{ flexBasis: "100%", fontSize: 12.5, color: "var(--txt-2)" }}>
          No se pudo copiar solo. Mantené apretado el texto para copiarlo:
          <textarea className="adm-input" readOnly rows={4} value={texto} onFocus={(e) => e.currentTarget.select()} style={{ marginTop: 6, width: "100%" }} />
        </div>
      )}
    </>
  );
}

/**
 * Abre WhatsApp con el mensaje armado y, al volver a la pestaña, pregunta «¿Lo
 * mandaste?». NUNCA se envía nada solo: `wa.me` deja el texto escrito y lo manda
 * la persona. Sin número válido no hay link: queda «Copiar texto».
 *
 * `onMandado` se llama con «Sí»; «No» sólo cierra la pregunta (el mensaje sigue
 * disponible para reintentar).
 */
export function EnvioWhatsapp({ whatsapp, texto, etiqueta = "Abrir WhatsApp", onMandado, deshabilitado }: {
  whatsapp: string | null | undefined;
  texto: string;
  etiqueta?: string;
  /** Qué pasa con «Sí, lo mandé». Sin esto no se pregunta (cuando la tarea se
   *  cierra por otro lado, p. ej. contando qué respondió el comerciante). */
  onMandado?: () => Promise<void>;
  deshabilitado?: boolean;
}) {
  const link = linkWhatsappTarea(whatsapp, texto);
  const [abierto, setAbierto] = useState(false);     // ya tocó «Abrir WhatsApp»
  const [pregunta, setPregunta] = useState(false);   // volvió: «¿Lo mandaste?»
  const [guardando, setGuardando] = useState(false);
  const [err, setErr] = useState("");

  // Al volver a la pestaña (después de WhatsApp) se pregunta si lo mandó.
  useEffect(() => {
    if (!abierto || !onMandado) return;
    const alVolver = () => { if (document.visibilityState === "visible") setPregunta(true); };
    document.addEventListener("visibilitychange", alVolver);
    return () => document.removeEventListener("visibilitychange", alVolver);
  }, [abierto]);

  async function si() {
    setGuardando(true); setErr("");
    try { await onMandado?.(); setPregunta(false); setAbierto(false); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo guardar"); }
    finally { setGuardando(false); }
  }

  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
      {link ? (
        <a className="btn btn-wa btn-sm" style={BTN_GRANDE} href={link} target="_blank" rel="noopener noreferrer"
           aria-disabled={deshabilitado} onClick={() => setAbierto(true)}>
          <Ic n="whatsapp" s={16} /> {etiqueta}
        </a>
      ) : (
        <span style={{ fontSize: 12.5, color: "var(--amber)" }}><Ic n="aviso" s={13} /> Sin WhatsApp válido: copiá el texto y mandalo por otro lado.</span>
      )}
      <BotonCopiar texto={texto} />
      {onMandado && pregunta && (
        <div role="group" aria-label="¿Lo mandaste?" style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", flexBasis: "100%" }}>
          <b style={{ fontSize: 13.5 }}>¿Lo mandaste?</b>
          <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} onClick={si} disabled={guardando}>
            <Ic n="si" s={15} /> {guardando ? "Guardando…" : "Sí, lo mandé"}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => setPregunta(false)} disabled={guardando}>
            Todavía no
          </button>
        </div>
      )}
      {err && <span role="alert" style={{ color: "var(--pink)", fontSize: 12.5, flexBasis: "100%" }}><Ic n="aviso" s={13} /> {err}</span>}
    </div>
  );
}

/** El pie de una sección que carga: reintentar si falló. */
export function ErrorConReintento({ mensaje, onReintentar }: { mensaje: string; onReintentar: () => void }) {
  return (
    <Aviso tono="error" accion={<button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={onReintentar}>Reintentar</button>}>
      {mensaje}
    </Aviso>
  );
}

/** ¿El navegador dice que no hay conexión? (se actualiza solo). */
export function useOnline(): boolean {
  const [online, setOnline] = useState(true);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    setOnline(navigator.onLine);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);
  return online;
}

/** El aviso de «sin conexión» que cada pantalla muestra arriba. */
export function SinConexion() {
  const online = useOnline();
  if (online) return null;
  return <Aviso tono="aviso">Sin conexión. Lo que ves puede estar desactualizado y las acciones no se van a guardar hasta que vuelva la señal.</Aviso>;
}
