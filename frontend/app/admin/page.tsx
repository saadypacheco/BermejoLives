"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import {
  listPendientes, moderar, revisarConIA, type VeredictoIA, login, getToken, type PendingPub,
  listComerciosPorVerificar, listTodosComercios, verificarComercio, rechazarComercio,
  editarComercio, type ComercioPorVerificar,
  listSuscripciones, registrarPago, suspenderComercio, activarComercio,
  setConfiable as setConfiable_, listarNumeros, agregarNumero, type NumeroComercio,
  listarGrupos, atarGrupo, soltarGrupo, crearGrupoComercio, type GrupoComercio,
  altasPorDia, type AltasDia,
  rubrosDeComercio, editarRubrosComercio,
  adminListarFotos, adminSubirFoto, adminBorrarFoto, type FotoComercio,
  analizarComercio, type AnalisisIA,
  pendientesAnalisis, analizarTanda, type ResultadoTanda,
  type ComercioSuscripcion, type EstadoSuscripcion,
  listPagosPendientes, confirmarPago, type PagoPendiente,
  enviarMensajeComercio,
  getEstadisticas, type EstadisticasAdmin,
  getKpis, type Kpis,
  getPesoFotos, optimizarFotos, type PesoFotos, type ResultadoOptimizar,
  getVencimientos,
  listReclamos, responderReclamo, type Reclamo,
  getReservaloResumen, type ReservaloResumen,
  getReservaloConsultas, responderReservaloConsulta, type ConsultaReservalo,
  listSolicitudesCambioNumero, aprobarSolicitudCambioNumero, rechazarSolicitudCambioNumero, type SolicitudCambioNumero,
} from "@/lib/api";
import { getRubros } from "@/lib/data";
import { AdminMap } from "@/components/admin-map";
import { LugaresEditor } from "@/components/lugares-editor";
import { AdornosEditor } from "@/components/adornos-editor";
import { ImportadosPanel } from "@/components/importados-panel";
import { VencimientosPanel } from "@/components/vencimientos-panel";
import { CatalogoPanel } from "@/components/catalogo-panel";
import { ImageLightbox } from "@/components/image-lightbox";
import type { Rubro } from "@/lib/types";
import { precioFmt, MODALIDAD_LABEL, comoLlegarHref } from "@/lib/types";
import { abiertoAhora } from "@/lib/horario";
import { Check, X, Edit, Pin, WhatsApp, Verified } from "@/components/icons";

