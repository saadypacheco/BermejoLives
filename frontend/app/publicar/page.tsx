"use client";

import { useEffect, useRef, useState } from "react";
import { agenteLogin, getAgenteToken, clearAgente, altaComercioCampo, transcribirAudio, sugerirRubros, misComercios, type ComercioAgente } from "@/lib/campo";
import { getCiudades, getRubros } from "@/lib/data";
import type { Ciudad, Rubro } from "@/lib/types";
import { Pin, User } from "@/components/icons";
import { comprimirImagen } from "@/lib/imagen";
import { geoErrorMsg } from "@/lib/geo";

// Prefijo telefónico según país
const PREFIJO: Record<string, string> = { Bolivia: "591", Argentina: "54" };

const MODALIDADES = [
  { key: "mayorista", label: "Mayorista" },
  { key: "minorista", label: "Minorista" },
  { key: "ambos",     label: "Ambos" },
];

const MAX_INTENTOS_AUDIO = 2;

// ─────────────────────────────────────────────
export default function CampoPage() {
  const [authed, setAuthed] = useState(false);
  const [vista, setVista] = useState<"form" | "lista">("form");
  useEffect(() => setAuthed(Boolean(getAgenteToken())), []);
  if (!authed) return <Login onOk={() => setAuthed(true)} />;
  const onLogout = () => { clearAgente(); setAuthed(false); };
  if (vista === "lista") return <MisComercios onVolver={() => setVista("form")} onLogout={onLogout} />;
  return <FormCampo onLogout={onLogout} onVerMisComercios={() => setVista("lista")} />;
}

