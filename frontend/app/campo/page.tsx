"use client";

import { useEffect, useRef, useState } from "react";
import { agenteLogin, getAgenteToken, clearAgente, altaComercioCampo, transcribirAudio } from "@/lib/campo";
import { getCiudades, getRubros } from "@/lib/data";
import type { Ciudad, Rubro } from "@/lib/types";
import { Pin, User } from "@/components/icons";

// Prefijo telefónico según país
const PREFIJO: Record<string, string> = { Bolivia: "591", Argentina: "54" };

const MODALIDADES = [
  { key: "mayorista", label: "Mayorista" },
  { key: "minorista", label: "Minorista" },
  { key: "ambos",     label: "Ambos" },
];

const MONEDAS = [
  { key: "bolivianos", label: "Bs" },
  { key: "pesos-arg",  label: "$ ARG" },
  { key: "dolares",    label: "USD" },
  { key: "reales",     label: "R$" },
];

const ORIGENES = [
  { key: "china",     label: "China" },
  { key: "brasil",    label: "Brasil" },
  { key: "argentina", label: "Argentina" },
  { key: "chile",     label: "Chile" },
];

// ─────────────────────────────────────────────
export default function CampoPage() {
  const [authed, setAuthed] = useState(false);
  useEffect(() => setAuthed(Boolean(getAgenteToken())), []);
  if (!authed) return <Login onOk={() => setAuthed(true)} />;
  return <FormCampo onLogout={() => { clearAgente(); setAuthed(false); }} />;
}

// ─────────────────────────────────────────────
function Login({ onOk }: { onOk: () => void }) {
  const [email, setEmail] = useState("lobito@lobito.com");
  const [pass, setPass]   = useState("");
  const [err, setErr]     = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try { await agenteLogin(email, pass); onOk(); }
    catch { setErr("Credenciales incorrectas. ¿Backend corriendo?"); }
  }

  return (
    <div className="campo-wrap">
      <span className="eyebrow"><User style={{ width: 14, height: 14 }} /> Agente de campo</span>
      <h1 style={{ fontSize: 26, margin: "8px 0 4px" }}>Carga de negocios</h1>
      <p style={{ color: "var(--txt-3)", marginBottom: 20, fontSize: 14 }}>Ingresá para registrar comercios, hoteles, casas de cambio y más.</p>
      <form onSubmit={submit} className="glass" style={{ padding: 20, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 }}>
        <input className="adm-input" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
        <input className="adm-input" type="password" value={pass} onChange={(e) => setPass(e.target.value)} placeholder="Contraseña" />
        {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
        <button className="btn btn-primary" type="submit">Entrar</button>
      </form>
    </div>
  );
}

// ─────────────────────────────────────────────
const EMPTY = {
  nombre: "", cel: "", modalidad: "mayorista", direccion: "", descripcion: "",
  email: "", facebook_url: "", tiktok_url: "", instagram_url: "", sitio_web: "", video_url: "",
  pedido_minimo: "", horario: "",
};

function toggle<T>(arr: T[], val: T): T[] {
  return arr.includes(val) ? arr.filter((x) => x !== val) : [...arr, val];
}

function ChipToggle({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: "6px 12px", borderRadius: 20, fontSize: 13, border: "1px solid",
        borderColor: active ? "var(--neon)" : "var(--border)",
        background: active ? "rgba(0,255,130,0.12)" : "transparent",
        color: active ? "var(--neon)" : "var(--txt-2)",
        cursor: "pointer",
      }}
    >
      {label}
    </button>
  );
}

