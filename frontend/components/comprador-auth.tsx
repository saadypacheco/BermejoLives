"use client";

import { useEffect, useRef, useState } from "react";
import { solicitarCodigoUsuario, verificarCodigoUsuario } from "@/lib/usuario";

const POLL_MS = 2500;

export function CompradorAuthForm({ onOk, titulo }: { onOk: () => void; titulo?: string }) {
  const [paso, setPaso] = useState<"telefono" | "confirmar">("telefono");
  const [whatsapp, setWhatsapp] = useState("");
  const [codigo, setCodigo] = useState("");
  const [waLink, setWaLink] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [err, setErr] = useState("");
  const intervaloRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (intervaloRef.current) clearInterval(intervaloRef.current); }, []);

  async function pedirCodigo(e: React.FormEvent) {
    e.preventDefault();
    if (!whatsapp.trim()) { setErr("Ingresá tu WhatsApp"); return; }
    setEnviando(true); setErr("");
    try {
      const { codigo: c, wa_link } = await solicitarCodigoUsuario(whatsapp.trim());
      setCodigo(c); setWaLink(wa_link); setPaso("confirmar");
      // arranca a pollear apenas se muestra el botón — no hace falta que el
      // usuario haga nada más que tocar "Confirmar por WhatsApp" y volver
      intervaloRef.current = setInterval(async () => {
        const usuario = await verificarCodigoUsuario(whatsapp.trim(), c);
        if (usuario) {
          if (intervaloRef.current) clearInterval(intervaloRef.current);
          onOk();
        }
      }, POLL_MS);
    } catch { setErr("No se pudo generar el código, probá de nuevo"); }
    finally { setEnviando(false); }
  }

  function usarOtroNumero() {
    if (intervaloRef.current) clearInterval(intervaloRef.current);
    setPaso("telefono"); setErr("");
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <h3 style={{ margin: 0 }}>{titulo ?? "Dejanos tu WhatsApp"}</h3>
      <p style={{ color: "var(--txt-3)", fontSize: 13, margin: 0 }}>
        Sin contraseña: confirmás con tu propio WhatsApp. Lo usamos para guardar tus locales favoritos
        y avisarte de ofertas o comercios nuevos — nada más.
      </p>
      {paso === "telefono" ? (
        <form onSubmit={pedirCodigo} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <input className="adm-input" value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)} placeholder="Tu WhatsApp (ej: 59170000000)" />
          {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
          <button className="btn btn-primary" type="submit" disabled={enviando}>{enviando ? "Generando…" : "Continuar"}</button>
        </form>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <a
            className="btn btn-primary"
            href={waLink}
            target="_blank"
            rel="noopener"
            style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
          >
            Confirmar por WhatsApp
          </a>
          <p style={{ color: "var(--txt-3)", fontSize: 12.5, margin: 0, textAlign: "center" }}>
            Se abre WhatsApp con un mensaje ya escrito — solo tocá enviar y volvé acá.
          </p>
          {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
          <button type="button" onClick={usarOtroNumero} style={{ background: "none", border: "none", color: "var(--txt-3)", fontSize: 13, cursor: "pointer", padding: 0, textAlign: "left" }}>
            ← Usar otro número
          </button>
        </div>
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
