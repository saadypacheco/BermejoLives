"use client";

import { useState } from "react";
import Link from "next/link";
import { Nav } from "@/components/nav";
import { buscarComercioPorNombre, solicitarCambioNumero, type ComercioBusqueda } from "@/lib/comercio";
import { comprimirImagen } from "@/lib/imagen";

export default function RecuperarNegocioPage() {
  const [comercio, setComercio] = useState<ComercioBusqueda | null>(null);
  const [enviado, setEnviado] = useState(false);

  return (
    <>
      <Nav mapOnly />
      <div className="wrap" style={{ maxWidth: 480, paddingTop: 56, paddingBottom: 60 }}>
        <span className="eyebrow"><span className="dot-live" /> Recuperar negocio</span>
        <h1 style={{ fontSize: 28, margin: "10px 0 6px" }}>¿Cambiaste de número?</h1>
        <p style={{ color: "var(--txt-3)", marginBottom: 20 }}>
          Buscá tu negocio, subí una foto actual del local y tu WhatsApp nuevo. Un admin de Encontralo revisa el pedido — nunca se aprueba solo, para que nadie pueda robarse un negocio ajeno.
        </p>

        {enviado ? (
          <div className="glass" style={{ padding: 22, borderRadius: 16, textAlign: "center" }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>✅</div>
            <h3 style={{ marginBottom: 6 }}>Solicitud enviada</h3>
            <p style={{ color: "var(--txt-3)", fontSize: 14 }}>
              La va a revisar el equipo de Encontralo. Si se aprueba, tu WhatsApp nuevo queda activo y podés entrar con el código de siempre.
            </p>
            <Link className="btn btn-ghost btn-sm" href="/" style={{ marginTop: 14, display: "inline-flex" }}>Volver al inicio</Link>
          </div>
        ) : comercio ? (
          <SolicitudForm comercio={comercio} onEnviado={() => setEnviado(true)} onVolver={() => setComercio(null)} />
        ) : (
          <BuscarNegocio onElegir={setComercio} />
        )}
      </div>
    </>
  );
}

function BuscarNegocio({ onElegir }: { onElegir: (c: ComercioBusqueda) => void }) {
  const [q, setQ] = useState("");
  const [resultados, setResultados] = useState<ComercioBusqueda[]>([]);
  const [buscando, setBuscando] = useState(false);
  const [buscado, setBuscado] = useState(false);

  async function buscar(e: React.FormEvent) {
    e.preventDefault();
    if (q.trim().length < 2) return;
    setBuscando(true);
    try { setResultados(await buscarComercioPorNombre(q.trim())); }
    finally { setBuscando(false); setBuscado(true); }
  }

  return (
    <form onSubmit={buscar} className="glass" style={{ padding: 22, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <input className="adm-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nombre de tu negocio" />
      <button className="btn btn-primary" type="submit" disabled={buscando}>{buscando ? "Buscando…" : "Buscar"}</button>

      {buscado && resultados.length === 0 && (
        <p style={{ color: "var(--txt-3)", fontSize: 13 }}>No encontramos ningún negocio con ese nombre.</p>
      )}
      {resultados.map((c) => (
        <button
          key={c.id} type="button" onClick={() => onElegir(c)}
          style={{ display: "flex", alignItems: "center", gap: 10, textAlign: "left", padding: 10, borderRadius: 10, border: "1px solid var(--stroke)", background: "var(--panel)", cursor: "pointer" }}
        >
          {c.portada_url
            ? <img src={c.portada_url} alt="" style={{ width: 44, height: 44, borderRadius: 8, objectFit: "cover", flexShrink: 0 }} />
            : <div style={{ width: 44, height: 44, borderRadius: 8, background: "var(--stroke)", flexShrink: 0, display: "grid", placeItems: "center" }}>🏪</div>}
          <div>
            <div style={{ fontWeight: 600 }}>{c.nombre}</div>
            {c.direccion && <div style={{ fontSize: 12, color: "var(--txt-3)" }}>{c.direccion}</div>}
          </div>
        </button>
      ))}
    </form>
  );
}

function SolicitudForm({ comercio, onEnviado, onVolver }: { comercio: ComercioBusqueda; onEnviado: () => void; onVolver: () => void }) {
  const [whatsapp, setWhatsapp] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [foto, setFoto] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [comprimiendo, setComprimiendo] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [err, setErr] = useState("");

  async function onFoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    if (!file) { setFoto(null); setPreview(""); return; }
    setPreview(URL.createObjectURL(file));
    setComprimiendo(true);
    const comprimida = await comprimirImagen(file);
    setComprimiendo(false);
    setFoto(comprimida);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    if (!whatsapp.trim()) { setErr("Ingresá tu WhatsApp nuevo"); return; }
    if (!foto) { setErr("Falta una foto actual del local"); return; }
    setEnviando(true);
    try {
      await solicitarCambioNumero(comercio.id, whatsapp.trim(), mensaje.trim() || undefined, foto);
      onEnviado();
    } catch (ex) { setErr(ex instanceof Error ? ex.message : "No se pudo enviar"); }
    finally { setEnviando(false); }
  }

  return (
    <form onSubmit={submit} className="glass" style={{ padding: 22, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {comercio.portada_url && <img src={comercio.portada_url} alt="" style={{ width: 40, height: 40, borderRadius: 8, objectFit: "cover" }} />}
        <b>{comercio.nombre}</b>
      </div>

      <input className="adm-input" value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)} placeholder="Tu WhatsApp nuevo (ej: 59170000000)" />

      <div>
        <label className="campo-lbl">Foto actual del local *</label>
        <label className="foto-drop">
          {preview ? <img src={preview} alt="" /> : <span>📷 Sacar foto / elegir</span>}
          <input type="file" accept="image/*" capture="environment" onChange={onFoto} hidden />
        </label>
        {comprimiendo && <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}>Comprimiendo foto…</div>}
      </div>

      <textarea className="adm-input" rows={2} value={mensaje} onChange={(e) => setMensaje(e.target.value)}
        placeholder="Contanos algo que ayude a confirmar que sos vos (opcional)" style={{ resize: "vertical" }} />

      {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
      <button className="btn btn-primary" type="submit" disabled={enviando || comprimiendo}>
        {enviando ? "Enviando…" : "Enviar solicitud"}
      </button>
      <button type="button" onClick={onVolver} style={{ background: "none", border: "none", color: "var(--txt-3)", fontSize: 13, textAlign: "left", padding: 0, cursor: "pointer" }}>
        ← No es este negocio
      </button>
    </form>
  );
}