function FormCampo({ onLogout }: { onLogout: () => void }) {
  const [ciudades, setCiudades] = useState<Ciudad[]>([]);
  const [rubros,   setRubros]   = useState<Rubro[]>([]);

  const [f, setF]               = useState({ ...EMPTY });
  const set = (k: keyof typeof EMPTY, v: string) => setF((s) => ({ ...s, [k]: v }));

  const [ciudadSlug,  setCiudadSlug]  = useState("bermejo");
  const [prefijo,     setPrefijo]     = useState("591");
  const [rubroSlugs,  setRubroSlugs]  = useState<string[]>([]);
  const [monedas,     setMonedas]     = useState<string[]>([]);
  const [origenes,    setOrigenes]    = useState<string[]>([]);
  const [enviosInt,   setEnviosInt]   = useState(false);
  const [factura,     setFactura]     = useState(false);
  const [tieneStock,  setTieneStock]  = useState(true);

  const [mas,         setMas]         = useState(false);
  const [masFrontera, setMasFrontera] = useState(false);
  const [coords,      setCoords]      = useState<{ lat: number; lng: number; acc: number } | null>(null);
  const [geoMsg,      setGeoMsg]      = useState("");
  const [foto,        setFoto]        = useState<File | null>(null);
  const [preview,     setPreview]     = useState("");
  const [consent,     setConsent]     = useState(true);
  const [saving,      setSaving]      = useState(false);
  const [done,        setDone]        = useState<string | null>(null);
  const [count,       setCount]       = useState(0);
  const [err,         setErr]         = useState("");

  // Audio
  const [grabando,      setGrabando]      = useState(false);
  const [transcribiendo,setTranscribiendo]= useState(false);
  const recRef   = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    getCiudades().then(setCiudades);
    getRubros().then(setRubros);
  }, []);

  // Actualiza el prefijo automáticamente según la ciudad seleccionada
  useEffect(() => {
    const c = ciudades.find((c) => c.slug === ciudadSlug);
    if (c) setPrefijo(PREFIJO[c.pais] ?? "591");
  }, [ciudadSlug, ciudades]);

  async function iniciarGrabacion() {
    setErr("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (e) => e.data.size > 0 && chunksRef.current.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
        setTranscribiendo(true);
        try {
          const texto = await transcribirAudio(blob);
          setF((s) => ({ ...s, descripcion: (s.descripcion ? s.descripcion + " " : "") + texto }));
        } catch (ex) {
          setErr(ex instanceof Error ? ex.message : "No se pudo transcribir — escribí a mano");
        } finally {
          setTranscribiendo(false);
        }
      };
      recRef.current = rec;
      rec.start();
      setGrabando(true);
    } catch {
      setErr("No se pudo acceder al micrófono (¿permiso/HTTPS?). Escribí a mano.");
    }
  }

  function detenerGrabacion() { recRef.current?.stop(); setGrabando(false); }

  function ubicar() {
    setGeoMsg("Obteniendo ubicación…");
    if (!navigator.geolocation) { setGeoMsg("Este dispositivo no tiene GPS disponible."); return; }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude, acc: Math.round(pos.coords.accuracy) });
        setGeoMsg("");
      },
      (e) => setGeoMsg(e.code === 1 ? "Permiso denegado. Activá la ubicación." : "No se pudo obtener la ubicación."),
      { enableHighAccuracy: true, timeout: 10000 },
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
    const cel = f.cel.replace(/\D/g, "");
    if (!f.nombre.trim() || !cel) { setErr("Faltan nombre y celular."); return; }
    if (!f.descripcion.trim()) { setErr("Escribí qué vende / descripción del negocio."); return; }

    setSaving(true);
    const fd = new FormData();
    fd.append("nombre",      f.nombre);
    fd.append("whatsapp",    prefijo + cel);
    fd.append("ciudad_slug", ciudadSlug);
    rubroSlugs.forEach((r) => fd.append("rubro_slugs", r));
    fd.append("modalidad",   f.modalidad);

    // Campos fronterizos
    monedas.forEach((m)  => fd.append("monedas_aceptadas",  m));
    origenes.forEach((o) => fd.append("origen_importacion", o));
    fd.append("envios_internacionales", String(enviosInt));
    fd.append("tiene_factura",          String(factura));
    fd.append("tiene_stock",            String(tieneStock));
    if (f.pedido_minimo.trim()) fd.append("pedido_minimo", f.pedido_minimo.trim());
    if (f.horario.trim())       fd.append("horario",       f.horario.trim());

    for (const k of ["direccion", "descripcion", "email", "facebook_url", "tiktok_url", "instagram_url", "sitio_web", "video_url"] as const) {
      if (f[k].trim()) fd.append(k, f[k].trim());
    }
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
    setF({ ...EMPTY }); setRubroSlugs([]); setMonedas([]); setOrigenes([]);
    setEnviosInt(false); setFactura(false); setTieneStock(true);
    setMas(false); setMasFrontera(false);
    setCoords(null); setGeoMsg(""); setFoto(null); setPreview(""); setConsent(true);
    setDone(null); setErr("");
  }

  // Agrupa ciudades por país para el selector.
  // Si pais es undefined (migration 0011 aún no aplicada en cloud), todo cae a Bolivia.
  const bolivianas = ciudades.filter((c) => !c.pais || c.pais === "Bolivia");
  const argentinas = ciudades.filter((c) => c.pais === "Argentina");

  if (done) {
    const ciudadActual = ciudades.find((c) => c.slug === ciudadSlug);
    return (
      <div className="campo-wrap" style={{ textAlign: "center", paddingTop: 60 }}>
        <div style={{ fontSize: 48 }}>✅</div>
        <h1 style={{ fontSize: 24, margin: "10px 0 4px" }}>¡{done} cargado!</h1>
        <p style={{ color: "var(--txt-3)", marginBottom: 6 }}>
          {ciudadActual ? `${ciudadActual.nombre} · ` : ""}Pendiente de verificar.
        </p>
        <p style={{ color: "var(--txt-3)", marginBottom: 22 }}>Llevás {count} en este recorrido.</p>
        <button className="btn btn-primary" style={{ width: "100%" }} onClick={otro}>Cargar otro negocio</button>
      </div>
    );
  }

  return (
    <div className="campo-wrap">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div>
          <span className="eyebrow"><Pin style={{ width: 13, height: 13 }} /> Carga de negocios</span>
          {count > 0 && <div style={{ fontSize: 12, color: "var(--neon)" }}>{count} cargados hoy</div>}
        </div>
        <button className="link-more" onClick={onLogout} style={{ padding: "6px 12px" }}>Salir</button>
      </div>

      <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>

        {/* ── Ciudad ── */}
        <div>
          <label className="campo-lbl">Ciudad *</label>
          <select className="adm-input" value={ciudadSlug} onChange={(e) => setCiudadSlug(e.target.value)}>
            {ciudades.length === 0 ? (
              <option value="bermejo">Bermejo</option>
            ) : (
              <>
                {bolivianas.length > 0 && (
                  <optgroup label="🇧🇴 Bolivia">
                    {bolivianas.map((c) => <option key={c.slug} value={c.slug}>{c.nombre}</option>)}
                  </optgroup>
                )}
                {argentinas.length > 0 && (
                  <optgroup label="🇦🇷 Argentina">
                    {argentinas.map((c) => <option key={c.slug} value={c.slug}>{c.nombre}</option>)}
                  </optgroup>
                )}
              </>
            )}
          </select>
        </div>

        {/* ── Nombre ── */}
        <input className="adm-input" value={f.nombre} onChange={(e) => set("nombre", e.target.value)} placeholder="Nombre del negocio *" />

        {/* ── WhatsApp ── */}
        <div>
          <label className="campo-lbl">WhatsApp del negocio *</label>
          <div className="cel-wrap">
            <span className="cel-flag">{prefijo === "54" ? "🇦🇷" : "🇧🇴"} +{prefijo}</span>
            <input className="adm-input" type="tel" inputMode="numeric" value={f.cel}
              onChange={(e) => set("cel", e.target.value)} placeholder={prefijo === "54" ? "3514XXXXXX" : "7XXXXXXX"} />
          </div>
        </div>

        {/* ── Rubros ── */}
        <div>
          <label className="campo-lbl">Categorías (podés elegir más de una)</label>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
            {rubros.map((r) => (
              <ChipToggle key={r.slug} label={r.nombre} active={rubroSlugs.includes(r.slug)}
                onClick={() => setRubroSlugs((prev) => toggle(prev, r.slug))} />
            ))}
          </div>
        </div>

        {/* ── Modalidad ── */}
        <div>
          <label className="campo-lbl">¿Vende por mayor o menor?</label>
          <div className="seg">
            {MODALIDADES.map((m) => (
              <button type="button" key={m.key} className={f.modalidad === m.key ? "active" : ""} onClick={() => set("modalidad", m.key)}>{m.label}</button>
            ))}
          </div>
        </div>

        {/* ── Descripción / audio ── */}
        <div>
          <label className="campo-lbl">¿Qué vende? Grabá un audio o escribí *</label>
          {!grabando ? (
            <button type="button" className="btn btn-ghost" style={{ width: "100%", marginBottom: 8 }}
              onClick={iniciarGrabacion} disabled={transcribiendo}>
              🎤 {transcribiendo ? "Transcribiendo…" : "Grabar descripción"}
            </button>
          ) : (
            <button type="button" className="btn btn-primary" style={{ width: "100%", marginBottom: 8 }} onClick={detenerGrabacion}>
              <span className="dot-live" style={{ background: "#05130c" }} /> Detener y transcribir
            </button>
          )}
          <textarea className="adm-input" rows={3} value={f.descripcion} onChange={(e) => set("descripcion", e.target.value)}
            placeholder="Ej: Gomería y repuestos de moto. Importa desde China. Pedido mínimo 1 caja." style={{ resize: "vertical" }} />
        </div>

        {/* ── Info fronteriza (diferencial) ── */}
        <button type="button" className="mas-toggle" onClick={() => setMasFrontera((v) => !v)}>
          {masFrontera ? "− Ocultar info comercial" : "+ Info comercial (monedas, envíos, importación…)"}
        </button>
        {masFrontera && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14, padding: "12px 0" }}>

            <div>
              <label className="campo-lbl">Monedas que acepta</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                {MONEDAS.map((m) => (
                  <ChipToggle key={m.key} label={m.label} active={monedas.includes(m.key)}
                    onClick={() => setMonedas((prev) => toggle(prev, m.key))} />
                ))}
              </div>
            </div>

            <label style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 13.5, color: "var(--txt-2)" }}>
              <input type="checkbox" checked={enviosInt} onChange={(e) => setEnviosInt(e.target.checked)} />
              Hace envíos internacionales
            </label>

            <label style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 13.5, color: "var(--txt-2)" }}>
              <input type="checkbox" checked={factura} onChange={(e) => setFactura(e.target.checked)} />
              Entrega factura / comprobante oficial
            </label>

            <label style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 13.5, color: "var(--txt-2)" }}>
              <input type="checkbox" checked={tieneStock} onChange={(e) => setTieneStock(e.target.checked)} />
              Tiene stock disponible hoy
            </label>

            <div>
              <label className="campo-lbl">Importa desde (si aplica)</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                {ORIGENES.map((o) => (
                  <ChipToggle key={o.key} label={o.label} active={origenes.includes(o.key)}
                    onClick={() => setOrigenes((prev) => toggle(prev, o.key))} />
                ))}
              </div>
            </div>

            <input className="adm-input" value={f.pedido_minimo} onChange={(e) => set("pedido_minimo", e.target.value)}
              placeholder="Pedido mínimo (ej: 1 caja, $500, 12 unidades)" />

            <input className="adm-input" value={f.horario} onChange={(e) => set("horario", e.target.value)}
              placeholder="Horario (ej: Lun–Sab 8–20hs)" />
          </div>
        )}

        {/* ── GPS ── */}
        <div>
          <label className="campo-lbl">Ubicación (parado en la puerta)</label>
          <button type="button" className={`btn ${coords ? "btn-ghost" : "btn-primary"}`} style={{ width: "100%" }} onClick={ubicar}>
            <Pin style={{ width: 17, height: 17 }} /> {coords ? "Ubicación tomada ✓ — tomar de nuevo" : "Usar mi ubicación actual"}
          </button>
          {coords && <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}>📍 {coords.lat.toFixed(5)}, {coords.lng.toFixed(5)} (±{coords.acc} m)</div>}
          {geoMsg && <div style={{ fontSize: 12.5, color: "var(--amber)", marginTop: 6 }}>{geoMsg}</div>}
        </div>

        {/* ── Foto ── */}
        <div>
          <label className="campo-lbl">Foto del negocio</label>
          <label className="foto-drop">
            {preview ? <img src={preview} alt="" /> : <span>📷 Sacar foto / elegir</span>}
            <input type="file" accept="image/*" capture="environment" onChange={onFoto} hidden />
          </label>
        </div>

        <input className="adm-input" value={f.direccion} onChange={(e) => set("direccion", e.target.value)} placeholder="Dirección (Galería X, Local Y, calle…)" />

        {/* ── Opcionales (redes) ── */}
        <button type="button" className="mas-toggle" onClick={() => setMas((v) => !v)}>
          {mas ? "− Ocultar datos opcionales" : "+ Redes, email y video (opcional)"}
        </button>
        {mas && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <input className="adm-input" type="email" value={f.email} onChange={(e) => set("email", e.target.value)} placeholder="Email" />
            <input className="adm-input" value={f.facebook_url} onChange={(e) => set("facebook_url", e.target.value)} placeholder="Facebook / Marketplace (link)" />
            <input className="adm-input" value={f.instagram_url} onChange={(e) => set("instagram_url", e.target.value)} placeholder="Instagram (link o @usuario)" />
            <input className="adm-input" value={f.tiktok_url} onChange={(e) => set("tiktok_url", e.target.value)} placeholder="TikTok (link o @usuario)" />
            <input className="adm-input" value={f.sitio_web} onChange={(e) => set("sitio_web", e.target.value)} placeholder="Página web" />
            <input className="adm-input" value={f.video_url} onChange={(e) => set("video_url", e.target.value)} placeholder="Video (link de TikTok)" />
          </div>
        )}

        <label style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 13.5, color: "var(--txt-2)" }}>
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          El dueño aceptó aparecer en la plataforma
        </label>

        {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
        <button className="btn btn-primary" type="submit" disabled={saving} style={{ width: "100%", padding: 16 }}>
          {saving ? "Guardando…" : "Guardar negocio"}
        </button>
      </form>
      <div style={{ height: 40 }} />
    </div>
  );
}
