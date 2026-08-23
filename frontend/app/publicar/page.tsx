"use client";

import { useEffect, useRef, useState } from "react";
import {
  agenteLogin, getAgenteToken, clearAgente, altaComercioCampo,
  misComercios, editarComercioAgente, eliminarComercioAgente, actualizarFotoComercioAgente, type ComercioAgente,
  listarFotosCampo, listarVideosCampo, subirFotoCampo, subirVideoCampo, borrarFotoCampo, borrarVideoCampo,
  listarLugares, crearLugar, editarLugar, subirPortadaLugar, subirVideoLugar, type Lugar,
} from "@/lib/campo";
import { duracionVideo } from "@/lib/upload";
import { CapturaWhatsapp } from "@/components/captura-whatsapp";
import { getCiudades, getRubros } from "@/lib/data";
import type { Ciudad, Rubro } from "@/lib/types";
import { Pin, User, Arrow, Edit } from "@/components/icons";
import { comprimirImagen } from "@/lib/imagen";
import { GaleriaUploader } from "@/components/galeria-uploader";
import { AdminMap } from "@/components/admin-map";
import { geoErrorMsg } from "@/lib/geo";
import { encolarAlta, contarPendientes, sincronizarPendientes, listarPendientes,
         descartarPendiente, esIrrecuperable, type AltaPendiente } from "@/lib/offline-altas";

// Prefijo telefónico según país
// Prefijo telefónico para wa.me. Argentina lleva el 9 de móvil (549…): sin él
// el link no abre ningún chat. Bermejo es frontera, así que hay comercios
// con número de los dos países y el prefijo tiene que poder cambiarse a mano.
const PREFIJO: Record<string, string> = { Bolivia: "591", Argentina: "549" };

const MODALIDADES = [
  { key: "mayorista", label: "Mayorista" },
  { key: "minorista", label: "Minorista" },
  { key: "ambos",     label: "Ambos" },
];


// ─────────────────────────────────────────────
export default function CampoPage() {
  const [authed, setAuthed] = useState(false);
  const [vista, setVista] = useState<"form" | "lista">("form");
  useEffect(() => {
    setAuthed(Boolean(getAgenteToken()));
    // Entrada directa desde el shortcut de la PWA (mantener apretado el ícono).
    // Se lee de window en vez de useSearchParams para no arrastrar un Suspense.
    if (new URLSearchParams(window.location.search).get("vista") === "mis-comercios") {
      setVista("lista");
    }
  }, []);
  if (!authed) return <Login onOk={() => setAuthed(true)} />;
  const onLogout = () => { clearAgente(); setAuthed(false); };
  if (vista === "lista") return <MisComercios onVolver={() => setVista("form")} onLogout={onLogout} />;
  return <FormCampo onLogout={onLogout} onVerMisComercios={() => setVista("lista")} />;
}

// ─────────────────────────────────────────────
function normTxtA(s: string): string {
  return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}
// Motivos por los que un comercio del agente está incompleto (para completarlo).
function agenteIncompleto(c: ComercioAgente): string[] {
  const r: string[] = [];
  const nombre = (c.nombre ?? "").trim();
  const rubroNombre = (c.rubros?.nombre ?? "").trim();
  if (!nombre || nombre.toLowerCase() === "comercio" || (!!rubroNombre && nombre.toLowerCase() === rubroNombre.toLowerCase())) r.push("sin nombre");
  if (!c.portada_url) r.push("sin foto");
  if (!c.whatsapp && !c.telefono) r.push("sin contacto");
  if (!c.rubros) r.push("sin rubro");
  return r;
}

type FiltroAg = "todos" | "pendientes" | "verificados" | "incompletos";
type OrdenAg = "recientes" | "alfabetico" | "estado";

