"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { crearReclamo } from "@/lib/campo";

export default function ReclamosPage() {
  // Lee ?comercio_id=&nombre_comercio= sin useSearchParams (evita exigir Suspense)
  const [comercioId, setComercioId] = useState<string | undefined>();
  const [nombreComercio, setNombreComercio] = useState<string | null>(null);
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    setComercioId(p.get("comercio_id") ?? undefined);
    setNombreComercio(p.get("nombre_comercio"));
  }, []);

  const [nombre, setNombre] = useState("");
  const [contacto, setContacto] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [estado, setEstado] = useState<"idle" | "sending" | "ok">("idle");
  const [err, setErr] = useState("");

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    if (!mensaje.trim()) { setErr("Contanos qué pasó"); return; }
    setEstado("sending"); setErr("");
    try {
      await crearReclamo({
        nombre: nombre.trim() || undefined,
        contacto: contacto.trim() || undefined,
        comercio_id: comercioId,
        mensaje: mensaje.trim(),
      });
      setEstado("ok");
    } catch {
      setErr("No se pudo enviar. Intentá de nuevo.");
      setEstado("idle");
    }
  }

  return (
    <div className="wrap" style={{ maxWidth: 480, paddingTop: 60, paddingBottom: 60 }}>
      <Link className="brand" href="/" style={{ marginBottom: 24, display: "inline-flex" }}>
        <b style={{ fontSize: 22 }}>Encontralo</b>
      </Link>

      {estado === "ok" ? (
        <div className="glass" style={{ padding: 24, borderRadius: 16 }}>
          <h1 style={{ fontSize: 22, marginBottom: 8 }}>Comentario enviado ✓</h1>
          <p style={{ color: "var(--txt-2)" }}>Lo va a revisar el equipo de Encontralo. Si dejaste tu contacto, te respondemos a la brevedad.</p>
        </div>
      ) : (
        <>
          <h1 style={{ fontSize: 26, marginBottom: 6 }}>Dejar un comentario</h1>
          <p style={{ color: "var(--txt-3)", marginBottom: 24 }}>
            {nombreComercio
              ? <>Sobre <b style={{ color: "var(--txt)" }}>{nombreComercio}</b>. Contanos qué pasó o qué te gustaría comentar — lo lee el equipo de Encontralo.</>
              : "Contanos qué pasó, ya sea con un negocio o con la plataforma. Lo lee el equipo de Encontralo."}
          </p>
          <form onSubmit={enviar} className="glass" style={{ padding: 22, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 }}>
            <input className="adm-input" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Tu nombre (opcional)" />
            <input className="adm-input" value={contacto} onChange={(e) => setContacto(e.target.value)} placeholder="Tu WhatsApp o email (para responderte)" />
            <textarea className="adm-input" rows={5} value={mensaje} onChange={(e) => setMensaje(e.target.value)} placeholder="Contanos qué pasó o dejá tu comentario…" />
            {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
            <button className="btn btn-primary" type="submit" disabled={estado === "sending"}>
              {estado === "sending" ? "Enviando…" : "Enviar comentario"}
            </button>
          </form>
        </>
      )}
    </div>
  );
}
