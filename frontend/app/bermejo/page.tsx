"use client";

import { useEffect, useState } from "react";
import { agenteLogin, getAgenteToken, clearAgente, altaComercioCampo } from "@/lib/campo";
import { RUBROS } from "@/lib/types";
import { Pin, WhatsApp, User } from "@/components/icons";

const MODALIDADES = [
  { key: "mayorista", label: "Mayorista" },
  { key: "minorista", label: "Minorista" },
  { key: "ambos", label: "Ambos" },
];

export default function CampoPage() {
  const [authed, setAuthed] = useState(false);
  useEffect(() => setAuthed(Boolean(getAgenteToken())), []);
  if (!authed) return <Login onOk={() => setAuthed(true)} />;
  return <FormCampo onLogout={() => { clearAgente(); setAuthed(false); }} />;
}

function Login({ onOk }: { onOk: () => void }) {
  const [email, setEmail] = useState("agente@bermejolive.com");
  const [pass, setPass] = useState("");
  const [err, setErr] = useState("");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try { await agenteLogin(email, pass); onOk(); }
    catch { setErr("Credenciales incorrectas. ¿Backend corriendo?"); }
  }
  return (
    <div className="campo-wrap">
      <span className="eyebrow"><User style={{ width: 14, height: 14 }} /> Agente de campo</span>
      <h1 style={{ fontSize: 26, margin: "8px 0 4px" }}>Recorrido Bermejo</h1>
      <p style={{ color: "var(--txt-3)", marginBottom: 20, fontSize: 14 }}>Ingresá para cargar comercios en la calle.</p>
      <form onSubmit={submit} className="glass" style={{ padding: 20, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 }}>
        <input className="adm-input" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
        <input className="adm-input" type="password" value={pass} onChange={(e) => setPass(e.target.value)} placeholder="Contraseña" />
        {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
        <button className="btn btn-primary" type="submit">Entrar</button>
        <small style={{ color: "var(--txt-3)" }}>Demo: agente@bermejolive.com / campo1234</small>
      </form>
    </div>
  );
}

const EMPTY = { nombre: "", whatsapp: "", rubro_slug: "importadora", modalidad: "mayorista", direccion: "", descripcion: "" };

