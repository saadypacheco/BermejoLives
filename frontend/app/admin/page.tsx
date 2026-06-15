"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listPendientes, moderar, login, getToken, type PendingPub,
  listComerciosPorVerificar, verificarComercio, rechazarComercio, type ComercioPorVerificar,
  listSuscripciones, registrarPago, suspenderComercio, activarComercio, type ComercioSuscripcion, type EstadoSuscripcion,
} from "@/lib/api";
import { precioFmt, MODALIDAD_LABEL, comoLlegarHref } from "@/lib/types";
import { Check, X, Edit, Pin, WhatsApp, Verified } from "@/components/icons";

export default function AdminPage() {
  const [authed, setAuthed] = useState(false);
  const [email, setEmail] = useState("admin@bermejolive.com");
  const [pass, setPass] = useState("");
  const [err, setErr] = useState("");
  const [tab, setTab] = useState<"publicaciones" | "comercios" | "suscripciones">("publicaciones");
  const [items, setItems] = useState<PendingPub[]>([]);
  const [comercios, setComercios] = useState<ComercioPorVerificar[]>([]);
  const [suscripciones, setSuscripciones] = useState<ComercioSuscripcion[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getToken()) {
      setAuthed(true);
      load();
      loadComercios();
      loadSuscripciones();
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
    try { setComercios(await listComerciosPorVerificar()); } catch { setComercios([]); }
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
        <button className={tab === "publicaciones" ? "active" : ""} onClick={() => setTab("publicaciones")}>
          Publicaciones {items.length > 0 && `(${items.length})`}
        </button>
        <button className={tab === "comercios" ? "active" : ""} onClick={() => setTab("comercios")}>
          Comercios {comercios.length > 0 && `(${comercios.length})`}
        </button>
        <button className={tab === "suscripciones" ? "active" : ""} onClick={() => { setTab("suscripciones"); loadSuscripciones(); }}>
          Suscripciones {suscripciones.filter((c) => ["por_vencer","vencido","suspendido"].includes(c.suscripcion_estado)).length > 0 && `⚠️`}
        </button>
      </div>

      {tab === "comercios" && (
        <div className="panel-card glass">
          <div className="ph"><h3>Comercios del recorrido</h3><span style={{ color: "var(--txt-3)", fontSize: 13 }}>Verificá o rechazá las altas del agente de campo</span></div>
          {comercios.length === 0 && (
            <div className="mod-item" style={{ justifyContent: "center", color: "var(--txt-3)" }}>
              No hay comercios pendientes de verificar.
            </div>
          )}
          {comercios.map((c) => (
            <div className="mod-item" key={c.id}>
              <img src={c.portada_url ?? "https://picsum.photos/seed/loc/240/168"} alt="" />
              <div>
                <h4>{c.nombre} · <span style={{ color: "var(--blue-soft)" }}>{MODALIDAD_LABEL[c.modalidad] ?? c.modalidad}</span></h4>
                <p>{c.rubros?.nombre ?? "Sin rubro"}{c.direccion ? ` · ${c.direccion}` : ""}</p>
                <div className="mm">
                  <span><WhatsApp style={{ width: 13, height: 13, display: "inline", verticalAlign: "-2px" }} /> +{c.whatsapp}</span>
                  {c.lat != null ? (
                    <a href={comoLlegarHref(c)} target="_blank" rel="noopener" style={{ color: "var(--neon)" }}><Pin style={{ width: 13, height: 13, display: "inline", verticalAlign: "-2px" }} /> ubicación ✓</a>
                  ) : <span style={{ color: "var(--amber)" }}>sin GPS</span>}
                  <span>🕒 {new Date(c.created_at).toLocaleString("es-BO")}</span>
                </div>
              </div>
              <div className="mod-actions">
                <button className="mbtn approve" title="Verificar" onClick={() => actComercio(c.id, "verificar")}><Verified style={{ width: 18, height: 18 }} /></button>
                <button className="mbtn reject" title="Rechazar (desactivar)" onClick={() => actComercio(c.id, "rechazar")}><X style={{ width: 18, height: 18 }} /></button>
              </div>
            </div>
          ))}
        </div>
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
