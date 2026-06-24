"use client";

import { useState } from "react";
import { dejarMensaje } from "@/lib/comercio";

export function MensajeComercioForm({ comercioId, nombre }: { comercioId: string; nombre: string }) {
  const [n, setN] = useState("");
  const [contacto, setContacto] = useState("");
  const [cuerpo, setCuerpo] = useState("");
  const [estado, setEstado] = useState<"idle" | "sending" | "ok">("idle");
  const [err, setErr] = useState("");

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    if (!n.trim() || !cuerpo.trim()) { setErr("Completá tu nombre y el mensaje"); return; }
    setEstado("sending"); setErr("");
    try {
      await dejarMensaje({
        comercio_id: comercioId, nombre: n.trim(), cuerpo: cuerpo.trim(),
        contacto: contacto.trim() || undefined,
      });
      setEstado("ok");
    } catch (ex) { setErr(ex instanceof Error ? ex.message : "Error"); setEstado("idle"); }
  }

  if (estado === "ok") return (
    <div className="info-card glass">
      <h3>Mensaje enviado ✓</h3>
      <p style={{ color: "var(--txt-2)", fontSize: 14 }}>{nombre} lo va a ver y te contacta. ¡Gracias!</p>
    </div>
  );

  return (
    <form onSubmit={enviar} className="info-card glass" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <h3>Dejá un mensaje</h3>
      <p style={{ color: "var(--txt-3)", fontSize: 13, marginTop: -6 }}>¿No tenés su WhatsApp a mano? Escribile y te contacta.</p>
      <input className="adm-input" value={n} onChange={(e) => setN(e.target.value)} placeholder="Tu nombre" />
      <input className="adm-input" value={contacto} onChange={(e) => setContacto(e.target.value)} placeholder="Tu WhatsApp o email (para que te responda)" />
      <textarea className="adm-input" rows={3} value={cuerpo} onChange={(e) => setCuerpo(e.target.value)} placeholder="Tu consulta…" />
      {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
      <button className="btn btn-primary" type="submit" disabled={estado === "sending"}>
        {estado === "sending" ? "Enviando…" : "Enviar mensaje"}
      </button>
    </form>
  );
}