function FormCampo({ onLogout }: { onLogout: () => void }) {
  const [f, setF] = useState({ ...EMPTY });
  const set = (k: keyof typeof EMPTY, v: string) => setF((s) => ({ ...s, [k]: v }));
  const [coords, setCoords] = useState<{ lat: number; lng: number; acc: number } | null>(null);
  const [geoMsg, setGeoMsg] = useState("");
  const [foto, setFoto] = useState<File | null>(null);
  const [preview, setPreview] = useState<string>("");
  const [consent, setConsent] = useState(true);
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [count, setCount] = useState(0);
  const [err, setErr] = useState("");

  function ubicar() {
    setGeoMsg("Obteniendo ubicación…");
    if (!navigator.geolocation) { setGeoMsg("Este dispositivo no tiene GPS disponible."); return; }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude, acc: Math.round(pos.coords.accuracy) });
        setGeoMsg("");
      },
      (e) => setGeoMsg(e.code === 1 ? "Permiso denegado. Activá la ubicación." : "No se pudo obtener la ubicación (¿estás en HTTPS?)."),
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  function onFoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setFoto(file);
    setPreview(file ? URL.createObjectURL(file) : "");
  }

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    if (!f.nombre.trim() || !f.whatsapp.trim()) { setErr("Faltan nombre y celular."); return; }
    setSaving(true);
    const fd = new FormData();
    fd.append("nombre", f.nombre);
    fd.append("whatsapp", f.whatsapp);
    fd.append("rubro_slug", f.rubro_slug);
    fd.append("modalidad", f.modalidad);
    if (f.direccion) fd.append("direccion", f.direccion);
    if (f.descripcion) fd.append("descripcion", f.descripcion);
    if (coords) { fd.append("lat", String(coords.lat)); fd.append("lng", String(coords.lng)); }
    fd.append("consentimiento", String(consent));
    if (foto) fd.append("foto", foto);
    try {
      const r = await altaComercioCampo(fd);
      setDone(r.comercio.nombre);
      setCount((c) => c + 1);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Error al guardar");
    } finally {
      setSaving(false);
    }
  }

  function otro() {
    setF({ ...EMPTY }); setCoords(null); setGeoMsg(""); setFoto(null); setPreview(""); setConsent(true); setDone(null); setErr("");
  }

  if (done) {
    return (
      <div className="campo-wrap" style={{ textAlign: "center", paddingTop: 60 }}>
        <div style={{ fontSize: 48 }}>✅</div>
        <h1 style={{ fontSize: 24, margin: "10px 0 4px" }}>¡{done} cargado!</h1>
        <p style={{ color: "var(--txt-3)", marginBottom: 22 }}>Entró pendiente de verificar. Llevás {count} en este recorrido.</p>
        <button className="btn btn-primary" style={{ width: "100%" }} onClick={otro}>Cargar otro comercio</button>
      </div>
    );
  }

  return (
    <div className="campo-wrap">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div>
          <span className="eyebrow"><Pin style={{ width: 13, height: 13 }} /> Cargar comercio</span>
          {count > 0 && <div style={{ fontSize: 12, color: "var(--neon)" }}>{count} cargados hoy</div>}
        </div>
        <button className="link-more" onClick={onLogout} style={{ padding: "6px 12px" }}>Salir</button>
      </div>

      <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <input className="adm-input" value={f.nombre} onChange={(e) => set("nombre", e.target.value)} placeholder="Nombre del local *" />
        <input className="adm-input" type="tel" inputMode="tel" value={f.whatsapp} onChange={(e) => set("whatsapp", e.target.value)} placeholder="Celular con código país * (ej 5917…)" />

        <div>
          <label className="campo-lbl">Rubro</label>
          <select className="adm-input" value={f.rubro_slug} onChange={(e) => set("rubro_slug", e.target.value)}>
            {RUBROS.map((r) => (<option key={r.slug} value={r.slug}>{r.nombre}</option>))}
          </select>
        </div>

        <div>
          <label className="campo-lbl">¿Vende por mayor o menor?</label>
          <div className="seg">
            {MODALIDADES.map((m) => (
              <button type="button" key={m.key} className={f.modalidad === m.key ? "active" : ""} onClick={() => set("modalidad", m.key)}>{m.label}</button>
            ))}
          </div>
        </div>

        {/* Ubicación */}
        <div>
          <label className="campo-lbl">Ubicación (parado en la puerta)</label>
          <button type="button" className={`btn ${coords ? "btn-ghost" : "btn-primary"}`} style={{ width: "100%" }} onClick={ubicar}>
            <Pin style={{ width: 17, height: 17 }} /> {coords ? "Ubicación tomada ✓ — tomar de nuevo" : "Usar mi ubicación actual"}
          </button>
          {coords && <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}>📍 {coords.lat.toFixed(5)}, {coords.lng.toFixed(5)} (±{coords.acc} m)</div>}
          {geoMsg && <div style={{ fontSize: 12.5, color: "var(--amber)", marginTop: 6 }}>{geoMsg}</div>}
        </div>

        {/* Foto */}
        <div>
          <label className="campo-lbl">Foto del local</label>
          <label className="foto-drop">
            {preview ? <img src={preview} alt="" /> : <span>📷 Sacar foto / elegir</span>}
            <input type="file" accept="image/*" capture="environment" onChange={onFoto} hidden />
          </label>
        </div>

        <input className="adm-input" value={f.direccion} onChange={(e) => set("direccion", e.target.value)} placeholder="Dirección (opcional): Galería X, Local Y" />

        <label style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 13.5, color: "var(--txt-2)" }}>
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          El dueño aceptó aparecer en Bermejo Live Market
        </label>

        {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
        <button className="btn btn-primary" type="submit" disabled={saving} style={{ width: "100%", padding: 16 }}>
          {saving ? "Guardando…" : "Guardar comercio"}
        </button>
      </form>
      <div style={{ height: 40 }} />
    </div>
  );
}