export default function AdminPage() {
  const [authed, setAuthed] = useState(false);
  const [email, setEmail] = useState("admin@bermejolive.com");
  const [pass, setPass] = useState("");
  const [err, setErr] = useState("");
  const [tab, setTab] = useState<"publicaciones" | "comercios" | "lugares" | "adornos" | "catalogo" | "importados" | "suscripciones" | "pagos" | "monitoreo" | "kpis" | "reclamos" | "cambio-numero" | "vencimientos">("comercios");
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [items, setItems] = useState<PendingPub[]>([]);
  const [comercios, setComercios] = useState<ComercioPorVerificar[]>([]);
  const [todosLosComercios, setTodosLosComercios] = useState<ComercioPorVerificar[]>([]);
  const [rubros, setRubros] = useState<Rubro[]>([]);
  // Se carga al ABRIR el panel, no al entrar a la pestaña. Un aviso que sólo
  // aparece cuando ya fuiste a mirar no avisa nada.
  const [alertasVenc, setAlertasVenc] = useState(0);
  const [suscripciones, setSuscripciones] = useState<ComercioSuscripcion[]>([]);
  const [pagosPendientes, setPagosPendientes] = useState<PagoPendiente[]>([]);
  const [estadisticas, setEstadisticas] = useState<EstadisticasAdmin | null>(null);
  const [reservaloResumen, setReservaloResumen] = useState<ReservaloResumen | null>(null);
  const [reclamos, setReclamos] = useState<Reclamo[]>([]);
  const [consultasReservalo, setConsultasReservalo] = useState<ConsultaReservalo[]>([]);
  const [solicitudesCambioNumero, setSolicitudesCambioNumero] = useState<SolicitudCambioNumero[]>([]);
  const [loading, setLoading] = useState(false);
  const [veredictos, setVeredictos] = useState<Record<string, VeredictoIA | "cargando">>({});

  useEffect(() => {
    if (getToken()) {
      setAuthed(true);
      load();
      loadComercios();
      loadSuscripciones();
      loadPagos();
      loadEstadisticas();
      loadReclamos();
      loadSolicitudesCambioNumero();
      getRubros().then(setRubros);
      getVencimientos().then((v) => setAlertasVenc(v.alertas)).catch(() => {});
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

  async function loadPagos() {
    try { setPagosPendientes(await listPagosPendientes()); } catch { setPagosPendientes([]); }
  }

  async function loadEstadisticas() {
    try { setEstadisticas(await getEstadisticas()); } catch { setEstadisticas(null); }
    try { setReservaloResumen(await getReservaloResumen()); } catch { setReservaloResumen(null); }
  }

  async function loadKpis() {
    try { setKpis(await getKpis()); } catch { setKpis(null); }
  }

  async function loadReclamos() {
    try { setReclamos(await listReclamos()); } catch { setReclamos([]); }
    try { setConsultasReservalo(await getReservaloConsultas()); } catch { setConsultasReservalo([]); }
  }

  async function doConfirmarPago(pagoId: string, meses: number) {
    setPagosPendientes((prev) => prev.filter((p) => p.id !== pagoId)); // optimista
    try { await confirmarPago(pagoId, meses); loadSuscripciones(); } catch { loadPagos(); }
  }

  async function doResponderReclamo(id: string, respuesta: string) {
    try { await responderReclamo(id, respuesta); loadReclamos(); } catch { alert("No se pudo responder"); }
  }

  async function loadSolicitudesCambioNumero() {
    try { setSolicitudesCambioNumero(await listSolicitudesCambioNumero()); } catch { setSolicitudesCambioNumero([]); }
  }

  async function doAprobarSolicitud(id: string) {
    try { await aprobarSolicitudCambioNumero(id); loadSolicitudesCambioNumero(); } catch { alert("No se pudo aprobar"); }
  }

  async function doRechazarSolicitud(id: string) {
    try { await rechazarSolicitudCambioNumero(id); loadSolicitudesCambioNumero(); } catch { alert("No se pudo rechazar"); }
  }

  async function doResponderConsultaReservalo(id: number, respuesta: string) {
    try { await responderReservaloConsulta(id, respuesta); loadReclamos(); } catch { alert("No se pudo responder"); }
  }

  async function actComercio(id: string, accion: "verificar" | "rechazar") {
    // La lista que se ve en pantalla se pinta desde `todosLosComercios`, NO desde
    // `comercios` (que son sólo los pendientes, y hoy alimenta el contador del tab).
    // Actualizar una sola era el bug: el backend guardaba el cambio pero la tarjeta
    // seguía ahí, así que el botón parecía no hacer nada.
    setComercios((prev) => prev.filter((c) => c.id !== id));
    setTodosLosComercios((prev) => accion === "rechazar"
      // rechazar = activo:false en la BD, y el listado trae sólo activos → desaparece
      ? prev.filter((c) => c.id !== id)
      // verificar = el negocio sigue en la lista, cambia de estado (mueve los chips)
      : prev.map((c) => (c.id === id ? { ...c, verificado: true } : c)));
    try {
      accion === "verificar" ? await verificarComercio(id) : await rechazarComercio(id);
    } catch {
      loadComercios();   // falló el server: volvemos a la verdad de la BD
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
      loadPagos();
      loadEstadisticas();
      loadReclamos();
      loadSolicitudesCambioNumero();
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

  // La IA sugiere; el moderador confirma con los botones. Nunca aprueba sola.
  async function revisarIA(p: PendingPub) {
    setVeredictos((v) => ({ ...v, [p.id]: "cargando" }));
    try {
      const r = await revisarConIA(p.id, p.titulo ?? "", p.descripcion);
      setVeredictos((v) => ({ ...v, [p.id]: r }));
    } catch {
      setVeredictos((v) => ({ ...v, [p.id]: { veredicto: "dudoso", motivo: "No se pudo consultar la IA.", confianza: 0 } }));
    }
  }

  // Revisa con IA toda la cola y aprueba automáticamente solo lo que la IA marca
  // "aprobar" con confianza alta; el resto queda para revisión humana.
  async function revisarTodoIA() {
    const pendientes = [...items];
    for (const p of pendientes) {
      const r = await revisarConIA(p.id, p.titulo ?? "", p.descripcion).catch(() => null);
      if (r) setVeredictos((v) => ({ ...v, [p.id]: r }));
      if (r && r.veredicto === "aprobar" && r.confianza >= 0.8) {
        setItems((prev) => prev.filter((x) => x.id !== p.id));
        await moderar(p.id, "aprobado").catch(() => {});
      }
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
          <input className="adm-input" type="email" inputMode="email" autoCapitalize="none"
                 autoCorrect="off" spellCheck={false} autoComplete="username"
                 value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
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

      <div className="admin-tabs">
        <button className={tab === "comercios" ? "active" : ""} onClick={() => setTab("comercios")}>
          Negocios <span className="badge">{todosLosComercios.length}</span>
          {comercios.length > 0 && <span className="badge alerta">{comercios.length} pend.</span>}
        </button>
        <button className={tab === "lugares" ? "active" : ""} onClick={() => setTab("lugares")}>
          Lugares
        </button>
        <button className={tab === "catalogo" ? "active" : ""} onClick={() => setTab("catalogo")}>
          Catálogo
        </button>
        <button className={tab === "importados" ? "active" : ""} onClick={() => setTab("importados")}>
          Importados
        </button>
        <button className={tab === "adornos" ? "active" : ""} onClick={() => setTab("adornos")}>
          Adornos
        </button>
        <button className={tab === "publicaciones" ? "active" : ""} onClick={() => setTab("publicaciones")}>
          Publicaciones {items.length > 0 && <span className="badge">{items.length}</span>}
        </button>
        <button className={tab === "suscripciones" ? "active" : ""} onClick={() => { setTab("suscripciones"); loadSuscripciones(); }}>
          Suscripciones {(() => {
            const n = suscripciones.filter((c) => ["por_vencer", "vencido", "suspendido"].includes(c.suscripcion_estado)).length;
            return n > 0 && <span className="badge alerta">{n}</span>;
          })()}
        </button>
        <button className={tab === "pagos" ? "active" : ""} onClick={() => { setTab("pagos"); loadPagos(); }}>
          Pagos {pagosPendientes.length > 0 && <span className="badge alerta">{pagosPendientes.length}</span>}
        </button>
        <button className={tab === "monitoreo" ? "active" : ""} onClick={() => { setTab("monitoreo"); loadEstadisticas(); }}>
          Monitoreo {estadisticas && (estadisticas.alertas.vencido + estadisticas.alertas.suspendido) > 0 && (
            <span className="badge grave">{estadisticas.alertas.vencido + estadisticas.alertas.suspendido}</span>
          )}
        </button>
        <button className={tab === "kpis" ? "active" : ""} onClick={() => { setTab("kpis"); loadKpis(); }}>KPIs</button>
        <button className={tab === "reclamos" ? "active" : ""} onClick={() => { setTab("reclamos"); loadReclamos(); }}>
          Reclamos {(() => {
            const n = reclamos.filter((r) => r.estado === "pendiente").length + consultasReservalo.filter((c) => c.estado === "pendiente").length;
            return n > 0 && <span className="badge alerta">{n}</span>;
          })()}
        </button>
        {/* Vencimientos va ÚLTIMA en la fila pero su número se calcula al abrir
            el panel: si el dominio vence en tres días, tiene que verse sin que
            nadie entre acá a buscarlo. */}
        <button className={tab === "vencimientos" ? "active" : ""} onClick={() => setTab("vencimientos")}>
          Vencimientos {alertasVenc > 0 && <span className="badge grave">{alertasVenc}</span>}
        </button>
        <button className={tab === "cambio-numero" ? "active" : ""} onClick={() => { setTab("cambio-numero"); loadSolicitudesCambioNumero(); }}>
          Cambios de número {solicitudesCambioNumero.length > 0 && <span className="badge alerta">{solicitudesCambioNumero.length}</span>}
        </button>
      </div>

      {tab === "lugares" && <LugaresEditor />}
      {tab === "adornos" && <AdornosEditor />}
      {tab === "catalogo" && <CatalogoPanel />}
      {tab === "importados" && <ImportadosPanel rubros={rubros} />}

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

      {tab === "pagos" && <TabPagos items={pagosPendientes} onConfirmar={doConfirmarPago} />}

      {tab === "monitoreo" && <TabMonitoreo data={estadisticas} reservalo={reservaloResumen} comercios={todosLosComercios} />}
      {tab === "kpis" && <TabKpis data={kpis} />}
      {tab === "vencimientos" && <VencimientosPanel />}

      {tab === "reclamos" && (
        <TabReclamos
          reclamos={reclamos}
          consultasReservalo={consultasReservalo}
          onResponderReclamo={doResponderReclamo}
          onResponderConsulta={doResponderConsultaReservalo}
        />
      )}

      {tab === "cambio-numero" && (
        <TabCambioNumero items={solicitudesCambioNumero} onAprobar={doAprobarSolicitud} onRechazar={doRechazarSolicitud} />
      )}

      {tab === "publicaciones" && (
      <div className="panel-card glass">
        <div className="ph" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
          <div><h3>Cola de aprobación</h3><span style={{ color: "var(--txt-3)", fontSize: 13 }}>Aprobá, rechazá o pedí cambios</span></div>
          {items.length > 0 && (
            <button className="btn btn-ghost btn-sm" onClick={revisarTodoIA} title="La IA revisa todas y aprueba automáticamente solo las de alta confianza; el resto queda para vos.">
              ✨ Revisar todas con IA
            </button>
          )}
        </div>
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
                <IdentidadBadge pub={p} />
              </div>
              {(() => {
                const v = veredictos[p.id];
                if (!v) return null;
                if (v === "cargando") return <div style={{ marginTop: 8, fontSize: 12, color: "var(--txt-3)" }}>✨ Consultando IA…</div>;
                const color = v.veredicto === "aprobar" ? "var(--neon)" : v.veredicto === "rechazar" ? "var(--pink)" : "var(--amber)";
                const label = v.veredicto === "aprobar" ? "✓ IA sugiere aprobar" : v.veredicto === "rechazar" ? "✕ IA sugiere rechazar" : "? IA: revisión humana";
                return (
                  <div style={{ marginTop: 8, fontSize: 12, color, border: `1px solid ${color}`, borderRadius: 8, padding: "4px 8px", display: "inline-block" }}>
                    <b>{label}</b>{v.confianza > 0 && <span style={{ opacity: 0.7 }}> · {Math.round(v.confianza * 100)}%</span>}
                    {v.motivo && <span style={{ display: "block", color: "var(--txt-3)", marginTop: 2 }}>{v.motivo}</span>}
                  </div>
                );
              })()}
            </div>
            <div className="mod-actions">
              <button className="mbtn" title="Revisar con IA" onClick={() => revisarIA(p)} disabled={veredictos[p.id] === "cargando"} style={{ fontSize: 16 }}>✨</button>
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

/** De dónde salió la atribución de una publicación entrante.
 *
 * Importa al aprobar: si vino por código, el mensaje llegó de un número que no
 * estaba asociado al comercio y se identificó con el papel que quedó en el
 * local. Cualquiera que vea ese papel puede publicar, así que conviene mirarlo
 * antes de aprobar — el backend además revalida el código y devuelve 409 si dejó
 * de coincidir. */
function IdentidadBadge({ pub }: { pub: PendingPub }) {
  if (pub.identidad_origen === "codigo") {
    return (
      <span style={{ color: "var(--amber)" }} title="El número no estaba asociado: se identificó con el código del local">
        🔑 por código {pub.codigo_recibido ? `URUKU-${pub.codigo_recibido}` : ""}
      </span>
    );
  }
  if (pub.identidad_origen === "desconocido") {
    return <span style={{ color: "var(--pink)" }} title="Ni número conocido ni código: se creó un comercio borrador">⚠️ sin identificar</span>;
  }
  return null;  // 'numero' es el caso normal, no merece ruido visual
}

// ── Tab Reclamos ──────────────────────────────────────────────────────────────

function ReclamoRow({ nombre, contacto, sub, mensaje, estado, respuesta, onResponder }: {
  nombre: string; contacto: string | null; sub?: string; mensaje: string;
  estado: string; respuesta: string | null; onResponder: (respuesta: string) => void;
}) {
  const [respondiendo, setRespondiendo] = useState(false);
  const [texto, setTexto] = useState("");

  return (
    <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--border)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
        <div>
          <b>{nombre}</b>{sub && <span style={{ color: "var(--txt-3)", fontSize: 12 }}> · {sub}</span>}
          {contacto && <div style={{ fontSize: 12, color: "var(--txt-3)" }}>{contacto}</div>}
        </div>
        <span style={{ fontSize: 11, color: estado === "pendiente" ? "var(--amber)" : "var(--neon)" }}>
          {estado === "respondido" || estado === "respondida" ? "✓ respondido" : "pendiente"}
        </span>
      </div>
      <p style={{ marginTop: 6, fontSize: 14 }}>{mensaje}</p>
      {respuesta && (
        <div style={{ marginTop: 8, padding: 10, background: "var(--panel)", borderRadius: 8, fontSize: 13 }}>
          <b style={{ color: "var(--neon)" }}>Respuesta:</b> {respuesta}
        </div>
      )}
      {!respuesta && (
        respondiendo ? (
          <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
            <input className="adm-input" style={{ flex: 1 }} value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Tu respuesta…" />
            <button className="btn btn-primary btn-sm" onClick={() => { if (texto.trim()) { onResponder(texto.trim()); setRespondiendo(false); setTexto(""); } }}>Enviar</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setRespondiendo(false)}>Cancelar</button>
          </div>
        ) : (
          <button className="btn btn-ghost btn-sm" style={{ marginTop: 8 }} onClick={() => setRespondiendo(true)}>Responder</button>
        )
      )}
    </div>
  );
}

function TabReclamos({
  reclamos, consultasReservalo, onResponderReclamo, onResponderConsulta,
}: {
  reclamos: Reclamo[];
  consultasReservalo: ConsultaReservalo[];
  onResponderReclamo: (id: string, respuesta: string) => void;
  onResponderConsulta: (id: number, respuesta: string) => void;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="panel-card glass">
        <div className="ph"><h3>Reclamos (URUKU)</h3><span style={{ color: "var(--txt-3)", fontSize: 13 }}>Sobre negocios o la plataforma</span></div>
        {reclamos.length === 0 && <div style={{ padding: 20, textAlign: "center", color: "var(--txt-3)" }}>Sin reclamos.</div>}
        {reclamos.map((r) => (
          <ReclamoRow
            key={r.id}
            nombre={r.nombre ?? "Anónimo"}
            contacto={r.contacto}
            sub={r.comercios?.nombre}
            mensaje={r.mensaje}
            estado={r.estado}
            respuesta={r.respuesta}
            onResponder={(resp) => onResponderReclamo(r.id, resp)}
          />
        ))}
      </div>

      <div className="panel-card glass">
        <div className="ph"><h3>Consultas y reclamos (Reservalo)</h3><span style={{ color: "var(--txt-3)", fontSize: 13 }}>Formulario de contacto de la tienda</span></div>
        {consultasReservalo.length === 0 && <div style={{ padding: 20, textAlign: "center", color: "var(--txt-3)" }}>Sin consultas.</div>}
        {consultasReservalo.map((c) => (
          <ReclamoRow
            key={c.id}
            nombre={c.nombre ?? "Anónimo"}
            contacto={c.email}
            sub={c.tipo}
            mensaje={c.mensaje}
            estado={c.estado}
            respuesta={c.respuesta}
            onResponder={(resp) => onResponderConsulta(c.id, resp)}
          />
        ))}
      </div>
    </div>
  );
}

// ── Tab Cambio de número ──────────────────────────────────────────────────────

function TabCambioNumero({
  items, onAprobar, onRechazar,
}: {
  items: SolicitudCambioNumero[];
  onAprobar: (id: string) => void;
  onRechazar: (id: string) => void;
}) {
  return (
    <div className="panel-card glass">
      <div className="ph">
        <h3>Cambios de número</h3>
        <span style={{ color: "var(--txt-3)", fontSize: 13 }}>El dueño perdió su celu viejo — nunca se aprueba solo, siempre revisá vos</span>
      </div>
      {items.length === 0 && <div style={{ padding: 20, textAlign: "center", color: "var(--txt-3)" }}>Sin solicitudes pendientes.</div>}
      {items.map((s) => {
        return (
          <div key={s.id} style={{ padding: 16, borderBottom: "1px solid var(--border)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10 }}>
              <div>
                <b>{s.comercios?.nombre ?? "Comercio"}</b>
                <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 2 }}>
                  Número actual: +{s.comercios?.whatsapp} → nuevo: +{s.whatsapp_nuevo}
                </div>
                {s.lat != null && s.lng != null && (
                  <a href={`https://www.google.com/maps/search/?api=1&query=${s.lat},${s.lng}`} target="_blank" rel="noopener" style={{ fontSize: 12, color: "var(--blue-soft)" }}>
                    📍 Ver ubicación enviada
                  </a>
                )}
                {s.mensaje && <p style={{ fontSize: 13, color: "var(--txt-2)", marginTop: 6 }}>{s.mensaje}</p>}
              </div>
            </div>

            <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: "var(--txt-3)", marginBottom: 4 }}>Foto registrada</div>
                {s.comercios?.portada_url
                  ? <img src={s.comercios.portada_url} alt="" style={{ width: "100%", height: 120, objectFit: "cover", borderRadius: 8 }} />
                  : <div style={{ height: 120, background: "var(--panel)", borderRadius: 8, display: "grid", placeItems: "center", color: "var(--txt-3)", fontSize: 12 }}>sin foto</div>}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: "var(--txt-3)", marginBottom: 4 }}>Foto nueva</div>
                {s.foto_url
                  ? <img src={s.foto_url} alt="" style={{ width: "100%", height: 120, objectFit: "cover", borderRadius: 8 }} />
                  : <div style={{ height: 120, background: "var(--panel)", borderRadius: 8, display: "grid", placeItems: "center", color: "var(--txt-3)", fontSize: 12 }}>sin foto</div>}
              </div>
            </div>

            {s.estado === "pendiente" ? (
              <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
                <button className="btn btn-primary btn-sm" onClick={() => onAprobar(s.id)}>Aprobar</button>
                <button className="btn btn-ghost btn-sm" onClick={() => onRechazar(s.id)}>Rechazar</button>
              </div>
            ) : (
              <div style={{ marginTop: 10, fontSize: 12, color: s.estado === "aprobada" ? "var(--neon)" : "var(--pink)" }}>
                {s.estado === "aprobada" ? "✓ Aprobada" : "✗ Rechazada"}
              </div>
            )}
          </div>
        );
      })}
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

function TabPagos({
  items, onConfirmar,
}: {
  items: PagoPendiente[];
  onConfirmar: (pagoId: string, meses: number) => void;
}) {
  const METODO_LABEL: Record<string, string> = {
    "qr-bolivia": "QR Bolivia", "qr-argentina": "QR Argentina",
    transferencia: "Transferencia", efectivo: "Efectivo",
  };
  return (
    <div className="panel-card glass">
      <div className="ph"><h3>Pagos por confirmar</h3><span style={{ color: "var(--txt-3)", fontSize: 13 }}>Comprobantes que subieron los comercios</span></div>
      {items.length === 0 && (
        <div className="mod-item" style={{ justifyContent: "center", color: "var(--txt-3)" }}>
          No hay pagos pendientes de confirmación.
        </div>
      )}
      {items.map((p) => (
        <div className="mod-item" key={p.id}>
          {p.comprobante_url
            ? <a href={p.comprobante_url} target="_blank" rel="noopener"><img src={p.comprobante_url} alt="comprobante" /></a>
            : <div style={{ width: 120, minWidth: 120, height: 84, display: "grid", placeItems: "center", background: "var(--panel)", borderRadius: 8, color: "var(--txt-3)", fontSize: 12 }}>sin foto</div>}
          <div>
            <h4>{p.comercios?.nombre ?? "Comercio"}</h4>
            <p>
              <b style={{ color: "var(--neon)" }}>{p.moneda} {Number(p.monto).toLocaleString("es-AR")}</b>
              {" · "}{METODO_LABEL[p.metodo] ?? p.metodo}
              {p.referencia && <> · ref: {p.referencia}</>}
            </p>
            <div className="mm"><span>🕒 {new Date(p.created_at).toLocaleString("es-AR")}</span></div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginLeft: "auto" }}>
            <button className="btn btn-primary btn-sm" onClick={() => onConfirmar(p.id, 1)}>Confirmar 1 mes</button>
            <button className="btn btn-ghost btn-sm" onClick={() => onConfirmar(p.id, 2)}>Confirmar 2 meses</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function TabKpis({ data }: { data: Kpis | null }) {
  if (!data) return <p style={{ color: "var(--txt-3)" }}>Cargando KPIs…</p>;
  const m = data.monetizacion;
  const card: React.CSSProperties = { padding: 18, borderRadius: 14, border: "1px solid var(--stroke)", background: "var(--panel)" };
  const Lista = ({ titulo, items, empty }: { titulo: string; items: { query?: string; nombre?: string; slug?: string | null; n?: number; eventos?: number }[]; empty: string }) => (
    <div style={card}>
      <h3 style={{ marginTop: 0, fontSize: 15 }}>{titulo}</h3>
      {items.length === 0 ? <p style={{ color: "var(--txt-3)", fontSize: 13 }}>{empty}</p> : (
        <ol style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 6 }}>
          {items.map((it, i) => (
            <li key={i} style={{ fontSize: 13.5, color: "var(--txt-2)" }}>
              {it.slug ? <Link href={`/comercios/${it.slug}`} style={{ color: "var(--txt)" }}>{it.nombre}</Link> : (it.query ?? it.nombre)}
              <b style={{ color: "var(--neon)", marginLeft: 6 }}>{it.n ?? it.eventos}</b>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Monetización (para el creador del sitio) */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {[["Comercios activos", m.comercios_activos, "var(--txt)"], ["Pagando", m.pagando, "var(--neon)"], ["Gratis", m.gratis, "var(--txt-3)"]].map(([lbl, val, col]) => (
          <div key={lbl as string} style={{ ...card, flex: 1, minWidth: 130 }}>
            <div style={{ fontSize: 12, color: "var(--txt-3)" }}>{lbl as string}</div>
            <div style={{ fontSize: 28, fontWeight: 900, color: col as string }}>{val as number}</div>
          </div>
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 12 }}>
        <Lista titulo="🔎 Más buscado" items={data.top_busquedas} empty="Sin búsquedas todavía." />
        <Lista titulo="🚫 Buscado sin resultado" items={data.sin_resultado} empty="Nada sin resultado 🎉" />
        <Lista titulo="🏪 Locales más visitados" items={data.top_comercios} empty="Sin visitas todavía." />
      </div>
      <p style={{ color: "var(--txt-3)", fontSize: 12 }}>💡 "Buscado sin resultado" = oportunidades: rubros/productos que la gente busca y no están → a quién salir a sumar.</p>
    </div>
  );
}

function TabMonitoreo({
  data, reservalo, comercios,
}: {
  data: EstadisticasAdmin | null;
  reservalo: ReservaloResumen | null;
  comercios: ComercioPorVerificar[];
}) {
  const [altas, setAltas] = useState<AltasDia[]>([]);
  useEffect(() => { altasPorDia(60).then((r) => setAltas(r.items ?? [])).catch(() => {}); }, []);

  if (!data) return <div className="panel-card glass" style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>Cargando…</div>;

  const totalAlertas = data.alertas.vencido + data.alertas.suspendido;
  const nombrePorId = (id: string) => comercios.find((c) => c.id === id)?.nombre ?? "?";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Altas por día. Las columnas se leen de a pares: `altas` contra `con
          WhatsApp` es la diferencia entre un punto en el mapa y un local al que
          se le puede escribir; contra `analizados`, lo que falta pasar por la
          IA. Un total suelto no muestra ninguna de las dos. */}
      {altas.length > 0 && (
        <div className="panel-card glass" style={{ padding: 16 }}>
          <h3 style={{ marginBottom: 4 }}>Altas por día</h3>
          <p style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 12 }}>
            Últimos 60 días · {altas.reduce((a, d) => a + d.altas, 0)} comercios
          </p>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ color: "var(--txt-3)", fontSize: 11, textAlign: "right" }}>
                  <th style={{ textAlign: "left", padding: "4px 8px" }}>Día</th>
                  <th style={{ padding: "4px 8px" }}>Altas</th>
                  <th style={{ padding: "4px 8px" }}>Con nombre</th>
                  <th style={{ padding: "4px 8px" }}>Con foto</th>
                  <th style={{ padding: "4px 8px" }}>Con WhatsApp</th>
                  <th style={{ padding: "4px 8px" }}>Analizados</th>
                  <th style={{ padding: "4px 8px" }}>Agentes</th>
                </tr>
              </thead>
              <tbody>
                {altas.map((d) => {
                  const falta = d.altas - d.con_whatsapp;
                  return (
                    <tr key={d.dia} style={{ borderTop: "1px solid var(--border)", textAlign: "right" }}>
                      <td style={{ textAlign: "left", padding: "6px 8px", whiteSpace: "nowrap" }}>{d.dia}</td>
                      <td style={{ padding: "6px 8px", fontWeight: 700 }}>{d.altas}</td>
                      <td style={{ padding: "6px 8px" }}>{d.con_nombre}</td>
                      <td style={{ padding: "6px 8px" }}>{d.con_foto}</td>
                      {/* Lo que falta se resalta: es el número que decide si la
                          ficha lleva a algún lado o es sólo un punto. */}
                      <td style={{ padding: "6px 8px", color: falta > 0 ? "var(--amber)" : undefined }}>
                        {d.con_whatsapp}{falta > 0 && <span style={{ fontSize: 11 }}> (−{falta})</span>}
                      </td>
                      <td style={{ padding: "6px 8px" }}>{d.analizados}</td>
                      <td style={{ padding: "6px 8px", color: "var(--txt-3)" }}>{d.agentes}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
        <div className="panel-card glass" style={{ padding: 16, borderLeft: "3px solid var(--neon)" }}>
          <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Negocios nuevos (7d)</div>
          <div style={{ fontSize: 26, fontWeight: 700 }}>{data.comercios_nuevos_7d}</div>
          <div style={{ fontSize: 11, color: "var(--txt-3)" }}>{data.comercios_nuevos_30d} en 30 días</div>
        </div>
        <div className="panel-card glass" style={{ padding: 16, borderLeft: "3px solid var(--amber)" }}>
          <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Ofertas activas</div>
          <div style={{ fontSize: 26, fontWeight: 700 }}>{data.ofertas_total}</div>
        </div>
        {/* Lo que la plataforma le lleva al comercio: no las visitas a la
            ficha —que se cuentan solas— sino las veces que alguien salió de
            URUKU hacia el local. Es el número que hay que poder mostrarle al
            comerciante cuando pregunte para qué paga. */}
        <div className="panel-card glass" style={{ padding: 16, borderLeft: "3px solid var(--blue-soft)" }}>
          <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Contactos (30d)</div>
          <div style={{ fontSize: 26, fontWeight: 700 }}>{data.contactos_30d}</div>
          <div style={{ fontSize: 11, color: "var(--txt-3)", marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
            <span title="Abrieron el WhatsApp del comercio">💬 {data.contactos_por_tipo?.whatsapp ?? 0}</span>
            <span title="Tocaron &quot;Cómo llegar&quot;">📍 {data.contactos_por_tipo?.mapa ?? 0}</span>
            {/* La reserva vale distinto que un WhatsApp suelto: no preguntó,
                pidió algo concreto. Es el número que justifica un plan pago. */}
            <span title="Mandaron una reserva" style={{ color: (data.contactos_por_tipo?.reserva ?? 0) > 0 ? "var(--neon)" : undefined }}>
              🛒 {data.contactos_por_tipo?.reserva ?? 0}
            </span>
            {(data.contactos_por_tipo?.telefono ?? 0) > 0 && <span title="Llamaron">📞 {data.contactos_por_tipo.telefono}</span>}
          </div>
          <div style={{ fontSize: 11, color: "var(--txt-3)", marginTop: 2 }}>
            {data.vistas_30d ?? 0} fichas vistas
          </div>
        </div>
        <div className="panel-card glass" style={{ padding: 16, borderLeft: `3px solid ${totalAlertas > 0 ? "var(--pink)" : "var(--neon)"}` }}>
          <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Bajas / vencidos</div>
          <div style={{ fontSize: 26, fontWeight: 700, color: totalAlertas > 0 ? "var(--pink)" : undefined }}>{totalAlertas}</div>
          <div style={{ fontSize: 11, color: "var(--txt-3)" }}>{data.alertas.por_vencer} por vencer en 5 días</div>
        </div>
      </div>

      {totalAlertas > 0 && (
        <div className="panel-card glass" style={{ padding: "12px 16px", border: "1px solid var(--pink)", color: "var(--pink)", fontSize: 13 }}>
          ⚠️ {data.alertas.vencido} comercio(s) vencido(s) y {data.alertas.suspendido} suspendido(s). Revisá la pestaña "Suscripciones".
        </div>
      )}

      <PanelPesoFotos />

      {/* Top ofertas */}
      <div className="panel-card glass">
        <div className="ph"><h3>Comercios con más ofertas</h3></div>
        {data.ofertas_top_comercios.length === 0 && (
          <div style={{ padding: 20, textAlign: "center", color: "var(--txt-3)" }}>Sin ofertas cargadas todavía.</div>
        )}
        {data.ofertas_top_comercios.map((c) => (
          <div key={c.comercio_id} style={{ display: "flex", justifyContent: "space-between", padding: "10px 16px", borderBottom: "1px solid var(--border)" }}>
            <span>{c.nombre}</span>
            <b style={{ color: "var(--neon)" }}>{c.count}</b>
          </div>
        ))}
      </div>

      {/* Top contactos */}
      <div className="panel-card glass">
        <div className="ph"><h3>Comercios más contactados</h3><span style={{ color: "var(--txt-3)", fontSize: 13 }}>Últimos 30 días</span></div>
        {data.contactos_top_comercios.length === 0 && (
          <div style={{ padding: 20, textAlign: "center", color: "var(--txt-3)" }}>Todavía no hay contactos registrados.</div>
        )}
        {data.contactos_top_comercios.map((c) => (
          <div key={c.comercio_id} style={{ display: "flex", justifyContent: "space-between", padding: "10px 16px", borderBottom: "1px solid var(--border)" }}>
            <span>{c.nombre}</span>
            <b style={{ color: "var(--blue-soft)" }}>{c.count}</b>
          </div>
        ))}
      </div>

      {/* Reservalo */}
      {reservalo && (reservalo.reservas_30d_total != null) && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
            <div className="panel-card glass" style={{ padding: 16, borderLeft: "3px solid var(--neon)" }}>
              <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Clientes nuevos (Reservalo, 7d)</div>
              <div style={{ fontSize: 26, fontWeight: 700 }}>{reservalo.clientes_nuevos_7d ?? 0}</div>
              <div style={{ fontSize: 11, color: "var(--txt-3)" }}>{reservalo.clientes_nuevos_30d ?? 0} en 30 días</div>
            </div>
            <div className="panel-card glass" style={{ padding: 16, borderLeft: "3px solid var(--blue-soft)" }}>
              <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Reservas (30d)</div>
              <div style={{ fontSize: 26, fontWeight: 700 }}>{reservalo.reservas_30d_total ?? 0}</div>
            </div>
          </div>

          <div className="panel-card glass">
            <div className="ph"><h3>Reservas por negocio</h3><span style={{ color: "var(--txt-3)", fontSize: 13 }}>Últimos 30 días · Reservalo</span></div>
            {(reservalo.reservas_30d_por_vendedor ?? []).length === 0 && (
              <div style={{ padding: 20, textAlign: "center", color: "var(--txt-3)" }}>Sin reservas todavía.</div>
            )}
            {(reservalo.reservas_30d_por_vendedor ?? []).map((v) => (
              <div key={v.vendedor_id} style={{ display: "flex", justifyContent: "space-between", padding: "10px 16px", borderBottom: "1px solid var(--border)" }}>
                <span>{nombrePorId(v.vendedor_id)}</span>
                <b style={{ color: "var(--neon)" }}>{v.count}</b>
              </div>
            ))}
          </div>

          <div className="panel-card glass">
            <div className="ph"><h3>Productos más consultados</h3><span style={{ color: "var(--txt-3)", fontSize: 13 }}>Por cantidad de chats · Reservalo</span></div>
            {(reservalo.top_productos_consultados ?? []).length === 0 && (
              <div style={{ padding: 20, textAlign: "center", color: "var(--txt-3)" }}>Sin consultas todavía.</div>
            )}
            {(reservalo.top_productos_consultados ?? []).map((p) => (
              <div key={p.producto_id} style={{ display: "flex", justifyContent: "space-between", padding: "10px 16px", borderBottom: "1px solid var(--border)" }}>
                <span>{p.nombre}</span>
                <b style={{ color: "var(--blue-soft)" }}>{p.count}</b>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

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
  const [gestionandoId, setGestionandoId] = useState<string | null>(null);

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
              <button className="btn btn-ghost btn-sm" title="Enviar mensaje al comercio" onClick={async () => {
                const cuerpo = prompt(`Mensaje para ${c.nombre}:`);
                if (cuerpo && cuerpo.trim()) { try { await enviarMensajeComercio(c.id, cuerpo.trim()); alert("Mensaje enviado ✓"); } catch { alert("No se pudo enviar"); } }
              }}>✉️</button>
              <button className="btn btn-ghost btn-sm" title="Confiable y números autorizados" onClick={() => setGestionandoId(c.id)}>
                ⚙️
              </button>
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

      {/* Modal de gestión: confiable + números autorizados */}
      {gestionandoId && (
        <ModalGestionComercio
          comercio={items.find((c) => c.id === gestionandoId)!}
          onClose={() => setGestionandoId(null)}
        />
      )}

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

type FiltroComercio = "todos" | "pendientes" | "verificados" | "incompletos" | "sin-horario";
type OrdenComercio = "recientes" | "alfabetico" | "estado";
type VistaComercio = "lista" | "mapa";

function normTxt(s: string): string {
  return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

// Motivos por los que un comercio está "incompleto" (para completarlo en tanda).
//
// `noComerciales` son los slugs de rubros marcados `comercial = false` en la
// base: baños, taxis, trámites. A un baño público no se le reclama WhatsApp ni
// productos — está completo así. Sin esta excepción, cada punto de la ciudad
// que se cargue queda para siempre en la cola de "incompletos", y una cola que
// nunca baja se deja de mirar.
function incompletoDe(c: ComercioPorVerificar, noComerciales?: Set<string>): string[] {
  const r: string[] = [];
  const nombre = (c.nombre ?? "").trim();
  const rubroNombre = (c.rubros?.nombre ?? "").trim();
  // "sin nombre" = vacío, el default 'Comercio', o quedó con el nombre del rubro.
  if (!nombre || nombre.toLowerCase() === "comercio" || (!!rubroNombre && nombre.toLowerCase() === rubroNombre.toLowerCase())) r.push("sin nombre");
  if (!c.portada_url) r.push("sin foto");
  // La foto sí se le pide a todo: un baño sin foto en el mapa no se distingue
  // de un pin cualquiera, y la foto es lo que hace que alguien lo reconozca al
  // llegar.
  const esPunto = !!noComerciales?.has(c.rubros?.slug ?? "");
  if (esPunto) return r;
  if (!c.whatsapp && !c.telefono) r.push("sin contacto");
  // "otros" NO es un rubro: es el descarte. Un comercio ahí no aparece en
  // ninguna búsqueda por categoría, así que cuenta como sin clasificar. Antes
  // esto no se detectaba y los 92 comercios en "otros" figuraban como completos.
  if (!c.rubros?.slug || c.rubros.slug === "otros") r.push("sin clasificar");
  if (!c.prod_obs_human?.trim() && !c.prod_det_ia?.trim()) r.push("sin productos");
  return r;
}

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
  const [q, setQ] = useState("");
  const [orden, setOrden] = useState<OrdenComercio>("recientes");
  // Foto ampliada. Vive acá y no en cada tarjeta: el overlay va a pantalla
  // completa, así que sólo puede haber uno abierto a la vez.
  const [fotoGrande, setFotoGrande] = useState<{ src: string; alt: string } | null>(null);
  const [vista, setVista] = useState<VistaComercio>("lista");
  const [limitVis, setLimitVis] = useState(50);
  const [editandoId, setEditandoId] = useState<string | null>(null);

  const noComerciales = new Set(rubros.filter((r) => r.comercial === false).map((r) => r.slug));
  const nIncompletos = todos.filter((c) => incompletoDe(c, noComerciales).length > 0).length;
  const nVerificados = todos.filter((c) => c.verificado).length;
  const sinHorario = (c: ComercioPorVerificar) =>
    !((c as Record<string, unknown>).horario as string ?? "").trim();
  const nSinHorario = todos.filter(sinHorario).length;

  // 1) filtro por estado (B incluye "incompletos")
  const porEstado = filtro === "todos" ? todos
    : filtro === "pendientes" ? todos.filter((c) => !c.verificado)
    : filtro === "verificados" ? todos.filter((c) => c.verificado)
    : filtro === "sin-horario" ? todos.filter(sinHorario)
    : todos.filter((c) => incompletoDe(c, noComerciales).length > 0);

  // 2) buscador multi-campo (A): nombre + qué vende + dirección + contacto + rubro + ciudad
  const nq = normTxt(q.trim());
  // Se busca por PALABRAS y todas tienen que estar, no la frase entera.
  //
  // Antes era `includes(nq)` sobre el texto pegado: "coca hoja" no encontraba a
  // "hoja de coca" —está en otro orden— y "juguete niño" no encontraba a una
  // juguetería que vende juguetes para niños. Escribir dos palabras devolvía
  // menos que escribir una, que es lo contrario de lo que espera cualquiera.
  //
  // Esto NO tiene tolerancia a errores de tipeo, a diferencia del buscador
  // público: acá se viene a encontrar un comercio que se sabe que existe, y
  // adivinar sería peor. "decoca" no va a aparecer nunca porque en la base dice
  // "de coca".
  const palabras = nq.split(/\s+/).filter(Boolean);
  const buscadas = !palabras.length ? porEstado : porEstado.filter((c) => {
    // El código se busca con o sin el prefijo: en el papel dice "URUKU-K7M2"
    // pero en la base sólo está "K7M2".
    const texto = [c.nombre, c.descripcion, c.prod_obs_human, c.prod_det_ia, c.subcategoria,
                   c.direccion, c.whatsapp, c.telefono, c.rubros?.nombre, c.ciudades?.nombre,
                   c.codigo, c.codigo ? `uruku-${c.codigo}` : ""]
      .map((x) => normTxt(x ?? "")).join(" ");
    return palabras.every((p) => texto.includes(p));
  });

  // 3) orden (G)
  const filtradas = [...buscadas].sort((a, b) => {
    if (orden === "alfabetico") return (a.nombre ?? "").localeCompare(b.nombre ?? "");
    if (orden === "estado") return Number(a.verificado) - Number(b.verificado);      // pendientes primero
    return (b.created_at ?? "").localeCompare(a.created_at ?? "");                    // recientes primero
  });

  // reset de la paginación cuando cambian filtros/búsqueda/orden
  useEffect(() => { setLimitVis(50); }, [filtro, q, orden]);

  const visibles = filtradas.slice(0, limitVis);
  const editando = editandoId ? todos.find((c) => c.id === editandoId) ?? null : null;

  const chips: { key: FiltroComercio; label: string; n: number; amber?: boolean }[] = [
    { key: "todos", label: "Todos", n: todos.length },
    { key: "pendientes", label: "Pendientes", n: pendientes.length },
    { key: "verificados", label: "Verificados", n: nVerificados },
    { key: "incompletos", label: "Incompletos", n: nIncompletos, amber: true },
    // Su propio filtro y no un motivo más de "incompleto": cargar horarios es
    // una pasada aparte —se hace de corrido, con la foto al lado— y mezclada
    // con los sin nombre y los sin foto no se puede hacer de corrido.
    { key: "sin-horario", label: "Sin horario", n: nSinHorario, amber: true },
  ];

  return (
    <div className="panel-card glass">
      {/* Por Portal: `.glass` tiene backdrop-filter y eso vuelve al contenedor
          el marco de referencia de `position: fixed`. Sin esto el overlay se
          centraría sobre la tarjeta de la lista, no sobre la pantalla — el
          mismo bug que ya nos escondió los modales. */}
      {fotoGrande && (
        <Portal>
          <ImageLightbox src={fotoGrande.src} alt={fotoGrande.alt}
                         onClose={() => setFotoGrande(null)} />
        </Portal>
      )}

      {/* Sin encabezado: el título repetía lo que ya dice la pestaña y se comía
          un renglón entero de una pantalla donde lo que hace falta es ver
          comercios. El único dato que valía —cuántos coincidieron— se movió al
          lado del buscador, sin ocupar alto propio. */}

      {/* Buscador (A) + orden (G) + vista lista/mapa (D) */}
      <div style={{ display: "flex", gap: 8, padding: "16px 16px 0", flexWrap: "wrap", alignItems: "center" }}>
        <input className="adm-input" style={{ flex: 1, minWidth: 200 }} value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar por nombre, código (URUKU-K7M2), productos, dirección, teléfono…" />
        {/* Sólo cuando el número dice algo: sin búsqueda ni filtro repite el
            "Todos (886)" del chip de abajo. */}
        {(q.trim() || filtro !== "todos") && (
          <span style={{ color: "var(--txt-3)", fontSize: 13, whiteSpace: "nowrap" }}>
            {filtradas.length} de {todos.length}
          </span>
        )}
        <select className="adm-input" style={{ width: "auto" }} value={orden} onChange={(e) => setOrden(e.target.value as OrdenComercio)}>
          <option value="recientes">Más recientes</option>
          <option value="alfabetico">A → Z</option>
          <option value="estado">Pendientes primero</option>
        </select>
        <div style={{ display: "flex", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden" }}>
          {(["lista", "mapa"] as VistaComercio[]).map((v) => (
            <button key={v} onClick={() => setVista(v)}
              style={{ padding: "7px 14px", fontSize: 13, cursor: "pointer", border: "none",
                background: vista === v ? "var(--neon)22" : "transparent",
                color: vista === v ? "var(--neon)" : "var(--txt-2)", fontWeight: vista === v ? 600 : 400 }}>
              {v === "lista" ? "☰ Lista" : "🗺 Mapa"}
            </button>
          ))}
        </div>
      </div>

      {/* Filtros por estado */}
      <div style={{ display: "flex", gap: 8, padding: "12px 16px", borderBottom: "1px solid var(--border)", flexWrap: "wrap" }}>
        {chips.map(({ key, label, n, amber }) => {
          const activo = filtro === key;
          const col = amber ? "var(--amber)" : "var(--neon)";
          return (
            <button key={key} onClick={() => setFiltro(key)}
              style={{ padding: "5px 14px", borderRadius: 20, border: "1px solid", cursor: "pointer", fontSize: 13,
                borderColor: activo ? col : "var(--border)",
                background: activo ? `${col}22` : "transparent",
                color: activo ? col : "var(--txt-2)", fontWeight: activo ? 600 : 400 }}>
              {label} ({n})
            </button>
          );
        })}
      </div>

      {/* Clasificación masiva: arriba de la lista, porque con 161 comercios sin
          categoría es la acción más útil de esta pantalla. */}
      <AnalisisMasivo onTerminado={onEdited} />

      {/* Vista MAPA (D): tocar un pin abre el editor; ideal para los sin nombre */}
      {vista === "mapa" ? (
        <div style={{ padding: 12 }}>
          <AdminMap
            comercios={filtradas.map((c) => ({
              id: c.id, nombre: c.nombre, lat: c.lat, lng: c.lng,
              rubro_slug: c.rubros?.slug ?? null, incompleto: incompletoDe(c, noComerciales).length > 0,
              lugar_id: c.lugar_id, lugar_nombre: c.lugares?.nombre ?? null, lugar_lat: c.lugares?.lat ?? null, lugar_lng: c.lugares?.lng ?? null, lugar_portada_thumb: c.lugares?.portada_thumb_url ?? null,
            }))}
            onSelect={setEditandoId}
          />
        </div>
      ) : (
      <>
      {visibles.length === 0 && (
        <div style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>Sin resultados.</div>
      )}

      {visibles.map((c) => {
        const motivos = incompletoDe(c, noComerciales);
        return (
        // flexWrap + minWidth en la info: en un celular los 5 botones de acción
        // no cedían espacio (flex-shrink: 0) y aplastaban el texto hasta dejar
        // una palabra por renglón. Ahora las acciones bajan a otra línea.
        <div key={c.id} className="adm-fila" style={{ display: "flex", gap: 12, padding: "14px 16px", borderBottom: "1px solid var(--border)", alignItems: "flex-start", flexWrap: "wrap" }}>
          {/* Foto — se agranda al tocarla.
              La miniatura son 64px: alcanza para ubicar la tarjeta, no para
              ver QUÉ vende el local. Y eso es lo que hay que decidir antes de
              mandar la ficha a la IA o de corregir lo que propuso. La versión
              grande es `portada_url`; la miniatura pesa 31KB y se ve borrosa
              ampliada. */}
          <button
            type="button"
            onClick={() => setFotoGrande({
              src: c.portada_url ?? c.portada_thumb_url ?? "",
              alt: c.nombre || "Comercio",
            })}
            disabled={!c.portada_url && !c.portada_thumb_url}
            title="Ver la foto en grande"
            style={{ padding: 0, border: "none", background: "none", flexShrink: 0,
                     cursor: (c.portada_url || c.portada_thumb_url) ? "zoom-in" : "default" }}
          >
            <img
              src={c.portada_thumb_url ?? c.portada_url ?? "https://picsum.photos/seed/" + c.id + "/80/80"}
              alt=""
              style={{ width: 64, height: 64, objectFit: "cover", borderRadius: 10, display: "block" }}
            />
          </button>

          {/* Info — clickeable entera. El encabezado dice "click para editar" y
              hasta ahora sólo abría el botón del lápiz: apuntar a un ícono de
              16px, 800 veces, es el doble de trabajo que tocar el nombre. */}
          <div
            onClick={() => setEditandoId(c.id)}
            title="Editar este comercio"
            style={{ flex: "1 1 200px", minWidth: 0, cursor: "pointer" }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <span style={{ fontWeight: 600, fontSize: 15 }}>{c.nombre || "Sin nombre"}</span>
              {c.verificado
                ? <span style={{ fontSize: 11, color: "var(--neon)", background: "var(--neon)22", padding: "2px 8px", borderRadius: 10 }}>✓ verificado</span>
                : <span style={{ fontSize: 11, color: "var(--amber)", background: "var(--amber)22", padding: "2px 8px", borderRadius: 10 }}>pendiente</span>}
              {c.suspendido && <span style={{ fontSize: 11, color: "#888", background: "#88888822", padding: "2px 8px", borderRadius: 10 }}>suspendido</span>}
              {motivos.map((m) => (
                <span key={m} style={{ fontSize: 11, color: "var(--amber)", border: "1px dashed var(--amber)", padding: "1px 7px", borderRadius: 10 }}>⚠️ {m}</span>
              ))}
            </div>
            <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 3 }}>
              {c.codigo && <span style={{ fontFamily: "monospace", color: "var(--neon)" }}>URUKU-{c.codigo} · </span>}
              {c.rubros?.nombre ?? "Sin rubro"}
              {c.lugares?.nombre ? ` · 🏬 ${c.lugares.nombre}${c.puesto ? ` #${c.puesto}` : ""}` : ""}
              {c.ciudades?.nombre ? ` · ${c.ciudades.nombre}` : ""}
              {c.modalidad ? ` · ${MODALIDAD_LABEL[c.modalidad] ?? c.modalidad}` : ""}
            </div>
            {/* Productos primero: es el texto del que sale la clasificación, así
                que es lo que hay que leer para decidir si el rubro está bien. */}
            {c.prod_obs_human && (
              <div style={{ fontSize: 12, color: "var(--txt)", marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                👤 {c.prod_obs_human}
              </div>
            )}
            {c.prod_det_ia && (
              <div style={{ fontSize: 12, color: "var(--blue-soft, #7aa2f7)", marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                🤖 {c.prod_det_ia}{c.subcategoria ? ` · ${c.subcategoria}` : ""}
              </div>
            )}
            {c.descripcion && (
              <div style={{ fontSize: 12, color: "var(--txt-2)", marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {c.descripcion}
              </div>
            )}
          </div>

          {/* Acciones */}
          <div style={{ display: "flex", gap: 8, flexShrink: 0, alignItems: "center", marginLeft: "auto" }}>
            {c.whatsapp && (
              <a
                href={`https://wa.me/${c.whatsapp}`}
                target="_blank" rel="noopener"
                className="mbtn"
                title={`WhatsApp +${c.whatsapp}`}
                style={{ display: "flex", alignItems: "center", justifyContent: "center" }}
              >
                <WhatsApp style={{ width: 16, height: 16 }} />
              </a>
            )}
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
        );
      })}

      {filtradas.length > limitVis && (
        <div style={{ padding: 16, textAlign: "center" }}>
          <button className="btn btn-ghost" onClick={() => setLimitVis((n) => n + 50)}>
            Ver más ({filtradas.length - limitVis} restantes)
          </button>
        </div>
      )}
      </>
      )}

      {editando && (() => {
        // El trabajo real es pasar comercio por comercio. Cerrar el modal,
        // buscar el renglón siguiente y volver a abrirlo son tres gestos por
        // ficha; multiplicado por 800, es lo que hace que la tarea se abandone
        // a la mitad. El modal se mueve solo por la lista YA filtrada.
        const i = filtradas.findIndex((c) => c.id === editando.id);
        const saltar = (d: number) => {
          const sig = filtradas[i + d];
          if (sig) setEditandoId(sig.id);
          else { setEditandoId(null); onEdited(); }
        };
        return (
          <ModalEditar
            key={editando.id}
            comercio={editando}
            rubros={rubros}
            posicion={i >= 0 ? { actual: i + 1, total: filtradas.length } : null}
            haySiguiente={i >= 0 && i + 1 < filtradas.length}
            hayAnterior={i > 0}
            onSaltar={saltar}
            onClose={() => setEditandoId(null)}
            onDone={() => { setEditandoId(null); onEdited(); }}
          />
        );
      })()}
    </div>
  );
}

/** Deja el campo como una URL que `href` pueda abrir.
 *
 * Lo que se copia de un celular es "@lobito" o "instagram.com/lobito", nunca la
 * URL completa. La ficha pública pone el valor crudo en `href`, así que sin
 * esto quedaba un enlace relativo — uruku.bo/@lobito, un 404 con cara de red
 * social cargada. Devuelve undefined si está vacío para no pisar con "". */
function normalizarRed(valor: string, base: string): string | undefined {
  const v = valor.trim();
  if (!v) return undefined;
  if (/^https?:\/\//i.test(v)) return v;
  if (v.includes(".") && !v.startsWith("@")) return `https://${v.replace(/^\/+/, "")}`;
  return base + v.replace(/^@+/, "");
}

const ULTIMO_HORARIO = "uruku_ultimo_horario";

function ultimoHorario(): string {
  if (typeof window === "undefined") return "";
  try { return localStorage.getItem(ULTIMO_HORARIO) ?? ""; } catch { return ""; }
}

/** Los horarios que de verdad se repiten en Bermejo.
 *
 *  El texto va en el formato que `abiertoAhora` entiende: los días de un lado y
 *  los dos turnos en el mismo segmento, para que la tarde no se aplique también
 *  al domingo. Un horario que el parser no entiende es peor que ninguno —el
 *  comprador no ve "Abierto ahora" y nadie se entera de por qué. */
const HORARIOS_FRECUENTES: { label: string; texto: string }[] = [
  { label: "8-12 · 14:30-20 (L-S)", texto: "Lun-Sáb 8:00-12:00 y 14:30-20:00" },
  { label: "8-12 · 14:30-20 + Dom AM", texto: "Lun-Sáb 8:00-12:00 y 14:30-20:00 · Dom 8:00-12:00" },
  { label: "Corrido 8-20 (L-S)", texto: "Lun-Sáb 8:00-20:00" },
  { label: "Corrido 9-21 (todos)", texto: "Todos los días 9:00-21:00" },
  { label: "9-13 · 15-19 (L-V)", texto: "Lun-Vie 9:00-13:00 y 15:00-19:00" },
  { label: "24 horas", texto: "Todos los días 0:00-24:00" },
];

function ModalEditar({
  comercio, rubros, onClose, onDone,
  posicion = null, haySiguiente = false, hayAnterior = false, onSaltar,
}: {
  comercio: ComercioPorVerificar;
  rubros: Rubro[];
  onClose: () => void;
  onDone: () => void;
  posicion?: { actual: number; total: number } | null;
  haySiguiente?: boolean;
  hayAnterior?: boolean;
  onSaltar?: (delta: number) => void;
}) {
  const [nombre, setNombre] = useState(comercio.nombre);
  const [whatsapp, setWhatsapp] = useState(comercio.whatsapp ?? "");
  const [telefono, setTelefono] = useState((comercio as Record<string, unknown>).telefono as string ?? "");
  const [descripcion, setDescripcion] = useState(comercio.descripcion ?? "");
  const [modalidad, setModalidad] = useState(comercio.modalidad ?? "local");
  const [direccion, setDireccion] = useState(comercio.direccion ?? "");
  const [horario, setHorario] = useState((comercio as Record<string, unknown>).horario as string ?? "");
  const _campo = (k: string) => (comercio as Record<string, unknown>)[k] as string ?? "";
  const [instagram, setInstagram] = useState(_campo("instagram_url"));
  const [facebook, setFacebook] = useState(_campo("facebook_url"));
  const [tiktok, setTiktok] = useState(_campo("tiktok_url"));
  const [sitioWeb, setSitioWeb] = useState(_campo("sitio_web"));
  const [email, setEmail] = useState(_campo("email"));
  const _rubroActual = (comercio.rubros as { slug: string } | undefined)?.slug;
  const [rubroSlugs, setRubroSlugs] = useState<string[]>(_rubroActual ? [_rubroActual] : []);
  const [prodObsHuman, setProdObsHuman] = useState(comercio.prod_obs_human ?? "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  // El formulario es largo (42 categorías) y el botón Cancelar queda muy abajo:
  // sin Escape ni ✕ en el encabezado, se entra al editor y no se ve cómo salir.
  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onEsc);
    return () => document.removeEventListener("keydown", onEsc);
  }, [onClose]);

  async function persistir(): Promise<boolean> {
    setSaving(true);
    setErr("");
    try {
      await editarComercio(comercio.id, {
        prod_obs_human: prodObsHuman || undefined,
        nombre: nombre || undefined,
        whatsapp: whatsapp || undefined,
        telefono: telefono || undefined,
        descripcion: descripcion || undefined,
        modalidad: modalidad || undefined,
        direccion: direccion || undefined,
        horario: horario || undefined,
        instagram_url: normalizarRed(instagram, "https://instagram.com/"),
        facebook_url: normalizarRed(facebook, "https://facebook.com/"),
        tiktok_url: normalizarRed(tiktok, "https://tiktok.com/@"),
        sitio_web: normalizarRed(sitioWeb, "https://"),
        email: email || undefined,
        rubro_slugs: rubroSlugs.length ? rubroSlugs : undefined,
      });
      // Se recuerda para el "igual que el anterior" de la ficha siguiente.
      // En localStorage y no en estado: el modal se remonta con `key` en cada
      // comercio, así que cualquier estado propio se pierde justo cuando hace
      // falta.
      if (horario.trim()) { try { localStorage.setItem(ULTIMO_HORARIO, horario.trim()); } catch { /* modo privado */ } }
      return true;
    } catch {
      setErr("No se pudo guardar. Verificá el backend.");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    if (await persistir()) onDone();
  }

  /** Guarda y encadena con el siguiente sin cerrar el modal.
   *
   * Si el guardado falla NO avanza: pasar de largo dejaría el cambio perdido y
   * el cartel de error tapado por la ficha siguiente. */
  async function guardarYSeguir() {
    if (await persistir()) onSaltar?.(1);
  }

  return (
    <Portal>
      <div onClick={onClose}
        style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
        <div className="glass" onClick={(e) => e.stopPropagation()}
          style={{ width: "100%", maxWidth: 480, borderRadius: 16, padding: 24, maxHeight: "90vh", overflowY: "auto" }}>
          {/* Encabezado pegajoso: la salida tiene que estar siempre a la vista,
              no al final de un formulario de 42 chips. */}
          <div style={{ position: "sticky", top: -24, zIndex: 1, background: "var(--panel, #12161d)",
                        margin: "-24px -24px 14px", padding: "18px 24px 12px",
                        display: "flex", alignItems: "center", justifyContent: "space-between",
                        borderBottom: "1px solid var(--border)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
              <h3 style={{ margin: 0 }}>Editar negocio</h3>
              {posicion && (
                <span style={{ fontSize: 12, color: "var(--txt-3)", whiteSpace: "nowrap" }}>
                  {posicion.actual} de {posicion.total}
                </span>
              )}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {onSaltar && (
                <>
                  <button type="button" className="mbtn" title="Anterior (sin guardar)"
                    disabled={!hayAnterior} onClick={() => onSaltar(-1)}
                    style={{ opacity: hayAnterior ? 1 : .35 }}>←</button>
                  <button type="button" className="mbtn" title="Siguiente (sin guardar)"
                    disabled={!haySiguiente} onClick={() => onSaltar(1)}
                    style={{ opacity: haySiguiente ? 1 : .35 }}>→</button>
                </>
              )}
            <button type="button" onClick={onClose} aria-label="Cerrar"
              style={{ background: "none", border: "none", color: "var(--txt-2)", fontSize: 22, cursor: "pointer", lineHeight: 1 }}>
              ✕
            </button>
            </div>
          </div>
          {/* Primero de todo: es la acción principal del trabajo de clasificación.
              Antes estaba después de las fotos y quedaba fuera de la vista. */}
          <AnalisisComercio comercioId={comercio.id} onAplicado={onDone} />

          <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 12 }}>
            {/* La foto al lado del campo, no 300px más abajo: el nombre se lee
                del cartel de la propia foto, y tenerla que ir a buscar con el
                scroll era el paso que hacía lento el ir uno por uno. */}
            <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
              {(comercio.portada_url || comercio.portada_thumb_url) && (
                <a href={comercio.portada_url ?? comercio.portada_thumb_url ?? "#"}
                   target="_blank" rel="noopener" title="Abrir la foto en grande"
                   style={{ flexShrink: 0 }}>
                  <img src={comercio.portada_url ?? comercio.portada_thumb_url ?? ""} alt=""
                       style={{ width: 132, height: 132, objectFit: "cover", borderRadius: 12, display: "block" }} />
                </a>
              )}
              <label style={{ fontSize: 12, color: "var(--txt-3)", flex: 1, minWidth: 0 }}>Nombre
                <input className="adm-input" style={{ marginTop: 4, fontSize: 16, fontWeight: 600 }}
                  value={nombre} onChange={(e) => setNombre(e.target.value)}
                  autoFocus placeholder="Nombre del negocio" />
                {comercio.codigo && (
                  <div style={{ marginTop: 6, fontFamily: "monospace", color: "var(--neon)", fontSize: 12 }}>
                    URUKU-{comercio.codigo}
                  </div>
                )}
              </label>
            </div>
            <label style={{ fontSize: 12, color: "var(--txt-3)" }}>WhatsApp (opcional)
              <input className="adm-input" style={{ marginTop: 4 }} value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)} placeholder="591XXXXXXXX" />
            </label>
            <label style={{ fontSize: 12, color: "var(--txt-3)" }}>Teléfono (opcional)
              <input className="adm-input" style={{ marginTop: 4 }} value={telefono} onChange={(e) => setTelefono(e.target.value)} placeholder="Fijo o celular para llamar" />
            </label>
            <label style={{ fontSize: 12, color: "var(--txt-3)" }}>👤 Productos observados (dato humano — la IA no lo toca)
              <textarea className="adm-input" style={{ marginTop: 4, minHeight: 56, resize: "vertical" }} value={prodObsHuman}
                onChange={(e) => setProdObsHuman(e.target.value)}
                placeholder="zapatillas, championes, chinelas, mochilas" />
            </label>
            {comercio.prod_det_ia && (
              <div style={{ fontSize: 12, color: "var(--txt-3)" }}>🤖 Detectado por IA
                <div style={{ marginTop: 4, padding: 8, border: "1px solid var(--border)", borderRadius: 8, color: "var(--txt-2)" }}>
                  {comercio.prod_det_ia}
                  {comercio.subcategoria && <div style={{ opacity: .8, marginTop: 4 }}>Subcategoría: {comercio.subcategoria}</div>}
                </div>
              </div>
            )}
            <label style={{ fontSize: 12, color: "var(--txt-3)" }}>🤖 Descripción (la regenera la IA en cada análisis)
              <textarea className="adm-input" style={{ marginTop: 4, minHeight: 70, resize: "vertical" }} value={descripcion} onChange={(e) => setDescripcion(e.target.value)} placeholder="Se completa al analizar las fotos" />
            </label>
            <FotosComercio comercioId={comercio.id} portada={comercio.portada_url ?? null} />

            <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Categorías (tocá para elegir varias)
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6,
                            maxHeight: 170, overflowY: "auto", padding: 6,
                            border: "1px solid var(--border)", borderRadius: 10 }}>
                {rubros.map((r) => {
                  const on = rubroSlugs.includes(r.slug);
                  return (
                    <button type="button" key={r.slug} className={`mchip ${on ? "active" : ""}`} style={{ cursor: "pointer" }}
                      onClick={() => setRubroSlugs((prev) => on ? prev.filter((s) => s !== r.slug) : [...prev, r.slug])}>
                      {r.nombre}
                    </button>
                  );
                })}
              </div>
            </div>
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
            {/* HORARIO: el campo más caro del proyecto.
                Son 886 comercios y ninguno lo tiene, y es el dato que decide si
                alguien camina hasta el local o no. Escribirlo a mano 886 veces
                no lo hace nadie, así que acá se toca en vez de escribirse.
                "Igual que el anterior" es el que más rinde: en una cuadra los
                locales abren casi todos a la misma hora, y viniendo de a uno
                con las flechas, el anterior suele ser el vecino. */}
            <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Horario
              <input className="adm-input" style={{ marginTop: 4 }} value={horario}
                onChange={(e) => setHorario(e.target.value)} placeholder="Lun-Sáb 9-20 · Dom 10-14" />
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                {ultimoHorario() && ultimoHorario() !== horario && (
                  <button type="button" className="mchip" style={{ cursor: "pointer", borderColor: "var(--neon)", color: "var(--neon)" }}
                    onClick={() => setHorario(ultimoHorario())}
                    title={ultimoHorario()}>
                    ↩ Igual que el anterior
                  </button>
                )}
                {HORARIOS_FRECUENTES.map((h) => (
                  <button type="button" key={h.texto} className={`mchip ${horario === h.texto ? "active" : ""}`}
                    style={{ cursor: "pointer" }} title={h.texto}
                    onClick={() => setHorario(horario === h.texto ? "" : h.texto)}>
                    {h.label}
                  </button>
                ))}
                {horario && (
                  <button type="button" className="mchip" style={{ cursor: "pointer" }} onClick={() => setHorario("")}>
                    Limpiar
                  </button>
                )}
              </div>
              {/* Lo que el sitio va a entender de lo que quedó escrito. Si dice
                  "no se entiende", el comprador no va a ver "Abierto ahora" —
                  y eso hay que saberlo ACÁ, no descubrirlo en la ficha. */}
              {horario.trim() && (
                <div style={{ marginTop: 6, fontSize: 11.5,
                              color: abiertoAhora(horario).estado === "desconocido" ? "var(--amber)" : "var(--txt-3)" }}>
                  {abiertoAhora(horario).estado === "desconocido"
                    ? "⚠️ No se entiende: el sitio no va a poder decir si está abierto"
                    : `Ahora mismo: ${abiertoAhora(horario).estado}`}
                </div>
              )}
            </div>

            {/* Las columnas y el endpoint existían desde el init; lo que no
                había era dónde escribirlas, así que la ficha pública nunca
                mostró una red social de nadie. Se puede pegar "@lobito" o el
                link entero: lo de abajo lo normaliza. */}
            <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Redes y contacto
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 6 }}>
                <input className="adm-input" value={instagram} onChange={(e) => setInstagram(e.target.value)} placeholder="Instagram: @usuario o link" />
                <input className="adm-input" value={facebook} onChange={(e) => setFacebook(e.target.value)} placeholder="Facebook: usuario o link" />
                <input className="adm-input" value={tiktok} onChange={(e) => setTiktok(e.target.value)} placeholder="TikTok: @usuario o link" />
                <input className="adm-input" value={sitioWeb} onChange={(e) => setSitioWeb(e.target.value)} placeholder="Sitio web" />
                <input className="adm-input" style={{ gridColumn: "1 / -1" }} value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email (opcional)" />
              </div>
            </div>
            {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
            <div style={{ display: "flex", gap: 10, marginTop: 4, flexWrap: "wrap" }}>
              <button type="button" className="btn btn-ghost" style={{ flex: 1, minWidth: 110 }} onClick={onClose}>Cancelar</button>
              <button type="submit" className="btn btn-primary" style={{ flex: 2, minWidth: 150 }} disabled={saving}>
                {saving ? "Guardando…" : "Guardar cambios"}
              </button>
              {haySiguiente && (
                <button type="button" className="btn btn-primary" style={{ flex: 2, minWidth: 170 }}
                  disabled={saving} onClick={guardarYSeguir}>
                  {saving ? "Guardando…" : "Guardar y siguiente →"}
                </button>
              )}
            </div>
          </form>
        </div>
      </div>
    </Portal>
  );
}

// ── Modal Pago ────────────────────────────────────────────────────────────────

/** Clasificación por fotos de todos los comercios pendientes.
 *
 * Va de a pocos y en bucle desde el navegador, no en una sola llamada: cada
 * análisis tarda varios segundos, y 161 seguidos superan cualquier timeout y
 * chocan con el límite de frecuencia de Gemini. Así además el avance se ve y se
 * puede cortar en cualquier momento sin perder lo hecho.
 */
function AnalisisMasivo({ onTerminado }: { onTerminado: () => void }) {
  const [pendientes, setPendientes] = useState<number | null>(null);
  const [corriendo, setCorriendo] = useState(false);
  const [hechos, setHechos] = useState(0);
  const [ultimos, setUltimos] = useState<ResultadoTanda[]>([]);
  const [err, setErr] = useState("");
  const cancelar = useRef(false);

  useEffect(() => { pendientesAnalisis().then(setPendientes).catch(() => setPendientes(null)); }, []);

  async function correr() {
    setErr(""); setHechos(0); setUltimos([]); setCorriendo(true);
    cancelar.current = false;
    try {
      for (;;) {
        if (cancelar.current) break;
        const t = await analizarTanda(3, true);
        if (t.sin_mas || t.procesados === 0) { setPendientes(0); break; }
        setHechos((n) => n + t.procesados);
        setPendientes(t.restantes);
        setUltimos((prev) => [...t.resultados, ...prev].slice(0, 12));

        const fallo = t.resultados.find((r) => r.error);
        if (fallo) { setErr(`Se detuvo en "${fallo.nombre}": ${fallo.error}`); break; }
        if (t.restantes === 0) break;
        // Respiro entre tandas: el límite de Gemini es por ventana de tiempo, y
        // encadenar sin pausa es lo que dispara el 429.
        await new Promise((r) => setTimeout(r, 2500));
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Falló el análisis");
    } finally {
      setCorriendo(false);
      onTerminado();
    }
  }

  if (pendientes === null) return null;
  if (pendientes === 0 && !corriendo && hechos === 0) return null;

  return (
    <div style={{ border: "1px solid var(--neon)", background: "rgba(57,255,158,.06)",
                  borderRadius: 12, padding: 14, margin: "0 16px 12px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14 }}>🤖 Clasificar por fotos</div>
          <div style={{ fontSize: 12.5, color: "var(--txt-3)", marginTop: 2 }}>
            {corriendo
              ? `Analizando… ${hechos} listos · ${pendientes} por delante`
              : hechos > 0
                ? `${hechos} clasificados${pendientes ? ` · quedan ${pendientes}` : " · no queda ninguno"}`
                : `${pendientes} comercios con foto sin clasificar`}
          </div>
        </div>
        {corriendo ? (
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => { cancelar.current = true; }}>
            Detener
          </button>
        ) : (
          <button type="button" className="btn btn-primary btn-sm" onClick={correr} disabled={!pendientes}>
            Analizar {pendientes} pendientes
          </button>
        )}
      </div>

      {err && <div style={{ color: "var(--pink)", fontSize: 12.5, marginTop: 8 }}>{err}</div>}

      {ultimos.length > 0 && (
        <div style={{ marginTop: 10, borderTop: "1px solid var(--border)", paddingTop: 8, fontSize: 12 }}>
          {ultimos.map((r, i) => (
            <div key={`${r.slug}-${i}`} style={{ display: "flex", gap: 8, padding: "3px 0" }}>
              <span style={{ color: r.error ? "var(--pink)" : r.confianza >= 0.7 ? "var(--neon)" : "var(--amber)" }}>
                {r.error ? "✕" : `${Math.round(r.confianza * 100)}%`}
              </span>
              <b style={{ minWidth: 120 }}>{r.nombre}</b>
              <span style={{ color: "var(--txt-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {r.error ?? `${r.subcategoria || "—"} · ${r.productos || "nada detectado"}`}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Saca el contenido al <body>.
 *
 * Los modales viven dentro de `.panel-card.glass`, y `.glass` tiene
 * backdrop-filter. Un elemento con backdrop-filter se vuelve el marco de
 * referencia de todo `position: fixed` que tenga adentro, así que el modal no se
 * centraba en la pantalla sino sobre la tarjeta de la lista: había que scrollear
 * hasta el fondo para encontrarlo. En el celular quedaba directamente perdido.
 */
function Portal({ children }: { children: React.ReactNode }) {
  const [montado, setMontado] = useState(false);
  useEffect(() => setMontado(true), []);
  if (!montado) return null;
  return createPortal(children, document.body);
}

/** Clasificación por fotos: propone y, si el admin acepta, aplica.
 *
 * La propuesta se muestra SIEMPRE antes de escribir. El modelo es elocuente
 * aunque no vea nada —ante una persiana cerrada va a inventar algo plausible—,
 * así que la confianza va en grande y la decisión es de una persona. */
function AnalisisComercio({ comercioId, onAplicado }: { comercioId: string; onAplicado: () => void }) {
  const [res, setRes] = useState<AnalisisIA | null>(null);
  const [cargando, setCargando] = useState(false);
  const [aplicando, setAplicando] = useState(false);
  const [err, setErr] = useState("");

  async function analizar() {
    setErr(""); setCargando(true); setRes(null);
    try { setRes(await analizarComercio(comercioId, false)); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo analizar"); }
    finally { setCargando(false); }
  }

  async function aplicar() {
    setErr(""); setAplicando(true);
    try {
      await analizarComercio(comercioId, true);
      setRes(null);
      onAplicado();
    } catch (e) { setErr(e instanceof Error ? e.message : "No se pudo aplicar"); }
    finally { setAplicando(false); }
  }

  const p = res?.propuesta;
  const conf = p?.confianza ?? 0;
  const colorConf = conf >= 0.7 ? "var(--neon)" : conf >= 0.4 ? "var(--amber)" : "var(--pink)";
  const etiquetaConf = conf >= 0.7 ? "alta" : conf >= 0.4 ? "media" : "baja";

  return (
    <div style={{ border: "1px solid var(--neon)", background: "rgba(57,255,158,.06)",
                  borderRadius: 12, padding: 14 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <span style={{ fontSize: 13.5, fontWeight: 600 }}>🤖 Clasificar desde las fotos</span>
        <button type="button" className={res ? "btn btn-ghost btn-sm" : "btn btn-primary btn-sm"}
          disabled={cargando} onClick={analizar}>
          {cargando ? "Mirando las fotos…" : res ? "Analizar de nuevo" : "Analizar"}
        </button>
      </div>

      {err && <div style={{ color: "var(--pink)", fontSize: 12.5, marginTop: 8 }}>{err}</div>}

      {p && (
        <div style={{ marginTop: 10, fontSize: 12.5, lineHeight: 1.5 }}>
          <div style={{ marginBottom: 8 }}>
            Confianza <b style={{ color: colorConf }}>{etiquetaConf} ({Math.round(conf * 100)}%)</b>
            <span style={{ color: "var(--txt-3)" }}> · {p.fotos_analizadas} foto(s) analizada(s)</span>
            {p.tokens?.total != null && (
              // Entrada y salida por separado: la salida cuesta ~8 veces más y
              // en los modelos que razonan incluye los tokens de pensamiento.
              // Con el total solo no se ve si el costo se fue por ese lado.
              <span style={{ color: "var(--txt-3)" }}>
                {" · "}{p.tokens.total.toLocaleString("es-BO")} tokens
                {p.tokens.entrada != null && p.tokens.salida != null && (
                  <> ({p.tokens.entrada.toLocaleString("es-BO")} entrada +{" "}
                  <b style={{ color: p.tokens.salida > 1000 ? "var(--amber)" : "inherit" }}>
                    {p.tokens.salida.toLocaleString("es-BO")} salida
                  </b>)</>
                )}
              </span>
            )}
          </div>

          {/* Un fallo de la llamada NO es lo mismo que "no vio nada": antes las
              dos cosas mostraban el mismo cartel y no había cómo distinguirlas. */}
          {p.error ? (
            <div style={{ color: "var(--pink)", marginBottom: 8 }}>
              ⚠️ La llamada al modelo falló: {p.error}
            </div>
          ) : conf < 0.4 && (
            <div style={{ color: "var(--amber)", marginBottom: 8 }}>
              El modelo miró las fotos y no reconoció mercadería. Abrí la foto para
              ver si efectivamente no se ve nada, o si hay que sacar otra.
            </div>
          )}

          <div><b>Productos:</b> {p.productos || <i style={{ color: "var(--txt-3)" }}>nada detectado</i>}</div>
          <div><b>Subcategoría:</b> {p.subcategoria || <i style={{ color: "var(--txt-3)" }}>—</i>}</div>
          <div><b>Categorías:</b> {p.rubro_slugs.length ? p.rubro_slugs.join(", ") : <i style={{ color: "var(--txt-3)" }}>ninguna</i>}</div>
          {/* Sin esto, un rubro descartado se ve igual que un rubro no propuesto:
              "ninguna", sin explicación. Saber QUÉ propuso el modelo es lo que
              permite corregir la taxonomía o el prompt. */}
          {p.slugs_descartados && p.slugs_descartados.length > 0 && (
            <div style={{ color: "var(--amber)" }}>
              Propuso categorías que no existen y se descartaron: {p.slugs_descartados.join(", ")}
            </div>
          )}
          {p.descripcion && <div style={{ marginTop: 6 }}><b>Descripción:</b> {p.descripcion}</div>}

          <div style={{ color: "var(--txt-3)", marginTop: 8, fontSize: 11.5 }}>
            Al aplicar se guardan en <b>prod_det_ia</b>, <b>subcategoría</b> y
            se <b>reemplaza la descripción</b>.
            Tus productos observados no se tocan
            {res?.comercio.prod_obs_human ? ` (siguen siendo: "${res.comercio.prod_obs_human}")` : ""}.
          </div>

          {p.crudo && (
            <details style={{ marginTop: 8 }}>
              <summary style={{ cursor: "pointer", color: "var(--txt-3)", fontSize: 11.5 }}>
                Ver la respuesta del modelo
              </summary>
              <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 11,
                            color: "var(--txt-3)", marginTop: 6, maxHeight: 180, overflowY: "auto" }}>
                {p.crudo}
              </pre>
            </details>
          )}

          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <button type="button" className="btn btn-ghost btn-sm" style={{ flex: 1 }} onClick={() => setRes(null)}>
              Descartar
            </button>
            <button type="button" className="btn btn-primary btn-sm" style={{ flex: 2 }}
              disabled={aplicando || conf <= 0} onClick={aplicar}>
              {aplicando ? "Aplicando…" : "Aplicar"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Fotos del comercio dentro del editor.
 *
 * Existe porque para saber qué vende un local muchas veces hay que MIRAR la
 * vidriera: el texto que trajo el agente no siempre alcanza para clasificarlo.
 * Antes la única foto visible era el thumb de 64px de la lista, sin forma de
 * agrandarla, y no había manera de sumar fotos desde el panel. */
function FotosComercio({ comercioId, portada }: { comercioId: string; portada: string | null }) {
  const [fotos, setFotos] = useState<FotoComercio[]>([]);
  const [ampliada, setAmpliada] = useState<string | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const [err, setErr] = useState("");
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => { adminListarFotos(comercioId).then(setFotos).catch(() => {}); }, [comercioId]);

  async function subir(file: File | undefined) {
    if (!file) return;
    setErr(""); setSubiendo(true);
    try {
      const nueva = await adminSubirFoto(comercioId, file);
      setFotos((prev) => [...prev, nueva]);
    } catch (e) { setErr(e instanceof Error ? e.message : "No se pudo subir"); }
    finally { setSubiendo(false); if (input.current) input.current.value = ""; }
  }

  async function borrar(id: string) {
    if (!window.confirm("¿Borrar esta foto?")) return;
    await adminBorrarFoto(comercioId, id);
    setFotos((prev) => prev.filter((f) => f.id !== id));
  }

  const todas = [
    ...(portada ? [{ id: "__portada", url: portada, thumb_url: portada }] : []),
    ...fotos,
  ];

  return (
    <Portal>
      <div style={{ fontSize: 12, color: "var(--txt-3)" }}>
        Fotos del local (tocá para ampliar)
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
          {todas.length === 0 && <span style={{ opacity: 0.7 }}>Sin fotos todavía.</span>}
          {todas.map((f) => (
            <div key={f.id} style={{ position: "relative" }}>
              <img src={f.thumb_url ?? f.url} alt="" onClick={() => setAmpliada(f.url)}
                style={{ width: 72, height: 72, objectFit: "cover", borderRadius: 8, cursor: "zoom-in" }} />
              {f.id !== "__portada" && (
                <button type="button" onClick={() => borrar(f.id)} aria-label="Borrar foto"
                  style={{ position: "absolute", top: -6, right: -6, background: "var(--pink)", color: "#fff",
                           border: "none", borderRadius: "50%", width: 20, height: 20, cursor: "pointer", fontSize: 12 }}>
                  ×
                </button>
              )}
            </div>
          ))}
        </div>

        <input ref={input} type="file" accept="image/*" style={{ display: "none" }}
          onChange={(e) => subir(e.target.files?.[0])} />
        <button type="button" className="btn btn-ghost btn-sm" style={{ marginTop: 8 }}
          disabled={subiendo} onClick={() => input.current?.click()}>
          {subiendo ? "Subiendo…" : "+ Agregar foto"}
        </button>
        {err && <div style={{ color: "var(--pink)", marginTop: 6 }}>{err}</div>}

        {/* Visor: la foto grande, sobre todo lo demás */}
        {ampliada && (
          <div onClick={() => setAmpliada(null)}
            style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.92)", zIndex: 1200,
                     display: "flex", alignItems: "center", justifyContent: "center", cursor: "zoom-out" }}>
            <img src={ampliada} alt="" style={{ maxWidth: "96vw", maxHeight: "92vh", objectFit: "contain" }} />
            <button type="button" onClick={() => setAmpliada(null)} aria-label="Cerrar"
              style={{ position: "fixed", top: 16, right: 20, background: "none", border: "none",
                       color: "#fff", fontSize: 30, cursor: "pointer" }}>✕</button>
          </div>
        )}
      </div>
    </Portal>
  );
}

function ModalGestionComercio({ comercio, onClose }: { comercio: ComercioSuscripcion; onClose: () => void }) {
  const [confiable, setConfiable] = useState(!!comercio.confiable);
  const [rubros, setRubros] = useState<Rubro[]>([]);
  useEffect(() => { getRubros().then(setRubros).catch(() => {}); }, []);
  const [numeros, setNumeros] = useState<NumeroComercio[]>([]);
  const [nuevo, setNuevo] = useState("");
  const [etiqueta, setEtiqueta] = useState("");
  const [err, setErr] = useState("");
  const [cargando, setCargando] = useState(true);
  const [grupos, setGrupos] = useState<GrupoComercio[]>([]);
  const [grupoNuevo, setGrupoNuevo] = useState("");
  const [errGrupo, setErrGrupo] = useState("");
  const [misRubros, setMisRubros] = useState<string[] | null>(null);
  const [errRubros, setErrRubros] = useState("");

  useEffect(() => {
    listarNumeros(comercio.id)
      .then((r) => setNumeros(r.items ?? []))
      .catch(() => setErr("No se pudieron cargar los números"))
      .finally(() => setCargando(false));
    listarGrupos(comercio.id)
      .then((r) => setGrupos(r.items ?? []))
      .catch(() => setErrGrupo("No se pudieron cargar los grupos"));
    rubrosDeComercio(comercio.id)
      .then(setMisRubros)
      .catch(() => setErrRubros("No se pudieron cargar los rubros"));
  }, [comercio.id]);

  async function atar(e: React.FormEvent) {
    e.preventDefault();
    setErrGrupo("");
    try {
      const r = await atarGrupo(comercio.id, grupoNuevo.trim());
      setGrupos(r.grupos ?? []);
      setGrupoNuevo("");
    } catch (e2) {
      setErrGrupo(e2 instanceof Error ? e2.message : "No se pudo atar");
    }
  }

  // Un toque agrega o saca. Se guarda al instante y se revierte si falla: en un
  // trabajo de ir comercio por comercio, un botón "Guardar" por cada cambio es
  // el doble de toques y una oportunidad más de olvidárselo.
  async function toggleRubro(slug: string) {
    if (misRubros === null) return;
    const antes = misRubros;
    const ahora = antes.includes(slug) ? antes.filter((s) => s !== slug) : [...antes, slug];
    setMisRubros(ahora); setErrRubros("");
    try {
      setMisRubros(await editarRubrosComercio(comercio.id, ahora));
    } catch (e) {
      setMisRubros(antes);
      setErrRubros(e instanceof Error ? e.message : "No se pudo guardar");
    }
  }

  async function crearGrupo() {
    setErrGrupo("");
    if (!window.confirm(
      `Se va a crear un grupo de WhatsApp con ${comercio.nombre} y los números de URUKU. ` +
      `El comerciante lo va a ver aparecer en su teléfono. ¿Seguimos?`)) return;
    setGrupoNuevo("");
    try {
      const r = await crearGrupoComercio(comercio.id);
      setGrupos(r.grupos ?? []);
    } catch (e) {
      setErrGrupo(e instanceof Error ? e.message : "No se pudo crear el grupo");
    }
  }

  async function soltar(jid: string) {
    setErrGrupo("");
    try {
      const r = await soltarGrupo(comercio.id, jid);
      setGrupos(r.grupos ?? []);
    } catch {
      setErrGrupo("No se pudo soltar el grupo");
    }
  }

  async function toggleConfiable() {
    const valor = !confiable;
    setConfiable(valor);
    try { await setConfiable_(comercio.id, valor); }
    catch { setConfiable(!valor); setErr("No se pudo cambiar"); }
  }

  async function agregar(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      const r = await agregarNumero(comercio.id, nuevo.trim(), etiqueta.trim() || undefined);
      setNumeros((prev) => [...prev.filter((n) => n.numero !== r.numero.numero), r.numero]);
      setNuevo(""); setEtiqueta("");
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "No se pudo autorizar");
    }
  }

  return (
    <Portal>
      <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
        <div className="glass" style={{ width: "100%", maxWidth: 460, borderRadius: 16, padding: 24, maxHeight: "90vh", overflowY: "auto" }}>
          <h3 style={{ marginBottom: 4 }}>{comercio.nombre}</h3>
          <p style={{ color: "var(--txt-3)", fontSize: 13, marginBottom: 18 }}>Código, confianza y números autorizados</p>

          {/* Código del local: identificador estable de cara al dueño. El celular
              puede cambiar; esto no. Con él publica por WhatsApp desde cualquier
              número, sin cuenta y sin haber pagado. */}
          {comercio.codigo && (
            <div style={{ padding: 12, borderRadius: 10, background: "var(--panel)", border: "1px solid var(--border)", marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 4 }}>Código del local</div>
              <div style={{ fontFamily: "monospace", fontSize: 22, fontWeight: 700, letterSpacing: 2, color: "var(--neon)" }}>
                URUKU-{comercio.codigo}
              </div>
              <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}>
                Escribiéndolo en un WhatsApp, sus ofertas caen en este comercio.
              </div>
            </div>
          )}

          {/* Confiable */}
          <label style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 0", borderBottom: "1px solid var(--border)", cursor: "pointer" }}>
            <input type="checkbox" checked={confiable} onChange={toggleConfiable} />
            <div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>Comercio confiable</div>
              <div style={{ fontSize: 12, color: "var(--txt-3)" }}>
                Lo que publique sale directo, sin pasar por moderación.
              </div>
            </div>
          </label>

          {/* Rubros: agregar y sacar de a un toque. Es el trabajo que hay que
              hacer comercio por comercio, así que no lleva botón de guardar. */}
          <div style={{ marginTop: 16, paddingBottom: 16, borderBottom: "1px solid var(--border)" }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Rubros</div>
            <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 10 }}>
              Tocá para agregar o sacar. El primero es el principal.
            </div>
            {misRubros === null ? (
              <div style={{ fontSize: 13, color: "var(--txt-3)" }}>Cargando…</div>
            ) : (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {rubros.map((r) => {
                  const puesto = misRubros.indexOf(r.slug);
                  return (
                    <button key={r.slug} type="button" onClick={() => toggleRubro(r.slug)}
                            style={{ padding: "5px 10px", borderRadius: 999, fontSize: 12,
                                     cursor: "pointer", border: "1px solid var(--border)",
                                     background: puesto >= 0 ? "var(--neon)" : "var(--panel)",
                                     color: puesto >= 0 ? "#000" : "var(--txt-2)",
                                     fontWeight: puesto === 0 ? 700 : 400 }}>
                      {puesto === 0 && "★ "}{r.nombre}
                    </button>
                  );
                })}
              </div>
            )}
            {misRubros?.length === 0 && (
              <div style={{ fontSize: 12, color: "var(--amber)", marginTop: 8 }}>
                Sin rubros: no va a aparecer en ningún filtro de categoría.
              </div>
            )}
            {errRubros && <div style={{ color: "salmon", fontSize: 12, marginTop: 6 }}>{errRubros}</div>}
          </div>

          {/* Grupo de WhatsApp: el canal por el que llegan las ofertas.
              Se ata solo cuando alguien manda URUKU-XXXX adentro del grupo;
              esto es para verlo, y para atarlo a mano si hizo falta rehacerlo. */}
          <div style={{ marginTop: 16, paddingBottom: 16, borderBottom: "1px solid var(--border)" }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Grupo de WhatsApp</div>
            <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 10 }}>
              El grupo del comercio con URUKU y el testigo. Lo que se manda ahí entra como oferta.
            </div>

            {grupos.length === 0 && (
              <div style={{ padding: "8px 0" }}>
                {/* El camino corto: el sistema crea el grupo y, como lo crea él,
                    sabe su identificador y lo ata en el mismo acto. Sin código,
                    sin que nadie escriba nada. */}
                <button className="btn btn-primary" style={{ width: "100%" }} onClick={crearGrupo}>
                  Crear el grupo de WhatsApp
                </button>
                <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 8, lineHeight: 1.45 }}>
                  Lo arma con {comercio.nombre} y los números de URUKU, y queda atado solo.
                  {" "}También se ata si alguien escribe{" "}
                  <span style={{ fontFamily: "monospace", color: "var(--neon)" }}>
                    URUKU-{comercio.codigo ?? "XXXX"}
                  </span>{" "}
                  adentro de un grupo ya existente.
                </div>
              </div>
            )}

            {grupos.map((g) => (
              <div key={g.grupo_jid}
                   style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 0" }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontFamily: "monospace", fontSize: 12, overflow: "hidden",
                                textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {g.nombre || g.grupo_jid}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--txt-3)" }}>
                    {g.origen === "codigo" ? "se ató con el código" : "atado a mano"}
                  </div>
                </div>
                <button onClick={() => soltar(g.grupo_jid)}
                        style={{ background: "none", border: "1px solid var(--border)",
                                 borderRadius: 8, padding: "4px 10px", fontSize: 12,
                                 color: "var(--txt-3)", cursor: "pointer" }}>
                  Soltar
                </button>
              </div>
            ))}

            <form onSubmit={atar} style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <input value={grupoNuevo} onChange={(e) => setGrupoNuevo(e.target.value)}
                     placeholder="1203630...@g.us"
                     style={{ flex: 1, minWidth: 0, padding: "8px 10px", borderRadius: 8,
                              border: "1px solid var(--border)", background: "var(--panel)",
                              color: "var(--txt-1)", fontSize: 13, fontFamily: "monospace" }} />
              <button type="submit" disabled={!grupoNuevo.trim()}
                      style={{ padding: "8px 14px", borderRadius: 8, border: "none",
                               background: "var(--neon)", color: "#000", fontSize: 13,
                               fontWeight: 600, cursor: "pointer" }}>
                Atar
              </button>
            </form>
            {errGrupo && <div style={{ color: "salmon", fontSize: 12, marginTop: 6 }}>{errGrupo}</div>}
          </div>

          {/* Números */}
          <div style={{ marginTop: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Números que pueden publicar</div>
            <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 10 }}>
              El número del local y el del empleado que manda las fotos pueden ser distintos.
              Cualquiera de estos identifica al comercio cuando escribe por WhatsApp.
            </div>

            {cargando && <div style={{ fontSize: 13, color: "var(--txt-3)" }}>Cargando…</div>}
            {!cargando && numeros.length === 0 && (
              <div style={{ fontSize: 13, color: "var(--amber)" }}>
                Ninguno. Si escribe por WhatsApp se va a crear un comercio nuevo duplicado.
              </div>
            )}
            {numeros.map((n) => (
              <div key={n.id} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--border)", fontSize: 13 }}>
                <span>+{n.numero}</span>
                <span style={{ color: "var(--txt-3)" }}>{n.etiqueta || "—"}</span>
              </div>
            ))}

            <form onSubmit={agregar} style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
              <input className="adm-input" value={nuevo} onChange={(e) => setNuevo(e.target.value)}
                placeholder="Número (ej: 70123456)" inputMode="tel" />
              <input className="adm-input" value={etiqueta} onChange={(e) => setEtiqueta(e.target.value)}
                placeholder="De quién es (ej: vendedora del local)" />
              <button type="submit" className="btn btn-primary btn-sm" disabled={!nuevo.trim()}>Autorizar número</button>
            </form>
          </div>

          {err && <div style={{ color: "var(--pink)", fontSize: 13, marginTop: 10 }}>{err}</div>}

          <button className="btn btn-ghost" style={{ width: "100%", marginTop: 18 }} onClick={onClose}>Cerrar</button>
        </div>
      </div>
    </Portal>
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
  // Resultado del pago: el backend avisa si el WhatsApp del comercio no sirve y
  // si le quedó cuenta para entrar al panel. Se muestra ANTES de cerrar, porque
  // es el único momento en que el admin está cara a cara con el dueño.
  const [resultado, setResultado] = useState<{ advertencias: string[]; login: boolean } | null>(null);

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    if (!monto || isNaN(Number(monto))) { setErr("Ingresá un monto válido"); return; }
    setSaving(true);
    try {
      const r = await registrarPago(comercio.id, {
        monto: Number(monto), moneda, metodo, meses: Number(meses),
        referencia: referencia || undefined, notas: notas || undefined,
      });
      setResultado({ advertencias: r?.advertencias ?? [], login: !!r?.login });
    } catch {
      setErr("No se pudo registrar el pago. Verificá el backend.");
    } finally {
      setSaving(false);
    }
  }

  if (resultado) {
    return (
      <Portal>
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
          <div className="glass" style={{ width: "100%", maxWidth: 420, borderRadius: 16, padding: 24 }}>
            <h3 style={{ marginBottom: 4 }}>Pago registrado ✓</h3>
            <p style={{ color: "var(--txt-3)", fontSize: 13, marginBottom: 18 }}>{comercio.nombre}</p>

            <div style={{ fontSize: 14, marginBottom: 12 }}>
              {resultado.login
                ? <span style={{ color: "var(--neon)" }}>✓ El comercio ya puede entrar al panel</span>
                : <span style={{ color: "var(--amber)" }}>⚠️ No se pudo crear la cuenta del panel</span>}
            </div>

            {resultado.advertencias.length > 0 && (
              <div style={{ border: "1px solid var(--amber)", borderRadius: 10, padding: 12, marginBottom: 14 }}>
                <div style={{ color: "var(--amber)", fontWeight: 600, fontSize: 13, marginBottom: 6 }}>
                  Revisá esto con el dueño ahora
                </div>
                {resultado.advertencias.map((a, i) => (
                  <div key={i} style={{ fontSize: 13, color: "var(--txt-2)" }}>· {a}</div>
                ))}
                <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 8 }}>
                  Sin un WhatsApp válido no le llegan las reservas de la tienda.
                </div>
              </div>
            )}

            <button className="btn btn-primary" style={{ width: "100%" }} onClick={onDone}>Listo</button>
          </div>
        </div>
      </Portal>
    );
  }

  return (
    <Portal>
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
    </Portal>
  );
}


/** Cuánto pesan las fotos, y el botón para achicar las que se fueron de rango.
 *
 * La medición va primero y el botón queda apagado hasta verla. Todo lo que
 * sube por el backend ya pasa por el procesador de imágenes, así que lo
 * probable es que las fotos estén bien y el peso esté en los videos —que se
 * guardan crudos, tal como salen del celular—. Apretar "reducir" sin haber
 * mirado sería trabajar sobre una suposición.
 */
function PanelPesoFotos() {
  const [peso, setPeso] = useState<PesoFotos | null>(null);
  const [midiendo, setMidiendo] = useState(false);
  const [maxKb, setMaxKb] = useState(250);
  const [corriendo, setCorriendo] = useState(false);
  const [res, setRes] = useState<ResultadoOptimizar | null>(null);
  const [err, setErr] = useState("");

  const mb = (b: number) => `${(b / 1024 / 1024).toFixed(1)} MB`;

  async function medir() {
    setMidiendo(true); setErr(""); setRes(null);
    try { setPeso(await getPesoFotos()); }
    catch { setErr("No se pudo medir. ¿El backend está arriba?"); }
    finally { setMidiendo(false); }
  }

  async function optimizar() {
    // Pisa el archivo original y no hay vuelta atrás: la confirmación dice
    // exactamente eso, no un "¿estás seguro?" que nadie lee.
    if (!confirm(`Se van a recomprimir las imágenes de más de ${maxKb} KB.

` +
                 `El archivo original se pierde: esto NO se puede deshacer.

¿Seguimos?`)) return;
    setCorriendo(true); setErr("");
    try {
      const r = await optimizarFotos(maxKb, 50);
      setRes(r);
      await medir();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "No se pudo optimizar");
    } finally { setCorriendo(false); }
  }

  return (
    <div className="panel-card glass">
      <div className="ph">
        <h3>Peso de las fotos</h3>
        <button className="btn btn-ghost btn-sm" onClick={medir} disabled={midiendo}>
          {midiendo ? "Midiendo…" : peso ? "Volver a medir" : "Medir"}
        </button>
      </div>

      {!peso && !midiendo && (
        <div style={{ padding: 20, color: "var(--txt-3)", fontSize: 13 }}>
          Recorre el disco de fotos y dice cuánto ocupa cada cosa. Puede tardar unos segundos.
        </div>
      )}

      {peso && peso.existe === false && (
        <div style={{ padding: 20, color: "var(--amber)", fontSize: 13 }}>
          No existe el directorio {peso.dir}. Si el backend está en otro contenedor, revisá el volumen.
        </div>
      )}

      {peso?.existe && (
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
            <div>
              <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Imágenes</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{mb(peso.imagenes?.bytes ?? 0)}</div>
              <div style={{ fontSize: 11, color: "var(--txt-3)" }}>
                {peso.imagenes?.n ?? 0} archivos · {peso.imagenes?.promedio_kb ?? 0} KB promedio
              </div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Videos (sin procesar)</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: (peso.videos?.bytes ?? 0) > (peso.imagenes?.bytes ?? 0) ? "var(--amber)" : undefined }}>
                {mb(peso.videos?.bytes ?? 0)}
              </div>
              <div style={{ fontSize: 11, color: "var(--txt-3)" }}>
                {peso.videos?.n ?? 0} archivos · {peso.videos?.promedio_kb ?? 0} KB promedio
              </div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Total en disco</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{mb(peso.bytes_total ?? 0)}</div>
            </div>
          </div>

          {/* Si el peso está en los videos, el botón de abajo no los toca y
              decirlo evita apretarlo esperando que resuelva algo. */}
          {(peso.videos?.bytes ?? 0) > (peso.imagenes?.bytes ?? 0) && (
            <div style={{ fontSize: 12.5, color: "var(--amber)", border: "1px solid var(--amber)",
                          borderRadius: 8, padding: "8px 12px" }}>
              El grueso del peso está en los videos, que se guardan crudos. Optimizar las
              imágenes no los toca: si hay que bajar el disco, es ahí donde hay que mirar.
            </div>
          )}

          {peso.imagenes && peso.imagenes.top.length > 0 && (
            <div>
              <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 6 }}>Las más pesadas</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                {peso.imagenes.top.slice(0, 8).map((f) => (
                  <div key={f.path} style={{ display: "flex", justifyContent: "space-between", gap: 10, fontSize: 12 }}>
                    <span style={{ color: "var(--txt-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.path}</span>
                    <b style={{ flexShrink: 0, color: f.kb > 400 ? "var(--amber)" : "var(--txt-2)" }}>{f.kb} KB</b>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div style={{ borderTop: "1px solid var(--border)", paddingTop: 14, display: "flex",
                        gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <label style={{ fontSize: 12, color: "var(--txt-3)" }}>
              Achicar las que pasen de
              <input className="adm-input" type="number" min={50} step={50} value={maxKb}
                     onChange={(e) => setMaxKb(Number(e.target.value) || 250)}
                     style={{ width: 90, marginLeft: 8 }} /> KB
            </label>
            <button className="btn btn-primary btn-sm" onClick={optimizar} disabled={corriendo}>
              {corriendo ? "Achicando…" : "Reducir peso"}
            </button>
            <span style={{ fontSize: 11.5, color: "var(--txt-3)" }}>
              De a 50 por vez · pisa el original, no se puede deshacer
            </span>
          </div>

          {res && (
            <div style={{ fontSize: 13 }}>
              Se achicaron <b>{res.optimizados}</b> de {res.revisados} · ahorro <b>{mb(res.ahorro_bytes)}</b>
              {res.restantes > 0 && (
                <span style={{ color: "var(--amber)" }}> · quedan {res.restantes}, volvé a apretar</span>
              )}
            </div>
          )}
          {err && <div style={{ color: "var(--pink)", fontSize: 13 }}>{err}</div>}
        </div>
      )}
    </div>
  );
}