function MisComercios({ onVolver, onLogout }: { onVolver: () => void; onLogout: () => void }) {
  const [items, setItems] = useState<ComercioAgente[] | null>(null);
  const [rubros, setRubros] = useState<Rubro[]>([]);
  const [err, setErr] = useState("");
  const [editando, setEditando] = useState<ComercioAgente | null>(null);
  const [borrando, setBorrando] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [filtro, setFiltro] = useState<FiltroAg>("todos");
  const [orden, setOrden] = useState<OrdenAg>("recientes");
  const [vista, setVista] = useState<"lista" | "mapa">("lista");
  const [limitVis, setLimitVis] = useState(50);

  const cargar = () => misComercios().then(setItems).catch((e) => setErr(e instanceof Error ? e.message : "Error"));
  useEffect(() => { cargar(); getRubros().then(setRubros); }, []);
  useEffect(() => { setLimitVis(50); }, [filtro, q, orden]);

  async function eliminar(c: ComercioAgente) {
    if (!window.confirm(`¿Dar de baja "${c.nombre}"? Deja de aparecer en URUKU, pero el registro no se borra.`)) return;
    setBorrando(c.id);
    try { await eliminarComercioAgente(c.id); setItems((prev) => prev?.filter((x) => x.id !== c.id) ?? prev); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo eliminar"); }
    finally { setBorrando(null); }
  }

  const todos = items ?? [];
  const nVerificados = todos.filter((c) => c.verificado).length;
  const nPend = todos.length - nVerificados;
  const nIncompletos = todos.filter((c) => agenteIncompleto(c).length > 0).length;

  // A: filtro por estado → B: incompletos → búsqueda multi-campo → G: orden
  const porEstado = filtro === "todos" ? todos
    : filtro === "pendientes" ? todos.filter((c) => !c.verificado)
    : filtro === "verificados" ? todos.filter((c) => c.verificado)
    : todos.filter((c) => agenteIncompleto(c).length > 0);
  const nq = normTxtA(q.trim());
  const buscadas = !nq ? porEstado : porEstado.filter((c) =>
    [c.nombre, c.direccion, c.whatsapp, c.telefono, c.rubros?.nombre].map((x) => normTxtA(x ?? "")).join(" ").includes(nq));
  const filtradas = [...buscadas].sort((a, b) => {
    if (orden === "alfabetico") return (a.nombre ?? "").localeCompare(b.nombre ?? "");
    if (orden === "estado") return Number(a.verificado) - Number(b.verificado);
    return (b.created_at ?? "").localeCompare(a.created_at ?? "");
  });
  const visibles = filtradas.slice(0, limitVis);

  const chips: { key: FiltroAg; label: string; n: number; amber?: boolean }[] = [
    { key: "todos", label: "Todos", n: todos.length },
    { key: "pendientes", label: "Pendientes", n: nPend },
    { key: "verificados", label: "Verificados", n: nVerificados },
    { key: "incompletos", label: "Incompletos", n: nIncompletos, amber: true },
  ];

  return (
    <div className="campo-wrap">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div>
          <span className="eyebrow"><Pin style={{ width: 13, height: 13 }} /> Mis comercios cargados</span>
          {items && <div style={{ fontSize: 12, color: "var(--neon)" }}>{items.length} en total</div>}
        </div>
        <button className="link-more" onClick={onLogout} style={{ padding: "6px 12px" }}>Salir</button>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button className="link-more" style={{ display: "flex", alignItems: "center", gap: 6 }} onClick={onVolver}>
          <Arrow style={{ width: 15, height: 15, transform: "rotate(180deg)" }} /> Volver
        </button>
        <button className="btn btn-ghost" style={{ flex: 1 }} onClick={onVolver}>+ Cargar otro comercio</button>
      </div>

      {/* Buscador (A) + orden (G) + vista lista/mapa (D) */}
      <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap", alignItems: "center" }}>
        <input className="adm-input" style={{ flex: 1, minWidth: 160 }} value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar por nombre, dirección, teléfono…" />
        <select className="adm-input" style={{ width: "auto" }} value={orden} onChange={(e) => setOrden(e.target.value as OrdenAg)}>
          <option value="recientes">Recientes</option>
          <option value="alfabetico">A → Z</option>
          <option value="estado">Pendientes primero</option>
        </select>
        <div style={{ display: "flex", border: "1px solid var(--stroke)", borderRadius: 8, overflow: "hidden" }}>
          {(["lista", "mapa"] as const).map((v) => (
            <button key={v} onClick={() => setVista(v)}
              style={{ padding: "8px 12px", fontSize: 13, border: "none",
                background: vista === v ? "rgba(57,255,158,.12)" : "transparent",
                color: vista === v ? "var(--neon)" : "var(--txt-2)", fontWeight: vista === v ? 700 : 400 }}>
              {v === "lista" ? "☰ Lista" : "🗺 Mapa"}
            </button>
          ))}
        </div>
      </div>

      {/* Filtros por estado (B: incluye Incompletos) */}
      <div style={{ display: "flex", gap: 6, marginBottom: 14, flexWrap: "wrap" }}>
        {chips.map(({ key, label, n, amber }) => {
          const activo = filtro === key;
          const col = amber ? "var(--amber)" : "var(--neon)";
          return (
            <button key={key} onClick={() => setFiltro(key)}
              style={{ padding: "5px 12px", borderRadius: 20, border: "1px solid", fontSize: 12.5,
                borderColor: activo ? col : "var(--stroke)",
                background: activo ? "rgba(57,255,158,.10)" : "transparent",
                color: activo ? col : "var(--txt-2)", fontWeight: activo ? 700 : 400 }}>
              {label} ({n})
            </button>
          );
        })}
      </div>

      {err && <p style={{ color: "var(--pink)", fontSize: 13 }}>{err}</p>}
      {!items && !err && <p style={{ color: "var(--txt-3)" }}>Cargando…</p>}
      {items && items.length === 0 && <p style={{ color: "var(--txt-3)" }}>Todavía no cargaste ningún comercio.</p>}
      {items && items.length > 0 && filtradas.length === 0 && <p style={{ color: "var(--txt-3)" }}>Sin resultados para ese filtro/búsqueda.</p>}

      {/* Vista MAPA (D): tocá un pin y se abre el editor de ese comercio (ideal para los sin nombre) */}
      {vista === "mapa" ? (
        editando ? (
          <div className="glass" style={{ padding: 14, borderRadius: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6, gap: 8 }}>
              <b style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{editando.nombre || "Sin nombre"}</b>
              <button className="link-more" style={{ flexShrink: 0 }} onClick={() => setEditando(null)}>← Volver al mapa</button>
            </div>
            <EditarComercioForm
              comercio={editando} rubros={rubros}
              onCancel={() => setEditando(null)}
              onGuardado={(actualizado) => { setItems((prev) => prev?.map((x) => (x.id === editando.id ? { ...x, ...actualizado } : x)) ?? prev); setEditando(null); }}
            />
          </div>
        ) : (
          <AdminMap
            comercios={filtradas.map((c) => ({ id: c.id, nombre: c.nombre, lat: c.lat, lng: c.lng, rubro_slug: c.rubros?.slug ?? null, incompleto: agenteIncompleto(c).length > 0, lugar_id: c.lugar_id, lugar_nombre: c.lugares?.nombre ?? null, lugar_lat: c.lugares?.lat ?? null, lugar_lng: c.lugares?.lng ?? null, lugar_portada_thumb: c.lugares?.portada_thumb_url ?? null }))}
            onSelect={(id) => setEditando(todos.find((x) => x.id === id) ?? null)}
          />
        )
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {visibles.map((c) => {
            const motivos = agenteIncompleto(c);
            return (
            <div key={c.id} className="glass" style={{ padding: 14, borderRadius: 14, display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <div style={{ width: 48, height: 48, borderRadius: 10, overflow: "hidden", background: "var(--panel)", flexShrink: 0, display: "grid", placeItems: "center", fontSize: 20 }}>
                  {(c.portada_thumb_url || c.portada_url) ? <img src={(c.portada_thumb_url || c.portada_url) as string} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : "🏪"}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.nombre || "Sin nombre"}</div>
                  <div style={{ fontSize: 12.5, color: "var(--txt-3)" }}>{c.rubros?.nombre ?? "Sin rubro"}{c.lugares?.nombre ? ` · 🏬 ${c.lugares.nombre}${c.puesto ? ` #${c.puesto}` : ""}` : c.direccion ? ` · ${c.direccion}` : ""}</div>
                </div>
                <span style={{ fontSize: 11, fontWeight: 700, padding: "3px 9px", borderRadius: 999, color: c.verificado ? "var(--neon)" : "var(--amber)", background: c.verificado ? "rgba(57,255,158,.12)" : "rgba(255,176,32,.12)" }}>
                  {c.verificado ? "Verificado" : "Pendiente"}
                </span>
              </div>
              {motivos.length > 0 && (
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {motivos.map((m) => (
                    <span key={m} style={{ fontSize: 11, color: "var(--amber)", border: "1px dashed var(--amber)", padding: "1px 7px", borderRadius: 10 }}>⚠️ {m}</span>
                  ))}
                </div>
              )}
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
            );
          })}
          {filtradas.length > limitVis && (
            <button className="btn btn-ghost" onClick={() => setLimitVis((n) => n + 50)}>
              Ver más ({filtradas.length - limitVis} restantes)
            </button>
          )}
        </div>
      )}
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
const EMPTY = { nombre: "", modalidad: "mayorista", direccion: "", prodObs: "" };

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

// Editor del mercado/galería (nombre + tipo + foto de portada + video de recorrido).
// El agente está parado ahí: es el mejor momento para la portada y el recorrido.
function MercadoEditor({ lugar, onClose, onSaved }: { lugar: Lugar; onClose: () => void; onSaved: (l: Lugar) => void }) {
  const [nombre, setNombre] = useState(lugar.nombre);
  const [tipo, setTipo] = useState(lugar.tipo || "mercado");
  const [portadaThumb, setPortadaThumb] = useState(lugar.portada_thumb_url ?? lugar.portada_url ?? null);
  const [videoUrl, setVideoUrl] = useState(lugar.video_url ?? null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  async function guardarNombre() {
    if (!nombre.trim()) { setErr("El nombre no puede quedar vacío"); return; }
    setBusy(true); setErr(""); setMsg("");
    try { const l = await editarLugar(lugar.id, { nombre: nombre.trim(), tipo }); onSaved(l); setMsg("Guardado ✓"); }
    catch (e) { setErr(e instanceof Error ? e.message : "Error"); }
    finally { setBusy(false); }
  }
  async function onPortada(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; e.target.value = ""; if (!file) return;
    setBusy(true); setErr(""); setMsg("");
    try {
      const comp = await comprimirImagen(file);
      const l = await subirPortadaLugar(lugar.id, comp);
      setPortadaThumb(l.portada_thumb_url ?? l.portada_url ?? null); onSaved(l); setMsg("Foto subida ✓");
    } catch (e) { setErr(e instanceof Error ? e.message : "No se pudo subir la foto"); }
    finally { setBusy(false); }
  }
  async function onVideo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; e.target.value = ""; if (!file) return;
    setErr(""); setMsg("");
    if (file.size > 50 * 1024 * 1024) { setErr("El video supera los 50 MB"); return; }
    const dur = await duracionVideo(file);
    if (dur > 60) { setErr(`El video dura ${dur}s — máximo 60s`); return; }
    setBusy(true);
    try { const l = await subirVideoLugar(lugar.id, file); setVideoUrl(l.video_url ?? null); onSaved(l); setMsg("Video subido ✓"); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo subir el video"); }
    finally { setBusy(false); }
  }

  return (
    <div className="glass" style={{ padding: 12, borderRadius: 12, display: "flex", flexDirection: "column", gap: 10, border: "1px solid rgba(139,92,246,.4)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <b style={{ fontSize: 13.5 }}>Editar mercado / galería</b>
        <button type="button" className="link-more" onClick={onClose}>Cerrar</button>
      </div>
      <input className="adm-input" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre" />
      <select className="adm-input" value={tipo} onChange={(e) => setTipo(e.target.value)}>
        <option value="mercado">Mercado</option>
        <option value="galeria">Galería</option>
        <option value="paseo">Paseo comercial</option>
        <option value="shopping">Shopping</option>
        <option value="referencia">Referencia (plaza, terminal…)</option>
      </select>
      <button type="button" className="btn btn-ghost" disabled={busy} onClick={guardarNombre}>Guardar nombre / tipo</button>
      <div style={{ display: "flex", gap: 10 }}>
        <label className="btn btn-ghost" style={{ flex: 1, textAlign: "center", cursor: "pointer" }}>
          📷 {portadaThumb ? "Cambiar portada" : "Foto de portada"}
          <input type="file" accept="image/*" capture="environment" hidden onChange={onPortada} />
        </label>
        <label className="btn btn-ghost" style={{ flex: 1, textAlign: "center", cursor: "pointer" }}>
          🎬 {videoUrl ? "Cambiar recorrido" : "Video recorrido"}
          <input type="file" accept="video/*" capture="environment" hidden onChange={onVideo} />
        </label>
      </div>
      {(portadaThumb || videoUrl) && (
        <div style={{ display: "flex", gap: 10 }}>
          {portadaThumb && <img src={portadaThumb} alt="" style={{ width: 70, height: 70, objectFit: "cover", borderRadius: 8 }} />}
          {videoUrl && <video src={videoUrl} muted playsInline preload="metadata" style={{ width: 70, height: 70, objectFit: "cover", borderRadius: 8, background: "#000" }} />}
        </div>
      )}
      {busy && <span style={{ fontSize: 12, color: "var(--txt-3)" }}>Subiendo…</span>}
      {msg && <span style={{ fontSize: 12, color: "var(--neon)" }}>{msg}</span>}
      {err && <span style={{ fontSize: 12, color: "var(--pink)" }}>{err}</span>}
    </div>
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

  // Lugares (mercados/galerías): dónde está el puesto, opcional
  const [lugares,     setLugares]     = useState<Lugar[]>([]);
  const [lugarId,     setLugarId]     = useState("");
  const [puesto,      setPuesto]      = useState("");
  const [nuevoLugar,  setNuevoLugar]  = useState("");
  const [creandoLugar,setCreandoLugar]= useState(false);
  // "Modo mercado": recuerda el lugar recién cargado para seguir con el próximo puesto
  const [subioLugar,  setSubioLugar]  = useState<{ id: string; nombre: string } | null>(null);
  const [ultimoPuesto,setUltimoPuesto]= useState("");
  const [editMercado, setEditMercado] = useState(false);

  const [coords,      setCoords]      = useState<{ lat: number; lng: number; acc: number } | null>(null);
  const [geoMsg,      setGeoMsg]      = useState("");
  const [foto,        setFoto]        = useState<File | null>(null);
  const [preview,     setPreview]     = useState("");
  const [comprimiendo,setComprimiendo]= useState(false);
  const [consent,     setConsent]     = useState(true);
  const [saving,      setSaving]      = useState(false);
  const [done,        setDone]        = useState<string | null>(null);
  const [doneOffline, setDoneOffline] = useState(false);
  // Por qué quedó guardado sin subir. Vacío = de verdad no había señal.
  const [doneMotivo,  setDoneMotivo]  = useState("");
  // Código del local recién dado de alta: hay que dictárselo o anotárselo al
  // dueño en el momento — es lo que le permite mandar ofertas por WhatsApp sin
  // tener número cargado, sin login y sin haber pagado.
  const [doneCodigo,  setDoneCodigo]  = useState<string | null>(null);
  const [altaId,      setAltaId]      = useState<string | null>(null);
  // Queda en true una vez que se guardó el número en la pantalla siguiente.
  const [whatsappCargado, setWhatsappCargado] = useState(false);
  const [count,       setCount]       = useState(0);
  const [err,         setErr]         = useState("");

  // Cola offline: altas guardadas sin señal que se suben cuando vuelve internet.
  const [pendientes,   setPendientes]   = useState(0);
  const [sincronizando, setSincronizando] = useState(false);
  const refrescarPend = () => contarPendientes().then(setPendientes).catch(() => {});
  // Resultado del último intento manual. Sin esto el botón falla en silencio: se
  // reintenta, todo rebota, el contador no baja y no hay nada en pantalla que
  // explique por qué.
  const [syncMsg, setSyncMsg] = useState("");
  const [detallePend, setDetallePend] = useState<AltaPendiente[] | null>(null);

  async function verPendientes() {
    if (detallePend) { setDetallePend(null); return; }
    setDetallePend(await listarPendientes());
  }

  async function descartar(rec: AltaPendiente) {
    const nombre = rec.campos.nombre || "este comercio";
    if (!window.confirm(`¿Descartar "${nombre}"? No se puede recuperar.`)) return;
    await descartarPendiente(rec.id);
    setDetallePend(await listarPendientes());
    refrescarPend();
  }

  async function sincronizar(manual = false) {
    if (sincronizando) return;
    setSincronizando(true);
    if (manual) setSyncMsg("");
    try {
      const r = await sincronizarPendientes(refrescarPend);
      if (!manual) return;
      if (r.sinSenal) setSyncMsg("El celular está sin conexión — se suben solas cuando vuelva.");
      else if (r.fallas === 0 && r.subidas > 0) setSyncMsg(`✅ Subieron ${r.subidas}.`);
      else if (r.fallas > 0) {
        setSyncMsg(`${r.subidas > 0 ? `Subieron ${r.subidas}. ` : ""}Fallaron ${r.fallas}: ${r.errores.join(" · ")}`);
      }
    } catch (ex) {
      if (manual) setSyncMsg(ex instanceof Error ? ex.message : "No se pudo sincronizar");
    } finally {
      setSincronizando(false);
      refrescarPend();
    }
  }
  useEffect(() => {
    refrescarPend();
    sincronizar();                                  // intento al abrir
    const onOnline = () => sincronizar();
    window.addEventListener("online", onOnline);    // y al volver la señal
    return () => window.removeEventListener("online", onOnline);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  useEffect(() => {
    getCiudades().then(setCiudades);
    getRubros().then(setRubros);
  }, []);

  // Mercados/galerías de la ciudad (para el selector "¿está dentro de un mercado?")
  useEffect(() => { listarLugares(ciudadSlug).then(setLugares).catch(() => {}); }, [ciudadSlug]);

  async function crearNuevoLugar() {
    const nombre = nuevoLugar.trim();
    if (!nombre) return;
    setCreandoLugar(true);
    setErr("");
    try {
      const lugar = await crearLugar({ nombre, ciudad_slug: ciudadSlug, lat: coords?.lat ?? null, lng: coords?.lng ?? null });
      setLugares((prev) => [...prev, lugar].sort((a, b) => a.nombre.localeCompare(b.nombre)));
      setLugarId(lugar.id);
      setNuevoLugar("");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "No se pudo crear el mercado");
    } finally {
      setCreandoLugar(false);
    }
  }

  // El rubro ya no se elige ni se sugiere en el campo: se deduce en el servidor
  // del texto cargado, y después la IA lo recalcula desde las fotos. Sacar la
  // llamada acá evita además un request en zonas sin señal.
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
    // Alta mínima: solo la ubicación es obligatoria. Nombre, descripción y foto
    // son opcionales (locales sin contacto → quedan como punto en el mapa). El
    // WhatsApp ya no se pide acá: va en la pantalla siguiente.
    if (!coords) { setErr("Falta la ubicación — tocá \"Usar mi ubicación actual\"."); return; }
    if (comprimiendo) { setErr("Esperá a que termine de comprimir la foto."); return; }

    setSaving(true);
    const campos: Record<string, string> = {
      ciudad_slug: ciudadSlug, modalidad: f.modalidad,
      lat: String(coords.lat), lng: String(coords.lng), consentimiento: String(consent),
    };
    if (f.nombre.trim()) campos.nombre = f.nombre.trim();
    if (f.prodObs.trim()) campos.prod_obs_human = f.prodObs.trim();
    if (f.direccion.trim()) campos.direccion = f.direccion.trim();
    if (lugarId && lugarId !== "__nuevo__") campos.lugar_id = lugarId;
    if (puesto.trim()) campos.puesto = puesto.trim();
    const lugarActual = (lugarId && lugarId !== "__nuevo__") ? lugares.find((l) => l.id === lugarId) ?? null : null;
    // Sin chips en el formulario: el backend deduce los rubros del texto y la IA
    // los recalcula desde las fotos. "otros" es sólo el punto de partida.
    const rubroList = ["otros"];
    const online = typeof navigator === "undefined" || navigator.onLine;

    try {
      if (!online) throw new Error("__offline__");
      const fd = new FormData();
      Object.entries(campos).forEach(([k, v]) => fd.append(k, v));
      rubroList.forEach((r) => fd.append("rubro_slugs", r));
      if (foto) fd.append("foto", foto);
      const r = await altaComercioCampo(fd);
      setDone(r.comercio.nombre);
      setDoneCodigo(r.comercio.codigo_formateado ?? null);
      setAltaId(r.comercio.id);
      setCount((c) => c + 1);
      setSubioLugar(lugarActual ? { id: lugarActual.id, nombre: lugarActual.nombre } : null);
      setUltimoPuesto(puesto);
      listarLugares(ciudadSlug).then(setLugares).catch(() => {});   // refresca el conteo del mercado
    } catch (ex) {
      // Falló la subida → guardar OFFLINE igual, así el alta NUNCA se pierde.
      //
      // Antes esto sólo encolaba si parecía un problema de red, y además la
      // pantalla decía "sin conexión" pasara lo que pasara. Con un backend
      // roto el agente se pasó una hora buscando señal con el celular
      // perfecto. Ahora se encola siempre y se distingue el motivo real.
      const esRed = !online || ex instanceof TypeError || /__offline__|fetch|network|Failed/i.test(String(ex));
      const motivo = ex instanceof Error ? ex.message : String(ex);
      {
        try {
          await encolarAlta(campos, rubroList, foto);
          setDone(campos.nombre ?? "Comercio");
          setDoneOffline(true);
          setDoneMotivo(esRed ? "" : motivo);
          setCount((c) => c + 1);
          setSubioLugar(lugarActual ? { id: lugarActual.id, nombre: lugarActual.nombre } : null);
          setUltimoPuesto(puesto);
          refrescarPend();
        } catch {
          setErr("No se pudo guardar ni siquiera offline. Reintentá.");
        }
      }
    } finally {
      setSaving(false);
    }
  }

  function limpiar() {
    setF({ ...EMPTY });
    setCoords(null); setGeoMsg(""); setFoto(null); setPreview(""); setConsent(true);
    setNuevoLugar(""); setEditMercado(false); setDone(null); setDoneOffline(false); setDoneMotivo(""); setDoneCodigo(null); setAltaId(null); setWhatsappCargado(false); setErr("");
  }
  function otro() {
    limpiar();
    setLugarId(""); setPuesto(""); setSubioLugar(null);   // sale del mercado (a la calle u otro)
  }
  // Sigue cargando en el MISMO mercado: mantiene el lugar y sugiere el próximo N° de puesto.
  function otroPuestoAca() {
    limpiar();
    setLugarId(subioLugar?.id ?? "");
    const m = ultimoPuesto.trim().match(/^(\d+)$/);
    setPuesto(m ? String(parseInt(m[1], 10) + 1) : "");
  }

  if (done) {
    const ciudadActual = ciudades.find((c) => c.slug === ciudadSlug);
    return (
      <div className="campo-wrap" style={{ textAlign: "center", paddingTop: 60 }}>
        <div style={{ fontSize: 48 }}>{doneOffline ? "📴" : "✅"}</div>
        <h1 style={{ fontSize: 24, margin: "10px 0 4px" }}>¡{done} {doneOffline ? "guardado sin conexión" : "cargado"}!</h1>
        <p style={{ color: "var(--txt-3)", marginBottom: 6 }}>
          {doneOffline
            ? (doneMotivo
                ? `Quedó guardado en el celular, pero NO por falta de señal: ${doneMotivo}`
                : "Se sube solo cuando haya señal. Las fotos las agregás después desde \"mis comercios\".")
            : `${ciudadActual ? `${ciudadActual.nombre} · ` : ""}Pendiente de verificar.`}
        </p>
        <p style={{ color: "var(--txt-3)", marginBottom: 18 }}>Llevás {count} en este recorrido.{pendientes > 0 ? ` · ${pendientes} sin subir` : ""}</p>

        {doneCodigo && (
          <div style={{ marginBottom: 18, padding: 16, borderRadius: 14, background: "var(--panel)", border: "2px solid var(--neon)" }}>
            <p style={{ color: "var(--txt-2)", fontSize: 13.5, marginBottom: 8 }}>
              📝 Dejale este código al dueño:
            </p>
            <div style={{ fontSize: 30, fontWeight: 800, letterSpacing: 3, color: "var(--neon)", fontFamily: "monospace", marginBottom: 10 }}>
              {doneCodigo}
            </div>
            <p style={{ color: "var(--txt-3)", fontSize: 12.5, lineHeight: 1.5, marginBottom: 10 }}>
              Con este código puede mandar sus ofertas por WhatsApp desde cualquier
              celular, sin cuenta y sin cargar su número. Sólo tiene que escribirlo
              en el mensaje.
            </p>
            <button
              className="btn btn-ghost"
              style={{ width: "100%" }}
              onClick={() => {
                const texto = `Tu código de URUKU es ${doneCodigo}. Mandá tus ofertas por WhatsApp escribiendo ese código en el mensaje.`;
                navigator.clipboard?.writeText(texto).catch(() => {});
              }}
            >
              Copiar mensaje para el dueño
            </button>
          </div>
        )}

        {/* El WhatsApp va ACÁ y no en el formulario: el agente releva el local
            primero y recién después se pone a hablar con la persona, así que el
            número aparece al final de esa charla. Va antes de la galería porque
            es lo que se pide cara a cara, mientras el otro está enfrente. */}
        {altaId && !whatsappCargado && (
          <CapturaWhatsapp
            comercioId={altaId}
            nombre={done}
            prefijoInicial={prefijo}
            onGuardado={() => setWhatsappCargado(true)}
          />
        )}

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

        {subioLugar && (
          <button className="btn btn-primary" style={{ width: "100%", marginBottom: 10, background: "#6d28d9", borderColor: "#6d28d9", color: "#fff" }} onClick={otroPuestoAca}>
            ➕ Otro puesto en {subioLugar.nombre}
          </button>
        )}
        <button className={subioLugar ? "btn btn-ghost" : "btn btn-primary"} style={{ width: "100%", marginBottom: 10 }} onClick={otro}>Cargar otro comercio {subioLugar ? "(a la calle / otro)" : ""}</button>
        <button className="link-more" onClick={onVerMisComercios}>Ver mis comercios cargados</button>
      </div>
    );
  }


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
        <div style={{ background: "rgba(240,160,40,.12)", border: "1px solid rgba(240,160,40,.45)", color: "var(--amber)", borderRadius: 12, padding: "10px 12px", marginBottom: 12, fontSize: 13 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
            <span>📴 {pendientes} guardado{pendientes > 1 ? "s" : ""} sin conexión — se sube{pendientes > 1 ? "n" : ""} con señal</span>
            <button type="button" className="btn btn-ghost" style={{ padding: "5px 12px", whiteSpace: "nowrap" }} disabled={sincronizando} onClick={() => sincronizar(true)}>
              {sincronizando ? "Subiendo…" : "Sincronizar"}
            </button>
          </div>
          {syncMsg && (
            <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid rgba(240,160,40,.3)", fontSize: 12.5, lineHeight: 1.45, wordBreak: "break-word" }}>
              {syncMsg}
            </div>
          )}
          <button type="button" className="link-more" style={{ color: "var(--amber)", marginTop: 6, padding: 0 }} onClick={verPendientes}>
            {detallePend ? "Ocultar" : "Ver cuáles son"}
          </button>
          {detallePend && (
            <div style={{ marginTop: 8, borderTop: "1px solid rgba(240,160,40,.3)", paddingTop: 8 }}>
              {detallePend.map((rec) => {
                const roto = esIrrecuperable(rec);
                return (
                  <div key={rec.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, padding: "5px 0", fontSize: 12.5 }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600 }}>{rec.campos.nombre || "(sin nombre)"}</div>
                      <div style={{ opacity: 0.8 }}>
                        {new Date(rec.creado).toLocaleString("es-BO")}
                        {roto && " · sin GPS: no va a entrar nunca"}
                      </div>
                      {/* Las coordenadas a la vista: si una falla por "falta la
                          ubicación" pero acá se ven, el problema está en el envío
                          y no en el dato. Sin esto hay que adivinar. */}
                      <div style={{ opacity: 0.65, fontFamily: "monospace", fontSize: 11 }}>
                        {rec.campos.lat && rec.campos.lng
                          ? `${Number(rec.campos.lat).toFixed(5)}, ${Number(rec.campos.lng).toFixed(5)}`
                          : "sin coordenadas"}
                        {rec.foto ? " · con foto" : " · sin foto"}
                      </div>
                    </div>
                    {/* Se puede descartar CUALQUIERA, no sólo las rotas: si una
                        se traba por lo que sea, tiene que haber forma de sacarla
                        de la cola sin borrar los datos del navegador. */}
                    <button type="button" className="link-more" style={{ color: "var(--pink)", flexShrink: 0, padding: 0 }} onClick={() => descartar(rec)}>
                      Descartar
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>

        {/* Banner "modo mercado": el lugar queda fijado hasta que el agente salga */}
        {lugarId && lugarId !== "__nuevo__" && (() => {
          const l = lugares.find((x) => x.id === lugarId);
          return (
            <>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, background: "rgba(109,40,217,.14)", border: "1px solid rgba(139,92,246,.45)", color: "#c4b5fd", borderRadius: 12, padding: "9px 12px", fontSize: 13 }}>
                <span>🏬 Cargando en <b>{l?.nombre ?? "mercado"}</b>{l?.n_comercios ? ` · ya llevás ${l.n_comercios}` : ""}</span>
                <div style={{ display: "flex", gap: 10, flexShrink: 0 }}>
                  <button type="button" className="link-more" style={{ color: "#c4b5fd" }} onClick={() => setEditMercado((v) => !v)}>✏️ Editar</button>
                  <button type="button" className="link-more" style={{ color: "#c4b5fd" }} onClick={() => { setLugarId(""); setPuesto(""); setEditMercado(false); }}>Salir</button>
                </div>
              </div>
              {editMercado && l && (
                <MercadoEditor lugar={l} onClose={() => setEditMercado(false)}
                  onSaved={(nl) => setLugares((prev) => prev.map((x) => (x.id === nl.id ? { ...x, ...nl } : x)))} />
              )}
            </>
          );
        })()}

        {/* ── Nombre ── */}
        <input className="adm-input" value={f.nombre} onChange={(e) => set("nombre", e.target.value)} placeholder="Nombre del comercio (opcional — si no, queda 'Comercio')" />

        {/* El WhatsApp NO va acá. Se pide en la pantalla siguiente, después de
            guardar: el agente releva el local primero y recién después se pone a
            hablar con la persona, así que el número aparece al final de esa
            charla. Tenerlo en este formulario obligaba a volver a un campo que
            ya había quedado atrás. Se pide en CapturaWhatsapp. */}

        {/* ── Modalidad ── */}
        <div>
          <label className="campo-lbl">¿Vende por mayor o menor?</label>
          <div className="seg">
            {MODALIDADES.map((m) => (
              <button type="button" key={m.key} className={f.modalidad === m.key ? "active" : ""} onClick={() => set("modalidad", m.key)}>{m.label}</button>
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

        {/* ── ¿Dentro de un mercado / galería? ── */}
        <div>
          <label className="campo-lbl">¿Está dentro de un mercado o galería? (opcional)</label>
          <select className="adm-input" value={lugarId} onChange={(e) => setLugarId(e.target.value)}>
            <option value="">No — local a la calle</option>
            {lugares.map((l) => <option key={l.id} value={l.id}>🏬 {l.nombre}{l.n_comercios ? ` (${l.n_comercios})` : ""}</option>)}
            <option value="__nuevo__">➕ Crear nuevo mercado/galería…</option>
          </select>
          {lugarId === "__nuevo__" && (
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <input className="adm-input" style={{ flex: 1 }} value={nuevoLugar} onChange={(e) => setNuevoLugar(e.target.value)} placeholder="Nombre (ej: Mercado Central)" />
              <button type="button" className="btn btn-ghost" style={{ whiteSpace: "nowrap" }} disabled={creandoLugar || !nuevoLugar.trim()} onClick={crearNuevoLugar}>
                {creandoLugar ? "Creando…" : "Crear"}
              </button>
            </div>
          )}
          {lugarId && lugarId !== "__nuevo__" && (
            <input className="adm-input" style={{ marginTop: 8 }} value={puesto} onChange={(e) => setPuesto(e.target.value)} placeholder="N° de puesto / local (opcional)" />
          )}
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

        {/* ── Productos observados: OPCIONAL. Lo importante son las fotos: de
               ahí se detectan después los productos, el rubro y la descripción.
               Por eso este bloque va DESPUÉS de la foto y no antes. ── */}
        <div>
          <label className="campo-lbl">¿Qué productos ves? (opcional)</label>
          <textarea className="adm-input" rows={2} value={f.prodObs}
            onChange={(e) => set("prodObs", e.target.value)}
            placeholder="Ej: zapatillas, championes, chinelas" style={{ resize: "vertical" }} />
          <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 4, lineHeight: 1.4 }}>
            Sólo si lo tenés a mano. Lo que escribas acá queda como dato tuyo y no
            se sobrescribe.
          </div>
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
