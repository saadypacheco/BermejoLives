"use client";

import { useEffect, useRef, useState } from "react";
import {
  agenteLogin, getAgenteToken, clearAgente, altaComercioCampo, transcribirAudio, sugerirRubros,
  misComercios, editarComercioAgente, eliminarComercioAgente, actualizarFotoComercioAgente, type ComercioAgente,
  listarFotosCampo, listarVideosCampo, subirFotoCampo, subirVideoCampo, borrarFotoCampo, borrarVideoCampo,
} from "@/lib/campo";
import { getCiudades, getRubros } from "@/lib/data";
import type { Ciudad, Rubro } from "@/lib/types";
import { Pin, User, Arrow, Edit } from "@/components/icons";
import { comprimirImagen } from "@/lib/imagen";
import { GaleriaUploader } from "@/components/galeria-uploader";
import { geoErrorMsg } from "@/lib/geo";
import { encolarAlta, contarPendientes, sincronizarPendientes } from "@/lib/offline-altas";

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
  const [rubros, setRubros] = useState<Rubro[]>([]);
  const [err, setErr] = useState("");
  const [editando, setEditando] = useState<ComercioAgente | null>(null);
  const [borrando, setBorrando] = useState<string | null>(null);

  const cargar = () => misComercios().then(setItems).catch((e) => setErr(e instanceof Error ? e.message : "Error"));
  useEffect(() => { cargar(); getRubros().then(setRubros); }, []);

  async function eliminar(c: ComercioAgente) {
    if (!window.confirm(`¿Dar de baja "${c.nombre}"? Deja de aparecer en URUKU, pero el registro no se borra.`)) return;
    setBorrando(c.id);
    try { await eliminarComercioAgente(c.id); setItems((prev) => prev?.filter((x) => x.id !== c.id) ?? prev); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo eliminar"); }
    finally { setBorrando(null); }
  }

  return (
    <div className="campo-wrap">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div>
          <span className="eyebrow"><Pin style={{ width: 13, height: 13 }} /> Mis comercios cargados</span>
          {items && <div style={{ fontSize: 12, color: "var(--neon)" }}>{items.length} en total</div>}
        </div>
        <button className="link-more" onClick={onLogout} style={{ padding: "6px 12px" }}>Salir</button>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        <button className="link-more" style={{ display: "flex", alignItems: "center", gap: 6 }} onClick={onVolver}>
          <Arrow style={{ width: 15, height: 15, transform: "rotate(180deg)" }} /> Volver
        </button>
        <button className="btn btn-ghost" style={{ flex: 1 }} onClick={onVolver}>+ Cargar otro comercio</button>
      </div>

      {err && <p style={{ color: "var(--pink)", fontSize: 13 }}>{err}</p>}
      {!items && !err && <p style={{ color: "var(--txt-3)" }}>Cargando…</p>}
      {items && items.length === 0 && <p style={{ color: "var(--txt-3)" }}>Todavía no cargaste ningún comercio.</p>}

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {items?.map((c) => (
          <div key={c.id} className="glass" style={{ padding: 14, borderRadius: 14, display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
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
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-sm" style={{ flex: 1, border: "1px solid var(--stroke)" }} onClick={() => setEditando(editando?.id === c.id ? null : c)}>
                <Edit style={{ width: 14, height: 14 }} /> Editar
              </button>
              <button className="btn btn-sm" style={{ flex: 1, border: "1px solid var(--stroke)", color: "var(--pink)" }} disabled={borrando === c.id} onClick={() => eliminar(c)}>
                {borrando === c.id ? "Eliminando…" : "Eliminar"}
              </button>
            </div>
            {editando?.id === c.id && (
              <EditarComercioForm
                comercio={c} rubros={rubros}
                onCancel={() => setEditando(null)}
                onGuardado={(actualizado) => { setItems((prev) => prev?.map((x) => (x.id === c.id ? { ...x, ...actualizado } : x)) ?? prev); setEditando(null); }}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
function EditarComercioForm({ comercio, rubros, onCancel, onGuardado }: {
  comercio: ComercioAgente; rubros: Rubro[]; onCancel: () => void; onGuardado: (patch: Partial<ComercioAgente>) => void;
}) {
  const [nombre, setNombre] = useState(comercio.nombre);
  const [whatsapp, setWhatsapp] = useState(comercio.whatsapp ?? "");
  const [direccion, setDireccion] = useState(comercio.direccion ?? "");
  const [modalidad, setModalidad] = useState(comercio.modalidad ?? "mayorista");
  const [rubroSlugs, setRubroSlugs] = useState<string[]>(comercio.rubros ? [comercio.rubros.slug] : []);
  const [foto, setFoto] = useState<File | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [subiendoFoto, setSubiendoFoto] = useState(false);
  const [err, setErr] = useState("");

  async function guardar() {
    if (!nombre.trim()) { setErr("El nombre es obligatorio"); return; }
    setGuardando(true); setErr("");
    try {
      let portada_url: string | null | undefined;
      if (foto) {
        setSubiendoFoto(true);
        portada_url = await actualizarFotoComercioAgente(comercio.id, foto);
        setSubiendoFoto(false);
      }
      await editarComercioAgente(comercio.id, {
        nombre: nombre.trim(), whatsapp: whatsapp.trim(), modalidad,
        direccion: direccion.trim() || undefined, rubro_slugs: rubroSlugs,
      });
      onGuardado({
        nombre: nombre.trim(), whatsapp: whatsapp.trim(), modalidad, direccion: direccion.trim() || null,
        rubros: rubros.find((r) => r.slug === rubroSlugs[0]) ?? comercio.rubros,
        ...(portada_url !== undefined ? { portada_url } : {}),
      });
    } catch (e) { setErr(e instanceof Error ? e.message : "No se pudo guardar"); }
    finally { setGuardando(false); setSubiendoFoto(false); }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, borderTop: "1px solid var(--stroke)", paddingTop: 10 }}>
      <input className="adm-input" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre" />
      <input className="adm-input" value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)} placeholder="WhatsApp" />
      <input className="adm-input" value={direccion} onChange={(e) => setDireccion(e.target.value)} placeholder="Punto de referencia" />
      <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, color: "var(--txt-3)" }}>
        Cambiar foto {subiendoFoto && "(subiendo…)"}
        <input type="file" accept="image/*" onChange={(e) => setFoto(e.target.files?.[0] ?? null)} />
      </label>
      <div className="seg">
        {MODALIDADES.map((m) => (
          <button type="button" key={m.key} className={modalidad === m.key ? "active" : ""} onClick={() => setModalidad(m.key)}>{m.label}</button>
        ))}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {rubros.map((r) => (
          <ChipToggle key={r.slug} label={r.nombre} active={rubroSlugs.includes(r.slug)} onClick={() => setRubroSlugs((s) => toggle(s, r.slug))} />
        ))}
      </div>
      {/* Galería del comercio ya cargado: agregar/quitar varias fotos y videos */}
      <div style={{ marginTop: 2 }}>
        <GaleriaUploader api={{
          cargarFotos: () => listarFotosCampo(comercio.id),
          subirFoto: (f, onP) => subirFotoCampo(comercio.id, f, onP),
          borrarFoto: (id) => borrarFotoCampo(comercio.id, id),
          cargarVideos: () => listarVideosCampo(comercio.id),
          subirVideo: (f, dur, onP) => subirVideoCampo(comercio.id, f, dur, onP),
          borrarVideo: (id) => borrarVideoCampo(comercio.id, id),
        }} comercioId={comercio.id} />
      </div>
      {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
      <div style={{ display: "flex", gap: 8 }}>
        <button className="btn btn-primary" style={{ flex: 1 }} disabled={guardando} onClick={guardar}>{guardando ? "Guardando…" : "Guardar cambios"}</button>
        <button className="btn btn-ghost" onClick={onCancel}>Cancelar</button>
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
      <h1 style={{ fontSize: 26, margin: "8px 0 4px" }}>Carga de comercios</h1>
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
  const [doneOffline, setDoneOffline] = useState(false);
  const [altaId,      setAltaId]      = useState<string | null>(null);
  const [count,       setCount]       = useState(0);
  const [err,         setErr]         = useState("");

  // Cola offline: altas guardadas sin señal que se suben cuando vuelve internet.
  const [pendientes,   setPendientes]   = useState(0);
  const [sincronizando, setSincronizando] = useState(false);
  const refrescarPend = () => contarPendientes().then(setPendientes).catch(() => {});
  async function sincronizar() {
    if (sincronizando) return;
    setSincronizando(true);
    try { await sincronizarPendientes(refrescarPend); } finally { setSincronizando(false); refrescarPend(); }
  }
  useEffect(() => {
    refrescarPend();
    sincronizar();                                  // intento al abrir
    const onOnline = () => sincronizar();
    window.addEventListener("online", onOnline);    // y al volver la señal
    return () => window.removeEventListener("online", onOnline);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
    // Alta mínima: solo la ubicación es obligatoria. Nombre, WhatsApp, descripción y
    // foto son opcionales (locales sin contacto → quedan como punto en el mapa).
    if (!coords) { setErr("Falta la ubicación — tocá \"Usar mi ubicación actual\"."); return; }
    if (comprimiendo) { setErr("Esperá a que termine de comprimir la foto."); return; }

    setSaving(true);
    const campos: Record<string, string> = {
      ciudad_slug: ciudadSlug, modalidad: f.modalidad,
      lat: String(coords.lat), lng: String(coords.lng), consentimiento: String(consent),
    };
    if (f.nombre.trim()) campos.nombre = f.nombre.trim();
    if (cel) campos.whatsapp = prefijo + cel;
    if (f.descripcion.trim()) campos.descripcion = f.descripcion.trim();
    if (f.direccion.trim()) campos.direccion = f.direccion.trim();
    const rubroList = rubroSlugs.length > 0 ? rubroSlugs : ["otros"];
    const online = typeof navigator === "undefined" || navigator.onLine;

    try {
      if (!online) throw new Error("__offline__");
      const fd = new FormData();
      Object.entries(campos).forEach(([k, v]) => fd.append(k, v));
      rubroList.forEach((r) => fd.append("rubro_slugs", r));
      if (foto) fd.append("foto", foto);
      const r = await altaComercioCampo(fd);
      setDone(r.comercio.nombre);
      setAltaId(r.comercio.id);
      setCount((c) => c + 1);
    } catch (ex) {
      // Sin señal o falló la red → guardar OFFLINE (se sube solo cuando vuelva internet).
      const esRed = !online || ex instanceof TypeError || /__offline__|fetch|network|Failed/i.test(String(ex));
      if (esRed) {
        try {
          await encolarAlta(campos, rubroList, foto);
          setDone(campos.nombre ?? "Comercio");
          setDoneOffline(true);
          setCount((c) => c + 1);
          refrescarPend();
        } catch {
          setErr("No se pudo guardar ni siquiera offline. Reintentá.");
        }
      } else {
        setErr(ex instanceof Error ? ex.message : "Error al guardar");
      }
    } finally {
      setSaving(false);
    }
  }

  function otro() {
    setF({ ...EMPTY }); setRubroSlugs([]); setIntentosAudio(0);
    setCoords(null); setGeoMsg(""); setFoto(null); setPreview(""); setConsent(true);
    setDone(null); setDoneOffline(false); setAltaId(null); setErr("");
  }

  if (done) {
    const ciudadActual = ciudades.find((c) => c.slug === ciudadSlug);
    return (
      <div className="campo-wrap" style={{ textAlign: "center", paddingTop: 60 }}>
        <div style={{ fontSize: 48 }}>{doneOffline ? "📴" : "✅"}</div>
        <h1 style={{ fontSize: 24, margin: "10px 0 4px" }}>¡{done} {doneOffline ? "guardado sin conexión" : "cargado"}!</h1>
        <p style={{ color: "var(--txt-3)", marginBottom: 6 }}>
          {doneOffline
            ? "Se sube solo cuando haya señal. Las fotos las agregás después desde \"mis comercios\"."
            : `${ciudadActual ? `${ciudadActual.nombre} · ` : ""}Pendiente de verificar.`}
        </p>
        <p style={{ color: "var(--txt-3)", marginBottom: 18 }}>Llevás {count} en este recorrido.{pendientes > 0 ? ` · ${pendientes} sin subir` : ""}</p>

        {altaId && (
          <div style={{ textAlign: "left", marginBottom: 18, padding: 14, borderRadius: 14, background: "var(--panel)", border: "1px solid var(--stroke)" }}>
            <p style={{ color: "var(--txt-2)", fontSize: 13.5, marginBottom: 12 }}>📸 Sumá fotos y videos del local (mejora la ficha y sirve de material para redes):</p>
            <GaleriaUploader api={{
              cargarFotos: () => listarFotosCampo(altaId),
              subirFoto: (f, onP) => subirFotoCampo(altaId, f, onP),
              borrarFoto: (id) => borrarFotoCampo(altaId, id),
              cargarVideos: () => listarVideosCampo(altaId),
              subirVideo: (f, dur, onP) => subirVideoCampo(altaId, f, dur, onP),
              borrarVideo: (id) => borrarVideoCampo(altaId, id),
            }} comercioId={altaId} />
          </div>
        )}

        <button className="btn btn-primary" style={{ width: "100%", marginBottom: 10 }} onClick={otro}>Cargar otro comercio</button>
        <button className="link-more" onClick={onVerMisComercios}>Ver mis comercios cargados</button>
      </div>
    );
  }

  const puedeGrabar = intentosAudio < MAX_INTENTOS_AUDIO;

  return (
    <div className="campo-wrap">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div>
          <span className="eyebrow"><Pin style={{ width: 13, height: 13 }} /> Carga de comercios</span>
          {count > 0 && <div style={{ fontSize: 12, color: "var(--neon)" }}>{count} cargados hoy</div>}
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          <button className="link-more" onClick={onVerMisComercios} style={{ padding: "6px 12px" }}>Mis comercios</button>
          <button className="link-more" onClick={onLogout} style={{ padding: "6px 12px" }}>Salir</button>
        </div>
      </div>

      {pendientes > 0 && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, background: "rgba(240,160,40,.12)", border: "1px solid rgba(240,160,40,.45)", color: "var(--amber)", borderRadius: 12, padding: "10px 12px", marginBottom: 12, fontSize: 13 }}>
          <span>📴 {pendientes} guardado{pendientes > 1 ? "s" : ""} sin conexión — se sube{pendientes > 1 ? "n" : ""} con señal</span>
          <button type="button" className="btn btn-ghost" style={{ padding: "5px 12px", whiteSpace: "nowrap" }} disabled={sincronizando} onClick={sincronizar}>
            {sincronizando ? "Subiendo…" : "Sincronizar"}
          </button>
        </div>
      )}

      <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>

        {/* ── Nombre ── */}
        <input className="adm-input" value={f.nombre} onChange={(e) => set("nombre", e.target.value)} placeholder="Nombre del comercio (opcional — si no, queda 'Comercio')" />

        {/* ── WhatsApp ── */}
        <div>
          <label className="campo-lbl">WhatsApp del comercio (opcional)</label>
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

        {/* ── Descripción: texto primero (siempre), audio como opción ── */}
        <div>
          <label className="campo-lbl">¿Qué vende? (opcional)</label>
          <textarea className="adm-input" rows={3} value={f.descripcion}
            onChange={(e) => set("descripcion", e.target.value)}
            onBlur={() => f.descripcion.trim() && sugerirDesdeDescripcion(f.descripcion)}
            placeholder="Ej: Gomería y repuestos de moto. Importa desde China. Pedido mínimo 1 caja." style={{ resize: "vertical" }} />
          {puedeGrabar && (
            !grabando ? (
              <button type="button" className="btn btn-ghost" style={{ width: "100%", marginTop: 8 }}
                onClick={iniciarGrabacion} disabled={transcribiendo}>
                🎤 {transcribiendo ? "Transcribiendo…" : "O grabá un audio"}
              </button>
            ) : (
              <button type="button" className="btn btn-primary" style={{ width: "100%", marginTop: 8 }} onClick={detenerGrabacion}>
                <span className="dot-live" style={{ background: "#05130c" }} /> Detener y transcribir
              </button>
            )
          )}
        </div>

        {/* ── Categorías: siempre visibles para elegir a mano (la IA además puede sugerir) ── */}
        <div>
          <label className="campo-lbl">Categoría{sugiriendo && " (sugiriendo…)"}</label>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
            {rubros.map((r) => (
              <ChipToggle key={r.slug} label={r.nombre} active={rubroSlugs.includes(r.slug)}
                onClick={() => setRubroSlugs((prev) => toggle(prev, r.slug))} />
            ))}
          </div>
        </div>

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
          <label className="campo-lbl">Foto del local (portada, opcional)</label>
          <label className="foto-drop">
            {preview ? <img src={preview} alt="" /> : <span>📷 Sacar foto / elegir</span>}
            <input type="file" accept="image/*" capture="environment" onChange={onFoto} hidden />
          </label>
          {comprimiendo && <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}>Comprimiendo foto…</div>}
          {!comprimiendo && foto && <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}>{(foto.size / 1024).toFixed(0)} KB</div>}
          <div style={{ fontSize: 12, color: "var(--neon)", marginTop: 8 }}>📸🎬 Después de guardar vas a poder sumar <b>más fotos y videos</b> del local.</div>
        </div>

        <input className="adm-input" value={f.direccion} onChange={(e) => set("direccion", e.target.value)}
          placeholder="Punto de referencia (ej: frente a la plaza, al lado de la farmacia)" />

        <label style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 13.5, color: "var(--txt-2)" }}>
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          El dueño aceptó aparecer en la plataforma
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