// ─────────────────────────────────────────────
function MisComercios({ onVolver, onLogout }: { onVolver: () => void; onLogout: () => void }) {
  const [items, setItems] = useState<ComercioAgente[] | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    misComercios().then(setItems).catch((e) => setErr(e instanceof Error ? e.message : "Error"));
  }, []);

  return (
    <div className="campo-wrap">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div>
          <span className="eyebrow"><Pin style={{ width: 13, height: 13 }} /> Mis negocios cargados</span>
          {items && <div style={{ fontSize: 12, color: "var(--neon)" }}>{items.length} en total</div>}
        </div>
        <button className="link-more" onClick={onLogout} style={{ padding: "6px 12px" }}>Salir</button>
      </div>

      <button className="btn btn-ghost" style={{ width: "100%", marginBottom: 14 }} onClick={onVolver}>
        + Cargar otro negocio
      </button>

      {err && <p style={{ color: "var(--pink)", fontSize: 13 }}>{err}</p>}
      {!items && !err && <p style={{ color: "var(--txt-3)" }}>Cargando…</p>}
      {items && items.length === 0 && <p style={{ color: "var(--txt-3)" }}>Todavía no cargaste ningún negocio.</p>}

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {items?.map((c) => (
          <div key={c.id} className="glass" style={{ padding: 14, borderRadius: 14, display: "flex", gap: 12, alignItems: "center" }}>
            <div style={{ width: 48, height: 48, borderRadius: 10, overflow: "hidden", background: "var(--panel)", flexShrink: 0, display: "grid", placeItems: "center", fontSize: 20 }}>
              {c.portada_url ? <img src={c.portada_url} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : "🏪"}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 700, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.nombre}</div>
              <div style={{ fontSize: 12.5, color: "var(--txt-3)" }}>{c.rubros?.nombre ?? "Sin rubro"}{c.direccion ? ` · ${c.direccion}` : ""}</div>
            </div>
            <span style={{ fontSize: 11, fontWeight: 700, padding: "3px 9px", borderRadius: 999, color: c.verificado ? "var(--neon)" : "var(--amber)", background: c.verificado ? "rgba(57,255,158,.12)" : "rgba(255,176,32,.12)" }}>
              {c.verificado ? "Verificado" : "Pendiente"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
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
const EMPTY = { nombre: "", cel: "", modalidad: "mayorista", direccion: "", descripcion: "" };

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

// Ciudad más cercana a un punto GPS (distancia euclidiana simple, alcanza para elegir entre pocas ciudades).
function ciudadMasCercana(ciudades: Ciudad[], lat: number, lng: number): Ciudad | null {
  const conCoords = ciudades.filter((c) => c.lat != null && c.lng != null);
  if (conCoords.length === 0) return null;
  let mejor = conCoords[0];
  let mejorDist = Infinity;
  for (const c of conCoords) {
    const d = (c.lat! - lat) ** 2 + (c.lng! - lng) ** 2;
    if (d < mejorDist) { mejorDist = d; mejor = c; }
  }
  return mejor;
}

function FormCampo({ onLogout, onVerMisComercios }: { onLogout: () => void; onVerMisComercios: () => void }) {
  const [ciudades, setCiudades] = useState<Ciudad[]>([]);
  const [rubros,   setRubros]   = useState<Rubro[]>([]);

  const [f, setF]               = useState({ ...EMPTY });
  const set = (k: keyof typeof EMPTY, v: string) => setF((s) => ({ ...s, [k]: v }));

  const [ciudadSlug,  setCiudadSlug]  = useState("bermejo");
  const [prefijo,     setPrefijo]     = useState("591");
  const [rubroSlugs,  setRubroSlugs]  = useState<string[]>([]);
  const [sugiriendo,  setSugiriendo]  = useState(false);

  const [coords,      setCoords]      = useState<{ lat: number; lng: number; acc: number } | null>(null);
  const [geoMsg,      setGeoMsg]      = useState("");
  const [foto,        setFoto]        = useState<File | null>(null);
  const [preview,     setPreview]     = useState("");
  const [comprimiendo,setComprimiendo]= useState(false);
  const [consent,     setConsent]     = useState(true);
  const [saving,      setSaving]      = useState(false);
  const [done,        setDone]        = useState<string | null>(null);
  const [count,       setCount]       = useState(0);
  const [err,         setErr]         = useState("");

  // Audio: hasta 2 intentos de grabación; al llegar al límite, solo queda escribir a mano.
  const [grabando,      setGrabando]      = useState(false);
  const [transcribiendo,setTranscribiendo]= useState(false);
  const [intentosAudio, setIntentosAudio] = useState(0);
  const recRef   = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    getCiudades().then(setCiudades);
    getRubros().then(setRubros);
  }, []);

  async function sugerirDesdeDescripcion(descripcion: string) {
    if (!descripcion.trim() || rubros.length === 0) return;
    setSugiriendo(true);
    try {
      const sugeridos = await sugerirRubros(descripcion, rubros);
      setRubroSlugs(sugeridos.length > 0 ? sugeridos : ["otros"]);
    } finally {
      setSugiriendo(false);
    }
  }

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
          const nueva = (f.descripcion ? f.descripcion + " " : "") + texto;
          setF((s) => ({ ...s, descripcion: nueva }));
          setIntentosAudio((n) => n + 1);
          await sugerirDesdeDescripcion(nueva);
        } catch (ex) {
          setErr(ex instanceof Error ? ex.message : "No se pudo transcribir — escribí a mano");
          setIntentosAudio((n) => n + 1);
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
        const lat = pos.coords.latitude, lng = pos.coords.longitude;
        setCoords({ lat, lng, acc: Math.round(pos.coords.accuracy) });
        setGeoMsg("");
        const cercana = ciudadMasCercana(ciudades, lat, lng);
        if (cercana) {
          setCiudadSlug(cercana.slug);
          setPrefijo(PREFIJO[cercana.pais] ?? "591");
        }
      },
      (e) => setGeoMsg(geoErrorMsg(e)),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  async function onFoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    if (!file) { setFoto(null); setPreview(""); return; }
    setPreview(URL.createObjectURL(file)); // vista previa inmediata, sin esperar la compresión
    setComprimiendo(true);
    const comprimida = await comprimirImagen(file);
    setComprimiendo(false);
    setFoto(comprimida);
  }

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    const cel = f.cel.replace(/\D/g, "");
    if (!f.nombre.trim() || !cel) { setErr("Faltan nombre y celular."); return; }
    if (!f.descripcion.trim()) { setErr("Falta qué vende (grabá un audio o escribí)."); return; }
    if (!coords) { setErr("Falta la ubicación — tocá \"Usar mi ubicación actual\"."); return; }
    if (comprimiendo) { setErr("Esperá a que termine de comprimir la foto."); return; }
    if (!foto) { setErr("Falta la foto del negocio."); return; }

    setSaving(true);
    const fd = new FormData();
    fd.append("nombre",      f.nombre);
    fd.append("whatsapp",    prefijo + cel);
    fd.append("ciudad_slug", ciudadSlug);
    (rubroSlugs.length > 0 ? rubroSlugs : ["otros"]).forEach((r) => fd.append("rubro_slugs", r));
    fd.append("modalidad",   f.modalidad);
    fd.append("descripcion", f.descripcion.trim());
    if (f.direccion.trim()) fd.append("direccion", f.direccion.trim());
    fd.append("lat", String(coords.lat));
    fd.append("lng", String(coords.lng));
    fd.append("consentimiento", String(consent));
    fd.append("foto", foto);

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
    setF({ ...EMPTY }); setRubroSlugs([]); setIntentosAudio(0);
    setCoords(null); setGeoMsg(""); setFoto(null); setPreview(""); setConsent(true);
    setDone(null); setErr("");
  }

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
        <button className="btn btn-primary" style={{ width: "100%", marginBottom: 10 }} onClick={otro}>Cargar otro negocio</button>
        <button className="link-more" onClick={onVerMisComercios}>Ver mis negocios cargados</button>
      </div>
    );
  }

  const puedeGrabar = intentosAudio < MAX_INTENTOS_AUDIO;

  return (
    <div className="campo-wrap">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div>
          <span className="eyebrow"><Pin style={{ width: 13, height: 13 }} /> Carga de negocios</span>
          {count > 0 && <div style={{ fontSize: 12, color: "var(--neon)" }}>{count} cargados hoy</div>}
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          <button className="link-more" onClick={onVerMisComercios} style={{ padding: "6px 12px" }}>Mis negocios</button>
          <button className="link-more" onClick={onLogout} style={{ padding: "6px 12px" }}>Salir</button>
        </div>
      </div>

      <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>

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
          <label className="campo-lbl">¿Qué vende? Grabá un audio *</label>
          {puedeGrabar ? (
            !grabando ? (
              <button type="button" className="btn btn-ghost" style={{ width: "100%", marginBottom: 8 }}
                onClick={iniciarGrabacion} disabled={transcribiendo}>
                🎤 {transcribiendo ? "Transcribiendo…" : `Grabar descripción${intentosAudio > 0 ? ` (intento ${intentosAudio + 1}/${MAX_INTENTOS_AUDIO})` : ""}`}
              </button>
            ) : (
              <button type="button" className="btn btn-primary" style={{ width: "100%", marginBottom: 8 }} onClick={detenerGrabacion}>
                <span className="dot-live" style={{ background: "#05130c" }} /> Detener y transcribir
              </button>
            )
          ) : (
            <p style={{ fontSize: 12.5, color: "var(--amber)", marginBottom: 8 }}>
              Ya grabaste {MAX_INTENTOS_AUDIO} veces — completá o corregí el texto a mano abajo.
            </p>
          )}
          {(intentosAudio > 0 || !puedeGrabar) && (
            <textarea className="adm-input" rows={3} value={f.descripcion}
              onChange={(e) => set("descripcion", e.target.value)}
              onBlur={() => sugerirDesdeDescripcion(f.descripcion)}
              placeholder="Ej: Gomería y repuestos de moto. Importa desde China. Pedido mínimo 1 caja." style={{ resize: "vertical" }} />
          )}
        </div>

        {/* ── Categorías: las sugiere la IA a partir de la descripción, el agente puede corregir ── */}
        {(rubroSlugs.length > 0 || sugiriendo) && (
          <div>
            <label className="campo-lbl">Categoría{sugiriendo && " (sugiriendo…)"}</label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
              {rubros.map((r) => (
                <ChipToggle key={r.slug} label={r.nombre} active={rubroSlugs.includes(r.slug)}
                  onClick={() => setRubroSlugs((prev) => toggle(prev, r.slug))} />
              ))}
            </div>
          </div>
        )}

        {/* ── GPS ── */}
        <div>
          <label className="campo-lbl">Ubicación (parado en la puerta) *</label>
          <button type="button" className={`btn ${coords ? "btn-ghost" : "btn-primary"}`} style={{ width: "100%" }} onClick={ubicar}>
            <Pin style={{ width: 17, height: 17 }} /> {coords ? "Ubicación tomada ✓ — tomar de nuevo" : "Usar mi ubicación actual"}
          </button>
          {coords && <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}>📍 {coords.lat.toFixed(5)}, {coords.lng.toFixed(5)} (±{coords.acc} m)</div>}
          {geoMsg && <div style={{ fontSize: 12.5, color: "var(--amber)", marginTop: 6 }}>{geoMsg}</div>}
        </div>

        {/* ── Foto ── */}
        <div>
          <label className="campo-lbl">Foto del negocio *</label>
          <label className="foto-drop">
            {preview ? <img src={preview} alt="" /> : <span>📷 Sacar foto / elegir</span>}
            <input type="file" accept="image/*" capture="environment" onChange={onFoto} hidden />
          </label>
          {comprimiendo && <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}>Comprimiendo foto…</div>}
          {!comprimiendo && foto && <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}>{(foto.size / 1024).toFixed(0)} KB</div>}
        </div>

        <input className="adm-input" value={f.direccion} onChange={(e) => set("direccion", e.target.value)}
          placeholder="Punto de referencia (ej: frente a la plaza, al lado de la farmacia)" />

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
