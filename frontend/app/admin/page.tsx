"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listPendientes, moderar, login, getToken, type PendingPub,
  listComerciosPorVerificar, verificarComercio, rechazarComercio, type ComercioPorVerificar,
} from "@/lib/api";
import { precioFmt, MODALIDAD_LABEL, comoLlegarHref } from "@/lib/types";
import { Check, X, Edit, Pin, WhatsApp, Verified } from "@/components/icons";

export default function AdminPage() {
  const [authed, setAuthed] = useState(false);
  const [email, setEmail] = useState("admin@bermejolive.com");
  const [pass, setPass] = useState("");
  const [err, setErr] = useState("");
  const [tab, setTab] = useState<"publicaciones" | "comercios">("publicaciones");
  const [items, setItems] = useState<PendingPub[]>([]);
  const [comercios, setComercios] = useState<ComercioPorVerificar[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getToken()) {
      setAuthed(true);
      load();
      loadComercios();
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
    } catch {
      setComercios([]);
    }
  }

  async function actComercio(id: string, accion: "verificar" | "rechazar") {
    setComercios((prev) => prev.filter((c) => c.id !== id)); // optimista
    try {
      accion === "verificar" ? await verificarComercio(id) : await rechazarComercio(id);
    } catch {
      loadComercios();
    }
  }

  async function doLogin(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      await login(email, pass);
      setAuthed(true);
      load();
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

      <div className="auth-tabs" style={{ maxWidth: 460, marginBottom: 18 }}>
        <button className={tab === "publicaciones" ? "active" : ""} onClick={() => setTab("publicaciones")}>
          Publicaciones {items.length > 0 && `(${items.length})`}
        </button>
        <button className={tab === "comercios" ? "active" : ""} onClick={() => setTab("comercios")}>
          Comercios por verificar {comercios.length > 0 && `(${comercios.length})`}
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
