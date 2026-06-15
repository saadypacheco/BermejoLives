"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listPendientes, moderar, login, getToken, type PendingPub,
  listComerciosPorVerificar, listTodosComercios, verificarComercio, rechazarComercio,
  editarComercio, type ComercioPorVerificar,
  listSuscripciones, registrarPago, suspenderComercio, activarComercio,
  type ComercioSuscripcion, type EstadoSuscripcion,
} from "@/lib/api";
import { getRubros } from "@/lib/data";
import type { Rubro } from "@/lib/types";
import { precioFmt, MODALIDAD_LABEL, comoLlegarHref } from "@/lib/types";
import { Check, X, Edit, Pin, WhatsApp, Verified } from "@/components/icons";

export default function AdminPage() {
  const [authed, setAuthed] = useState(false);
  const [email, setEmail] = useState("admin@bermejolive.com");
  const [pass, setPass] = useState("");
  const [err, setErr] = useState("");
  const [tab, setTab] = useState<"publicaciones" | "comercios" | "suscripciones">("comercios");
  const [items, setItems] = useState<PendingPub[]>([]);
  const [comercios, setComercios] = useState<ComercioPorVerificar[]>([]);
  const [todosLosComercios, setTodosLosComercios] = useState<ComercioPorVerificar[]>([]);
  const [rubros, setRubros] = useState<Rubro[]>([]);
  const [suscripciones, setSuscripciones] = useState<ComercioSuscripcion[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getToken()) {
      setAuthed(true);
      load();
      loadComercios();
      loadSuscripciones();
      getRubros().then(setRubros);
    }
  }, []);

  async function load() {
    setLoading(true);
    try {
      setItems(await listPendientes("pendiente"));
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  async function loadComercios() {
    try {
      setComercios(await listComerciosPorVerificar());
      setTodosLosComercios(await listTodosComercios());
    } catch { setComercios([]); }
  }

  async function loadSuscripciones() {
    try { setSuscripciones(await listSuscripciones()); } catch { setSuscripciones([]); }
  }

  async function actComercio(id: string, accion: "verificar" | "rechazar") {
    setComercios((prev) => prev.filter((c) => c.id !== id)); // optimista
    try {
      accion === "verificar" ? await verificarComercio(id) : await rechazarComercio(id);
    } catch {
      loadComercios();
    }
  }

  async function doSuspender(id: string) {
    setSuscripciones((prev) => prev.map((c) => c.id === id ? { ...c, suspendido: true, suscripcion_estado: "suspendido" } : c));
    try { await suspenderComercio(id); } catch { loadSuscripciones(); }
  }

  async function doActivar(id: string) {
    setSuscripciones((prev) => prev.map((c) => c.id === id ? { ...c, suspendido: false, suscripcion_estado: "activo" } : c));
    try { await activarComercio(id); } catch { loadSuscripciones(); }
  }

  async function doLogin(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      await login(email, pass);
      setAuthed(true);
      load();
      loadComercios();
      loadSuscripciones();
    } catch {
      setErr("Credenciales incorrectas. ¿Está corriendo el backend?");
    }
  }

  async function act(id: string, estado: string) {
    const motivo = estado === "rechazado" || estado === "cambios" ? prompt("Motivo (opcional):") ?? undefined : undefined;
    setItems((prev) => prev.filter((p) => p.id !== id)); // optimista
    try {
      await moderar(id, estado, motivo);
    } catch {
      load(); // revertir si falla
    }
  }

  if (!authed) {
    return (
      <div className="wrap" style={{ maxWidth: 420, paddingTop: 100 }}>
        <Link className="brand" href="/" style={{ marginBottom: 30, display: "inline-flex" }}>
          <b style={{ fontSize: 22 }}>BER<i style={{ color: "var(--neon)", fontStyle: "normal" }}>MEJO</i></b>
        </Link>
        <h1 style={{ fontSize: 26, marginBottom: 6 }}>Panel de moderación</h1>
        <p style={{ color: "var(--txt-3)", marginBottom: 24 }}>Ingresá para revisar las publicaciones que llegan por WhatsApp.</p>
        <form onSubmit={doLogin} className="glass" style={{ padding: 22, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <input className="adm-input" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
          <input className="adm-input" type="password" value={pass} onChange={(e) => setPass(e.target.value)} placeholder="Contraseña" />
          {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
          <button className="btn btn-primary" type="submit">Entrar</button>
          <small style={{ color: "var(--txt-3)" }}>Demo: admin@bermejolive.com / bermejo1234</small>
        </form>
      </div>
    );
  }

  return (
    <div className="admin-main" style={{ maxWidth: 1000, margin: "0 auto" }}>
      <div className="admin-top">
        <div>
          <h1>Panel de moderación</h1>
          <p>Publicaciones por WhatsApp y comercios cargados en el recorrido</p>
        </div>
        <Link className="btn btn-ghost btn-sm" href="/">Ver sitio</Link>
      </div>

      <div className="auth-tabs" style={{ maxWidth: 640, marginBottom: 18 }}>
        <button className={tab === "comercios" ? "active" : ""} onClick={() => setTab("comercios")}>
          Negocios ({todosLosComercios.length}) {comercios.length > 0 && <span style={{ color: "var(--amber)" }}>· {comercios.length} pendientes</span>}
        </button>
        <button className={tab === "publicaciones" ? "active" : ""} onClick={() => setTab("publicaciones")}>
          Publicaciones {items.length > 0 && `(${items.length})`}
        </button>
        <button className={tab === "suscripciones" ? "active" : ""} onClick={() => { setTab("suscripciones"); loadSuscripciones(); }}>
          Suscripciones {suscripciones.filter((c) => ["por_vencer","vencido","suspendido"].includes(c.suscripcion_estado)).length > 0 && "⚠️"}
        </button>
      </div>

      {tab === "comercios" && (
        <TabComercios
          todos={todosLosComercios}
          pendientes={comercios}
          rubros={rubros}
          onVerificar={(id) => actComercio(id, "verificar")}
          onRechazar={(id) => actComercio(id, "rechazar")}
          onEdited={loadComercios}
        />
      )}

      {tab === "suscripciones" && (
        <TabSuscripciones
          items={suscripciones}
          onSuspender={doSuspender}
          onActivar={doActivar}
          onPago={() => loadSuscripciones()}
        />
      )}

      {tab === "publicaciones" && (
      <div className="panel-card glass">
        <div className="ph"><h3>Cola de aprobación</h3><span style={{ color: "var(--txt-3)", fontSize: 13 }}>Aprobá, rechazá o pedí cambios</span></div>
        {loading && <div className="mod-item" style={{ justifyContent: "center", color: "var(--txt-3)" }}>Cargando…</div>}
        {!loading && items.length === 0 && (
          <div className="mod-item" style={{ justifyContent: "center", color: "var(--txt-3)" }}>
            No hay publicaciones pendientes. (Si esperabas ver algunas, verificá que el backend FastAPI esté corriendo.)
          </div>
        )}
        {items.map((p) => (
          <div className="mod-item" key={p.id}>
            <img src={p.imagen_url ?? "https://picsum.photos/seed/ph/240/168"} alt="" />
            <div>
              <h4>{p.comercios?.nombre ?? "Comercio"} · <span style={{ textTransform: "capitalize", color: "var(--blue-soft)" }}>{p.tipo}</span></h4>
              <p>{p.descripcion ?? p.titulo}</p>
              <div className="mm">
                {p.precio != null && <span style={{ color: "var(--neon)", fontWeight: 700 }}>{precioFmt(p.precio, p.moneda)}</span>}
                {p.tiktok_url && <span>🎬 TikTok adjunto</span>}
                <span>🕒 {new Date(p.created_at).toLocaleString("es-BO")}</span>
              </div>
            </div>
            <div className="mod-actions">
              <button className="mbtn approve" title="Aprobar" onClick={() => act(p.id, "aprobado")}><Check style={{ width: 18, height: 18 }} /></button>
              <button className="mbtn edit" title="Solicitar cambios" onClick={() => act(p.id, "cambios")}><Edit style={{ width: 18, height: 18 }} /></button>
              <button className="mbtn reject" title="Rechazar" onClick={() => act(p.id, "rechazado")}><X style={{ width: 18, height: 18 }} /></button>
            </div>
          </div>
        ))}
      </div>
      )}
    </div>
  );
}

// ── Tab Suscripciones ─────────────────────────────────────────────────────────

const ESTADO_CFG: Record<EstadoSuscripcion, { label: string; color: string }> = {
  activo:     { label: "Activo",       color: "var(--neon)" },
  por_vencer: { label: "Por vencer",   color: "var(--amber)" },
  vencido:    { label: "Vencido",      color: "var(--pink)" },
  suspendido: { label: "Suspendido",   color: "#888" },
  sin_plan:   { label: "Sin plan",     color: "var(--txt-3)" },
};

function TabSuscripciones({
  items, onSuspender, onActivar, onPago,
}: {
  items: ComercioSuscripcion[];
  onSuspender: (id: string) => void;
  onActivar: (id: string) => void;
  onPago: () => void;
}) {
  const [filtro, setFiltro] = useState<EstadoSuscripcion | "todos">("todos");
  const [pagandoId, setPagandoId] = useState<string | null>(null);

  const conteo = (e: EstadoSuscripcion) => items.filter((c) => c.suscripcion_estado === e).length;
  const visibles = filtro === "todos" ? items : items.filter((c) => c.suscripcion_estado === filtro);

  return (
    <div className="panel-card glass">
      <div className="ph">
        <h3>Suscripciones</h3>
        <span style={{ color: "var(--txt-3)", fontSize: 13 }}>Gestión de pagos y estado de cada negocio</span>
      </div>

      {/* Contadores */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
        {(["todos", "activo", "por_vencer", "vencido", "suspendido", "sin_plan"] as const).map((e) => {
          const n = e === "todos" ? items.length : conteo(e as EstadoSuscripcion);
          const cfg = e === "todos" ? { label: "Todos", color: "var(--txt-2)" } : ESTADO_CFG[e as EstadoSuscripcion];
          return (
            <button key={e} onClick={() => setFiltro(e)}
              style={{ padding: "6px 14px", borderRadius: 20, border: "1px solid", cursor: "pointer",
                borderColor: filtro === e ? cfg.color : "var(--border)",
                background: filtro === e ? `${cfg.color}22` : "transparent",
                color: cfg.color, fontSize: 13, fontWeight: filtro === e ? 600 : 400 }}>
              {cfg.label} <span style={{ opacity: 0.7 }}>({n})</span>
            </button>
          );
        })}
      </div>

      {/* Lista */}
      {visibles.length === 0 && (
        <div style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>Sin resultados.</div>
      )}
      {visibles.map((c) => {
        const cfg = ESTADO_CFG[c.suscripcion_estado];
        return (
          <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 16px", borderBottom: "1px solid var(--border)" }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: 15 }}>{c.nombre}</div>
              <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 2 }}>
                +{c.whatsapp} · {c.verificado ? "✓ verificado" : "sin verificar"}
              </div>
              <div style={{ fontSize: 12, marginTop: 4 }}>
                <span style={{ color: cfg.color, fontWeight: 600 }}>{cfg.label}</span>
                {c.paga_hasta && (
                  <span style={{ color: "var(--txt-3)", marginLeft: 8 }}>
                    · vence {new Date(c.paga_hasta + "T12:00:00").toLocaleDateString("es-BO")}
                  </span>
                )}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
              <button className="btn btn-ghost btn-sm" onClick={() => setPagandoId(c.id)}>
                + Pago
              </button>
              {c.suspendido ? (
                <button className="mbtn approve" title="Reactivar" onClick={() => onActivar(c.id)}>
                  <Check style={{ width: 16, height: 16 }} />
                </button>
              ) : (
                <button className="mbtn reject" title="Suspender" onClick={() => onSuspender(c.id)}>
                  <X style={{ width: 16, height: 16 }} />
                </button>
              )}
            </div>
          </div>
        );
      })}

      {/* Modal registro de pago */}
      {pagandoId && (
        <ModalPago
          comercio={items.find((c) => c.id === pagandoId)!}
          onClose={() => setPagandoId(null)}
          onDone={() => { setPagandoId(null); onPago(); }}
        />
      )}
    </div>
  );
}

// ── Tab Comercios ─────────────────────────────────────────────────────────────

type FiltroComercio = "todos" | "pendientes" | "verificados";

function TabComercios({
  todos, pendientes, rubros, onVerificar, onRechazar, onEdited,
}: {
  todos: ComercioPorVerificar[];
  pendientes: ComercioPorVerificar[];
  rubros: Rubro[];
  onVerificar: (id: string) => void;
  onRechazar: (id: string) => void;
  onEdited: () => void;
}) {
  const [filtro, setFiltro] = useState<FiltroComercio>("todos");
  const [editandoId, setEditandoId] = useState<string | null>(null);

  const visibles = filtro === "todos"
    ? todos
    : filtro === "pendientes"
    ? todos.filter((c) => !c.verificado)
    : todos.filter((c) => c.verificado);

  const editando = editandoId ? todos.find((c) => c.id === editandoId) ?? null : null;

  return (
    <div className="panel-card glass">
      <div className="ph">
        <h3>Negocios</h3>
        <span style={{ color: "var(--txt-3)", fontSize: 13 }}>Listado completo · click para editar</span>
      </div>

      {/* Filtros */}
      <div style={{ display: "flex", gap: 8, padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
        {(["todos", "pendientes", "verificados"] as FiltroComercio[]).map((f) => {
          const n = f === "todos" ? todos.length : f === "pendientes" ? pendientes.length : todos.filter((c) => c.verificado).length;
          return (
            <button key={f} onClick={() => setFiltro(f)}
              style={{ padding: "5px 14px", borderRadius: 20, border: "1px solid", cursor: "pointer", fontSize: 13,
                borderColor: filtro === f ? "var(--neon)" : "var(--border)",
                background: filtro === f ? "var(--neon)22" : "transparent",
                color: filtro === f ? "var(--neon)" : "var(--txt-2)", fontWeight: filtro === f ? 600 : 400 }}>
              {f.charAt(0).toUpperCase() + f.slice(1)} ({n})
            </button>
          );
        })}
      </div>

      {visibles.length === 0 && (
        <div style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>Sin resultados.</div>
      )}

      {visibles.map((c) => (
        <div key={c.id} style={{ display: "flex", gap: 12, padding: "14px 16px", borderBottom: "1px solid var(--border)", alignItems: "flex-start" }}>
          {/* Foto */}
          <img
            src={c.portada_url ?? "https://picsum.photos/seed/" + c.id + "/80/80"}
            alt=""
            style={{ width: 64, height: 64, objectFit: "cover", borderRadius: 10, flexShrink: 0 }}
          />

          {/* Info */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <span style={{ fontWeight: 600, fontSize: 15 }}>{c.nombre}</span>
              {c.verificado
                ? <span style={{ fontSize: 11, color: "var(--neon)", background: "var(--neon)22", padding: "2px 8px", borderRadius: 10 }}>✓ verificado</span>
                : <span style={{ fontSize: 11, color: "var(--amber)", background: "var(--amber)22", padding: "2px 8px", borderRadius: 10 }}>pendiente</span>}
              {c.suspendido && <span style={{ fontSize: 11, color: "#888", background: "#88888822", padding: "2px 8px", borderRadius: 10 }}>suspendido</span>}
            </div>
            <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 3 }}>
              {(c.rubros as { nombre: string } | undefined)?.nombre ?? "Sin rubro"}
              {(c.ciudades as { nombre: string } | undefined)?.nombre ? ` · ${(c.ciudades as { nombre: string }).nombre}` : ""}
              {c.modalidad ? ` · ${MODALIDAD_LABEL[c.modalidad] ?? c.modalidad}` : ""}
            </div>
            {c.descripcion && (
              <div style={{ fontSize: 12, color: "var(--txt-2)", marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 400 }}>
                {c.descripcion}
              </div>
            )}
          </div>

          {/* Acciones */}
          <div style={{ display: "flex", gap: 8, flexShrink: 0, alignItems: "center" }}>
            <a
              href={`https://wa.me/${c.whatsapp}`}
              target="_blank" rel="noopener"
              className="mbtn"
              title={`WhatsApp +${c.whatsapp}`}
              style={{ display: "flex", alignItems: "center", justifyContent: "center" }}
            >
              <WhatsApp style={{ width: 16, height: 16 }} />
            </a>
            {c.lat != null && (
              <a
                href={comoLlegarHref(c)}
                target="_blank" rel="noopener"
                className="mbtn"
                title="Ver en mapa"
                style={{ display: "flex", alignItems: "center", justifyContent: "center" }}
              >
                <Pin style={{ width: 16, height: 16 }} />
              </a>
            )}
            <button className="mbtn edit" title="Editar" onClick={() => setEditandoId(c.id)}>
              <Edit style={{ width: 16, height: 16 }} />
            </button>
            {!c.verificado && (
              <>
                <button className="mbtn approve" title="Verificar" onClick={() => onVerificar(c.id)}>
                  <Verified style={{ width: 16, height: 16 }} />
                </button>
                <button className="mbtn reject" title="Rechazar" onClick={() => onRechazar(c.id)}>
                  <X style={{ width: 16, height: 16 }} />
                </button>
              </>
            )}
          </div>
        </div>
      ))}

      {editando && (
        <ModalEditar
          comercio={editando}
          rubros={rubros}
          onClose={() => setEditandoId(null)}
          onDone={() => { setEditandoId(null); onEdited(); }}
        />
      )}
    </div>
  );
}

function ModalEditar({
  comercio, rubros, onClose, onDone,
}: {
  comercio: ComercioPorVerificar;
  rubros: Rubro[];
  onClose: () => void;
  onDone: () => void;
}) {
  const [nombre, setNombre] = useState(comercio.nombre);
  const [whatsapp, setWhatsapp] = useState(comercio.whatsapp);
  const [descripcion, setDescripcion] = useState(comercio.descripcion ?? "");
  const [modalidad, setModalidad] = useState(comercio.modalidad ?? "local");
  const [direccion, setDireccion] = useState(comercio.direccion ?? "");
  const [horario, setHorario] = useState((comercio as Record<string, unknown>).horario as string ?? "");
  const [rubroSlug, setRubroSlug] = useState((comercio.rubros as { slug: string } | undefined)?.slug ?? "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErr("");
    try {
      await editarComercio(comercio.id, {
        nombre: nombre || undefined,
        whatsapp: whatsapp || undefined,
        descripcion: descripcion || undefined,
        modalidad: modalidad || undefined,
        direccion: direccion || undefined,
        horario: horario || undefined,
        rubro_slugs: rubroSlug ? [rubroSlug] : undefined,
      });
      onDone();
    } catch {
      setErr("No se pudo guardar. Verificá el backend.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
      <div className="glass" style={{ width: "100%", maxWidth: 480, borderRadius: 16, padding: 24, maxHeight: "90vh", overflowY: "auto" }}>
        <h3 style={{ marginBottom: 18 }}>Editar negocio</h3>
        <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <label style={{ fontSize: 12, color: "var(--txt-3)" }}>Nombre
            <input className="adm-input" style={{ marginTop: 4 }} value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre del negocio" />
          </label>
          <label style={{ fontSize: 12, color: "var(--txt-3)" }}>WhatsApp
            <input className="adm-input" style={{ marginTop: 4 }} value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)} placeholder="591XXXXXXXX" />
          </label>
          <label style={{ fontSize: 12, color: "var(--txt-3)" }}>Descripción / reseña
            <textarea className="adm-input" style={{ marginTop: 4, minHeight: 70, resize: "vertical" }} value={descripcion} onChange={(e) => setDescripcion(e.target.value)} placeholder="Qué vende o qué ofrece…" />
          </label>
          <label style={{ fontSize: 12, color: "var(--txt-3)" }}>Rubro
            <select className="adm-input" style={{ marginTop: 4 }} value={rubroSlug} onChange={(e) => setRubroSlug(e.target.value)}>
              <option value="">— sin cambiar —</option>
              {rubros.map((r) => <option key={r.slug} value={r.slug}>{r.nombre}</option>)}
            </select>
          </label>
          <label style={{ fontSize: 12, color: "var(--txt-3)" }}>Modalidad
            <select className="adm-input" style={{ marginTop: 4 }} value={modalidad} onChange={(e) => setModalidad(e.target.value)}>
              <option value="local">Local</option>
              <option value="mayorista">Mayorista</option>
              <option value="delivery">Delivery</option>
              <option value="online">Online</option>
              <option value="mixto">Mixto</option>
            </select>
          </label>
          <label style={{ fontSize: 12, color: "var(--txt-3)" }}>Dirección
            <input className="adm-input" style={{ marginTop: 4 }} value={direccion} onChange={(e) => setDireccion(e.target.value)} placeholder="Calle, número, referencia" />
          </label>
          <label style={{ fontSize: 12, color: "var(--txt-3)" }}>Horario
            <input className="adm-input" style={{ marginTop: 4 }} value={horario} onChange={(e) => setHorario(e.target.value)} placeholder="Lun-Sáb 9-20 · Dom 10-14" />
          </label>
          {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
          <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
            <button type="button" className="btn btn-ghost" style={{ flex: 1 }} onClick={onClose}>Cancelar</button>
            <button type="submit" className="btn btn-primary" style={{ flex: 2 }} disabled={saving}>
              {saving ? "Guardando…" : "Guardar cambios"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Modal Pago ────────────────────────────────────────────────────────────────

function ModalPago({ comercio, onClose, onDone }: { comercio: ComercioSuscripcion; onClose: () => void; onDone: () => void }) {
  const [monto, setMonto] = useState("100");
  const [moneda, setMoneda] = useState("BOB");
  const [metodo, setMetodo] = useState("qr-bolivia");
  const [meses, setMeses] = useState("1");
  const [referencia, setReferencia] = useState("");
  const [notas, setNotas] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    if (!monto || isNaN(Number(monto))) { setErr("Ingresá un monto válido"); return; }
    setSaving(true);
    try {
      await registrarPago(comercio.id, {
        monto: Number(monto), moneda, metodo, meses: Number(meses),
        referencia: referencia || undefined, notas: notas || undefined,
      });
      onDone();
    } catch {
      setErr("No se pudo registrar el pago. Verificá el backend.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
      <div className="glass" style={{ width: "100%", maxWidth: 420, borderRadius: 16, padding: 24 }}>
        <h3 style={{ marginBottom: 4 }}>Registrar pago</h3>
        <p style={{ color: "var(--txt-3)", fontSize: 13, marginBottom: 18 }}>{comercio.nombre}</p>
        <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", gap: 10 }}>
            <input className="adm-input" style={{ flex: 2 }} type="number" value={monto} onChange={(e) => setMonto(e.target.value)} placeholder="Monto" />
            <select className="adm-input" style={{ flex: 1 }} value={moneda} onChange={(e) => setMoneda(e.target.value)}>
              <option value="BOB">BOB</option>
              <option value="ARS">ARS</option>
              <option value="USD">USD</option>
            </select>
          </div>
          <select className="adm-input" value={metodo} onChange={(e) => setMetodo(e.target.value)}>
            <option value="qr-bolivia">QR Bolivia</option>
            <option value="efectivo">Efectivo</option>
            <option value="transferencia">Transferencia</option>
          </select>
          <select className="adm-input" value={meses} onChange={(e) => setMeses(e.target.value)}>
            <option value="1">1 mes</option>
            <option value="3">3 meses</option>
            <option value="6">6 meses</option>
            <option value="12">12 meses</option>
          </select>
          <input className="adm-input" value={referencia} onChange={(e) => setReferencia(e.target.value)} placeholder="N° comprobante / referencia (opcional)" />
          <input className="adm-input" value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Notas (opcional)" />
          {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
          <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
            <button type="button" className="btn btn-ghost" style={{ flex: 1 }} onClick={onClose}>Cancelar</button>
            <button type="submit" className="btn btn-primary" style={{ flex: 2 }} disabled={saving}>
              {saving ? "Guardando…" : "Confirmar pago"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
