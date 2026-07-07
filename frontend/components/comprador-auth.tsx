"use client";

import { useState } from "react";
import { solicitarCodigoUsuario, verificarCodigoUsuario } from "@/lib/usuario";

export function CompradorAuthForm({ onOk, titulo }: { onOk: () => void; titulo?: string }) {
  const [paso, setPaso] = useState<"telefono" | "codigo">("telefono");
  const [whatsapp, setWhatsapp] = useState("");
  const [codigo, setCodigo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [err, setErr] = useState("");

  async function enviarCodigo(e: React.FormEvent) {
    e.preventDefault();
    if (!whatsapp.trim()) { setErr("Ingresá tu WhatsApp"); return; }
    setEnviando(true); setErr("");
    try { await solicitarCodigoUsuario(whatsapp.trim()); setPaso("codigo"); }
    catch { setErr("No se pudo enviar el código, probá de nuevo"); }
    finally { setEnviando(false); }
  }

  async function confirmar(e: React.FormEvent) {
    e.preventDefault();
    if (!codigo.trim()) { setErr("Ingresá el código"); return; }
    setEnviando(true); setErr("");
    try { await verificarCodigoUsuario(whatsapp.trim(), codigo.trim()); onOk(); }
    catch (ex) { setErr(ex instanceof Error ? ex.message : "Código incorrecto"); }
    finally { setEnviando(false); }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <h3 style={{ margin: 0 }}>{titulo ?? "Dejanos tu WhatsApp"}</h3>
      <p style={{ color: "var(--txt-3)", fontSize: 13, margin: 0 }}>
        Sin contraseña: te mandamos un código por WhatsApp. Lo usamos para guardar tus locales favoritos
        y avisarte de ofertas o comercios nuevos — nada más.
      </p>
      {paso === "telefono" ? (
        <form onSubmit={enviarCodigo} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <input className="adm-input" value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)} placeholder="Tu WhatsApp (ej: 59170000000)" />
          {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
          <button className="btn btn-primary" type="submit" disabled={enviando}>{enviando ? "Enviando…" : "Enviar código"}</button>
        </form>
      ) : (
        <form onSubmit={confirmar} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <input className="adm-input" value={codigo} onChange={(e) => setCodigo(e.target.value)} placeholder="Código de 6 dígitos" inputMode="numeric" />
          {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
          <button className="btn btn-primary" type="submit" disabled={enviando}>{enviando ? "Verificando…" : "Confirmar"}</button>
          <button type="button" onClick={() => { setPaso("telefono"); setErr(""); }} style={{ background: "none", border: "none", color: "var(--txt-3)", fontSize: 13, cursor: "pointer", padding: 0, textAlign: "left" }}>
            ← Usar otro número
          </button>
        </form>
      )}
    </div>
  );
}

export function CompradorAuthModal({ onClose, onOk, titulo }: { onClose: () => void; onOk: () => void; titulo?: string }) {
  return (
    <div
      style={{ position: "fixed", inset: 0, zIndex: 999, background: "rgba(0,0,0,.6)", display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}
      onClick={onClose}
    >
      <div className="glass" style={{ padding: 22, borderRadius: 16, maxWidth: 380, width: "100%" }} onClick={(e) => e.stopPropagation()}>
        <CompradorAuthForm onOk={onOk} titulo={titulo} />
        <button type="button" onClick={onClose} style={{ marginTop: 14, background: "none", border: "none", color: "var(--txt-3)", fontSize: 13, cursor: "pointer" }}>
          Cancelar
        </button>
      </div>
    </div>
  );
}
