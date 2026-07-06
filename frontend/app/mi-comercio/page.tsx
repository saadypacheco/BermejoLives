"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Nav } from "@/components/nav";
import {
  Send, Store, Phone, WhatsApp, Pin, Verified, Edit, Search, User,
  Instagram, Facebook, TikTok, Globe, Arrow,
} from "@/components/icons";

/* mini-íconos (los que no están en icons.tsx) — stroke 1.8, currentColor */
const ic = (d: string) => (p: { style?: React.CSSProperties }) => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={p.style}><path d={d} /></svg>
);
const Bell = ic("M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0");
const Chart = ic("M3 3v18h18M7 15l3-3 3 3 5-6");
const Chat = ic("M21 11.5a8.4 8.4 0 0 1-9 8.4 8.5 8.5 0 0 1-3.6-.8L3 21l1.9-5.4A8.4 8.4 0 1 1 21 11.5z");
const Gear = ic("M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 0 1-4 0v-.1A1.7 1.7 0 0 0 7 19.4l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 4.6 15H4a2 2 0 0 1 0-4h.1A1.7 1.7 0 0 0 6 8.3l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 11 4.6V4a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 2.9 1.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0 .3 1.9 1.7 1.7 0 0 0 1.5 1H20a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z");
const Ext = ic("M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14 21 3");
const Logout = ic("M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9");
const Tag = ic("M20.6 13.4 11 3.8H4v7l9.6 9.6a2 2 0 0 0 2.8 0l4.2-4.2a2 2 0 0 0 0-2.8zM7 7h.01");
import {
  comercioLogin, getComercioSession, clearComercio,
  getPerfil, updatePerfil, subirFotoPerfil, getSuscripcion, getMetricas, pagarSuscripcion,
  draftProducto, listProductos, crearProducto, borrarProducto, destacarProducto,
  getMensajes, marcarLeido,
  getMisPublicaciones, editarPublicacion, bajaPublicacion,
  type ComercioSession, type Perfil, type Suscripcion, type Metricas,
  type ProductoDraft, type ProductoRef, type Mensaje, type Publicacion,
} from "@/lib/comercio";
import { comprimirImagen } from "@/lib/imagen";
import { RUBROS } from "@/lib/types";
import { geoErrorMsg } from "@/lib/geo";

export default function MiComercioPage() {
  const [sess, setSess] = useState<ComercioSession | null>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => { setSess(getComercioSession()); setReady(true); }, []);

  if (!ready) return null;
  if (!sess) return <LoginGate onLogged={setSess} />;
  return <Panel sess={sess} onLogout={() => { clearComercio(); setSess(null); }} />;
}

/* --------------------------------- Login gate --------------------------------- */
function LoginGate({ onLogged }: { onLogged: (s: ComercioSession) => void }) {
  const [email, setEmail] = useState("");
  const [pass, setPass] = useState("");
  const [err, setErr] = useState("");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try { onLogged(await comercioLogin(email, pass)); }
    catch { setErr("Credenciales incorrectas."); }
  }
  return (
    <>
      <Nav mapOnly />
      <div className="wrap" style={{ maxWidth: 420, paddingTop: 56 }}>
        <span className="eyebrow"><span className="dot-live" /> Mi comercio</span>
        <h1 style={{ fontSize: 28, margin: "10px 0 6px" }}>Entrá a tu panel</h1>
        <p style={{ color: "var(--txt-3)", marginBottom: 20 }}>Gestioná tu comercio, ofertas y suscripción.</p>
        <form onSubmit={submit} className="glass" style={{ padding: 22, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <input className="adm-input" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
          <input className="adm-input" type="password" value={pass} onChange={(e) => setPass(e.target.value)} placeholder="Contraseña" />
          {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
          <button className="btn btn-primary" type="submit">Entrar</button>
          <small style={{ color: "var(--txt-3)" }}>
            ¿No tenés cuenta? <Link href="/autoregistro?modo=registro" style={{ color: "var(--neon)" }}>Creala acá</Link>.
          </small>
        </form>
      </div>
    </>
  );
}

/* =================================== Dashboard =================================== */
const Mail = ic("M3 6h18v12H3zM3 7l9 6 9-6");
const MODA_LABEL: Record<string, string> = { mayorista: "Mayorista", minorista: "Minorista", ambos: "Mayor y menor" };

type Vista = "inicio" | "editar" | "productos" | "ofertas" | "contactos" | "estadisticas" | "mensajes" | "suscripcion" | "config";
const TITULOS: Record<Vista, string> = {
  inicio: "Mi comercio", editar: "Editar mi comercio", productos: "Productos / Ofertas",
  ofertas: "Mis ofertas", contactos: "Contactos", estadisticas: "Estadísticas", mensajes: "Mensajes",
  suscripcion: "Suscripción", config: "Configuración",
};
const NAV_ITEMS: { v: Vista; label: string; Icon: any }[] = [
  { v: "inicio", label: "Mi comercio", Icon: Store },
  { v: "ofertas", label: "Mis ofertas", Icon: Tag },
  { v: "productos", label: "Productos", Icon: Send },
  { v: "contactos", label: "Contactos", Icon: Phone },
  { v: "estadisticas", label: "Estadísticas", Icon: Chart },
  { v: "mensajes", label: "Mensajes", Icon: Chat },
  { v: "config", label: "Configuración", Icon: Gear },
];

function Sidebar({ vista, setVista, sub, onLogout, noLeidos }: {
  vista: Vista; setVista: (v: Vista) => void; sub: Suscripcion | null; onLogout: () => void; noLeidos: number;
}) {
  const e = sub ? ESTADO[sub.estado] : null;
  return (
    <aside style={{ width: 244, flexShrink: 0, borderRight: "1px solid var(--stroke)", display: "flex", flexDirection: "column", padding: "22px 16px", position: "sticky", top: 0, height: "100vh" }}>
      <Link className="brand" href="/" style={{ marginBottom: 26, paddingLeft: 8 }}>
        <b>ENCON<i>TRALO</i></b><span>EN EL MAPA</span>
      </Link>
      <nav style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        {NAV_ITEMS.map((it) => {
          const active = vista === it.v || (it.v === "inicio" && vista === "editar");
          return (
            <button key={it.v} onClick={() => setVista(it.v)} style={{
              display: "flex", alignItems: "center", gap: 12, padding: "10px 12px", borderRadius: 10,
              background: active ? "rgba(57,255,158,.10)" : "transparent",
              color: active ? "var(--neon)" : "var(--txt-2)", fontWeight: 600, fontSize: 14.5, textAlign: "left",
            }}>
              <it.Icon style={{ width: 18, height: 18 }} />
              <span style={{ flex: 1 }}>{it.label}</span>
              {it.v === "mensajes" && noLeidos > 0 && <span style={{ background: "var(--neon)", color: "#04240f", borderRadius: 999, fontSize: 11, fontWeight: 800, padding: "1px 7px" }}>{noLeidos}</span>}
            </button>
          );
        })}
      </nav>
      <div style={{ flex: 1 }} />
      <div className="glass" style={{ padding: 14, borderRadius: 14, marginBottom: 8 }}>
        <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Plan actual</div>
        <div style={{ fontWeight: 800, color: e?.color ?? "var(--txt)", marginTop: 2 }}>● {e?.label ?? "—"}</div>
        <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 4 }}>{sub?.paga_hasta ? `vence ${sub.paga_hasta}` : "Sin pago registrado"}</div>
        <button className="btn btn-primary btn-sm" onClick={() => setVista("suscripcion")} style={{ width: "100%", marginTop: 10 }}>Ver planes</button>
      </div>
      <button onClick={onLogout} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", color: "var(--txt-2)", fontSize: 14 }}>
        <Logout style={{ width: 18, height: 18 }} /> Cerrar sesión
      </button>
    </aside>
  );
}

function Topbar({ titulo, noLeidos, onPublicar }: { titulo: string; noLeidos: number; onPublicar: () => void }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16, padding: "16px 26px", borderBottom: "1px solid var(--stroke)", position: "sticky", top: 0, background: "rgba(11,13,17,.78)", backdropFilter: "blur(10px)", zIndex: 4 }}>
      <h1 style={{ fontSize: 22, margin: 0, flex: 1 }}>{titulo}</h1>
      <div style={{ display: "flex", alignItems: "center", gap: 8, background: "var(--panel)", border: "1px solid var(--stroke)", borderRadius: 12, padding: "8px 12px", width: 220 }}>
        <Search style={{ width: 16, height: 16, color: "var(--txt-3)" }} />
        <input placeholder="Buscar…" style={{ background: "transparent", border: "none", outline: "none", color: "var(--txt)", fontSize: 14, width: "100%" }} />
      </div>
      <div style={{ position: "relative", color: "var(--txt-2)", padding: 6 }}>
        <Bell style={{ width: 20, height: 20 }} />
        {noLeidos > 0 && <span style={{ position: "absolute", top: 0, right: 0, background: "var(--neon)", color: "#04240f", borderRadius: 999, fontSize: 10, fontWeight: 800, padding: "0 5px" }}>{noLeidos}</span>}
      </div>
      <button className="btn btn-primary" onClick={onPublicar}>Publicar oferta <Send /></button>
    </div>
  );
}

function InfoRow({ label, value, Icon }: { label: string; value?: string | null; Icon: any }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 0", borderBottom: "1px solid var(--stroke)" }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, color: "var(--txt-3)" }}>{label}</div>
        <div style={{ fontSize: 15, color: "var(--txt)", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis" }}>{value || "—"}</div>
      </div>
      <Icon style={{ width: 18, height: 18, color: "var(--txt-3)", flexShrink: 0 }} />
    </div>
  );
}

function MiniStat({ Icon, value, label, sub, color }: { Icon: any; value: React.ReactNode; label: string; sub?: string; color?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <span style={{ width: 42, height: 42, borderRadius: 12, background: "var(--panel)", display: "grid", placeItems: "center", color: color ?? "var(--txt-2)", flexShrink: 0 }}><Icon style={{ width: 20, height: 20 }} /></span>
      <div>
        <div style={{ fontSize: 22, fontWeight: 800, lineHeight: 1, color: color ?? "var(--txt)" }}>{value}</div>
        <div style={{ fontSize: 13, color: "var(--txt-2)" }}>{label}</div>
        {sub && <div style={{ fontSize: 11, color: "var(--txt-3)" }}>{sub}</div>}
      </div>
    </div>
  );
}

function Overview({ onEditar, onProductos, onPlanes }: { onEditar: () => void; onProductos: () => void; onPlanes: () => void }) {
  const [p, setP] = useState<Perfil | null>(null);
  const [m, setM] = useState<Metricas | null>(null);
  const [sub, setSub] = useState<Suscripcion | null>(null);
  const [noLeidos, setNoLeidos] = useState(0);
  useEffect(() => {
    getPerfil().then(setP).catch(() => {});
    getMetricas().then(setM).catch(() => {});
    getSuscripcion().then(setSub).catch(() => {});
    getMensajes().then((r) => setNoLeidos(r.no_leidos)).catch(() => {});
  }, []);
  if (!p) return <p style={{ color: "var(--txt-3)" }}>Cargando…</p>;
  const e = sub ? ESTADO[sub.estado] : null;
  const wa = (p.whatsapp ?? "").replace(/\D/g, "");
  const maps = p.como_llegar ?? (p.direccion ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(p.direccion)}` : "#");
  const redes = [
    p.instagram_url && { label: "Instagram", href: p.instagram_url, Icon: Instagram },
    p.facebook_url && { label: "Facebook", href: p.facebook_url, Icon: Facebook },
    p.tiktok_url && { label: "TikTok", href: p.tiktok_url, Icon: TikTok },
    p.sitio_web && { label: "Sitio / Página", href: p.sitio_web, Icon: Globe },
  ].filter(Boolean) as { label: string; href: string; Icon: any }[];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* HERO */}
      <div className="glass" style={{ padding: 22, borderRadius: 18, display: "flex", gap: 20, flexWrap: "wrap" }}>
        {(p.portada_url || p.logo_url)
          ? <img src={(p.portada_url || p.logo_url) as string} alt="" style={{ width: 150, height: 130, borderRadius: 14, objectFit: "cover", flexShrink: 0 }} />
          : <div style={{ width: 150, height: 130, borderRadius: 14, background: "rgba(57,255,158,.12)", display: "grid", placeItems: "center", color: "var(--neon)", fontSize: 42, fontWeight: 800, flexShrink: 0 }}>{(p.nombre || "?").charAt(0)}</div>}
        <div style={{ flex: 1, minWidth: 240 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
            <div>
              {p.verificado && <span style={{ background: "rgba(57,255,158,.14)", color: "var(--neon)", fontSize: 12, fontWeight: 700, padding: "3px 9px", borderRadius: 999 }}>Verificado</span>}
              <h2 style={{ fontSize: 26, margin: "8px 0 6px" }}>{p.nombre}</h2>
              <span style={{ background: "rgba(91,157,255,.12)", color: "var(--blue-soft)", fontSize: 12, fontWeight: 700, padding: "3px 10px", borderRadius: 999 }}>{MODA_LABEL[p.modalidad ?? "mayorista"]}</span>
            </div>
            <div style={{ display: "flex", gap: 8, alignSelf: "flex-start" }}>
              <button className="btn" onClick={onEditar} style={{ border: "1px solid var(--stroke)", whiteSpace: "nowrap" }}><Edit style={{ width: 15, height: 15 }} /> Editar información</button>
              <Link href="/autoregistro" className="btn btn-primary" style={{ whiteSpace: "nowrap" }}><Send style={{ width: 15, height: 15 }} /> Publicar servicio/oferta</Link>
            </div>
          </div>
          <p style={{ color: "var(--txt-2)", margin: "12px 0", maxWidth: 560 }}>{p.descripcion}</p>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {wa && <a className="btn btn-primary" href={`https://wa.me/${wa}`} target="_blank" rel="noopener"><WhatsApp style={{ width: 17, height: 17 }} /> WhatsApp</a>}
            <a className="btn" href={maps} target="_blank" rel="noopener" style={{ border: "1px solid var(--stroke)" }}><Pin style={{ width: 16, height: 16 }} /> Cómo llegar</a>
          </div>
        </div>
      </div>

      {/* GRID */}
      <div className="mc-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, alignItems: "start" }}>
        {/* IZQUIERDA */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div className="glass" style={{ padding: 20, borderRadius: 16 }}>
            <h3 style={{ margin: "0 0 6px" }}>Información de contacto</h3>
            <InfoRow label="WhatsApp" value={p.whatsapp} Icon={WhatsApp} />
            <InfoRow label="Teléfono" value={p.telefono} Icon={Phone} />
            <InfoRow label="Email" value={p.email} Icon={Mail} />
            <InfoRow label="Dirección" value={p.direccion} Icon={Pin} />
            <InfoRow label="Horario" value={p.horario} Icon={ic("M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z")} />
          </div>
          <div className="glass" style={{ padding: 20, borderRadius: 16 }}>
            <h3 style={{ margin: "0 0 6px" }}>Redes y links</h3>
            {redes.length === 0 && <p style={{ color: "var(--txt-3)", fontSize: 13 }}>Todavía no cargaste redes. <button onClick={onEditar} style={{ color: "var(--neon)" }}>Agregar</button></p>}
            {redes.map((r) => (
              <a key={r.label} href={r.href} target="_blank" rel="noopener" style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 0", borderBottom: "1px solid var(--stroke)", color: "inherit" }}>
                <r.Icon style={{ width: 18, height: 18, color: "var(--txt-3)", flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: "var(--txt-3)" }}>{r.label}</div>
                  <div style={{ fontSize: 14, color: "var(--blue-soft)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.href.replace(/^https?:\/\//, "")}</div>
                </div>
                <Ext style={{ width: 16, height: 16, color: "var(--txt-3)", flexShrink: 0 }} />
              </a>
            ))}
          </div>
        </div>

        {/* DERECHA */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div className="glass" style={{ padding: 20, borderRadius: 16 }}>
            <h3 style={{ margin: "0 0 14px" }}>Resumen de actividad</h3>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
              <MiniStat Icon={WhatsApp} color="var(--neon)" value={m?.contactos_30d ?? "–"} label="Contactos" sub="Últimos 30 días" />
              <MiniStat Icon={Store} value={m?.publicaciones_total ?? "–"} label="Publicaciones" sub="Activas" />
              <MiniStat Icon={Chat} value={noLeidos} label="Mensajes" sub="Sin leer" />
            </div>
          </div>

          <div className="glass" style={{ padding: 20, borderRadius: 16 }}>
            <h3 style={{ margin: "0 0 10px" }}>Estado de suscripción</h3>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10 }}>
              <div>
                <div style={{ fontSize: 18, fontWeight: 800, color: e?.color ?? "var(--txt)" }}>● {e?.label ?? "—"}</div>
                <div style={{ fontSize: 13, color: "var(--txt-3)", marginTop: 4 }}>{sub?.paga_hasta ? `Vence el ${sub.paga_hasta}` : "Todavía no registramos un pago."}</div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 13, color: "var(--txt-3)" }}>Plan {sub?.plan ?? "—"}</div>
                <button className="btn btn-primary btn-sm" onClick={onPlanes} style={{ marginTop: 8 }}>Ver planes</button>
              </div>
            </div>
          </div>

          <div className="glass" style={{ padding: 20, borderRadius: 16, display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ flex: 1 }}>
              <h3 style={{ margin: "0 0 6px" }}>Tus productos / ofertas</h3>
              <p style={{ color: "var(--txt-2)", fontSize: 14, margin: "0 0 12px" }}>Mostrá tus productos y ofertas para que más personas te encuentren.</p>
              <button className="btn btn-primary btn-sm" onClick={onProductos}><Store style={{ width: 15, height: 15 }} /> Ver mis productos</button>
            </div>
            <div style={{ fontSize: 46 }}>🛍️</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ContactosView() {
  const [p, setP] = useState<Perfil | null>(null);
  const [m, setM] = useState<Metricas | null>(null);
  useEffect(() => {
    getPerfil().then(setP).catch(() => {});
    getMetricas().then(setM).catch(() => {});
  }, []);
  if (!p) return <p style={{ color: "var(--txt-3)" }}>Cargando…</p>;
  const tipos = m ? Object.entries(m.contactos_por_tipo) : [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="glass" style={{ padding: 22, borderRadius: 16 }}>
        <h3 style={{ marginTop: 0 }}>Cómo te contactan los clientes</h3>
        <InfoRow label="WhatsApp" value={p.whatsapp} Icon={WhatsApp} />
        <InfoRow label="Teléfono" value={p.telefono} Icon={Phone} />
        <InfoRow label="Email" value={p.email} Icon={Mail} />
        <InfoRow label="Dirección" value={p.direccion} Icon={Pin} />
        <InfoRow label="Horario" value={p.horario} Icon={ic("M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z")} />
      </div>
      <div className="glass" style={{ padding: 22, borderRadius: 16 }}>
        <h3 style={{ marginTop: 0 }}>Quién te contactó · últimos 30 días</h3>
        <Stat color="var(--neon)" value={m?.contactos_30d ?? "–"} label="contactos por la app" />
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 14 }}>
          {tipos.length === 0
            ? <span style={{ color: "var(--txt-3)", fontSize: 14 }}>Todavía nadie te contactó por la app.</span>
            : tipos.map(([t, n]) => <span key={t} style={{ color: "var(--txt-2)", fontSize: 14 }}>{TIPO_LABEL[t] ?? t}: <b>{n}</b></span>)}
        </div>
      </div>
    </div>
  );
}

function ConfiguracionView() {
  return (
    <div className="glass" style={{ padding: 22, borderRadius: 16 }}>
      <h3 style={{ marginTop: 0 }}>Configuración</h3>
      <p style={{ color: "var(--txt-3)", fontSize: 14 }}>Próximamente: cambiar email y contraseña, notificaciones y dar de baja la cuenta.</p>
    </div>
  );
}

/* --------------------------------- Mis ofertas --------------------------------- */
const PUB_ESTADO: Record<string, { label: string; color: string }> = {
  aprobado: { label: "En vivo", color: "var(--neon)" },
  pendiente: { label: "En revisión", color: "var(--amber)" },
  cambios: { label: "Pide cambios", color: "var(--amber)" },
  rechazado: { label: "Rechazada", color: "var(--pink)" },
};

function OfertasTab() {
  const [items, setItems] = useState<Publicacion[] | null>(null);
  const [editing, setEditing] = useState<Publicacion | null>(null);
  const [err, setErr] = useState("");

  const cargar = () => getMisPublicaciones().then((r) => setItems(r.items)).catch((e) => setErr(e.message));
  useEffect(() => { cargar(); }, []);

  async function eliminar(id: string) {
    if (!window.confirm("¿Eliminar esta publicación? No se puede deshacer.")) return;
    try { await bajaPublicacion(id); cargar(); } catch (e) { setErr(e instanceof Error ? e.message : "Error"); }
  }

  if (editing) return <OfertaEditForm pub={editing} onCancel={() => setEditing(null)} onSaved={() => { setEditing(null); cargar(); }} />;
  if (items === null) return <p style={{ color: "var(--txt-3)" }}>Cargando…</p>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <p style={{ color: "var(--txt-3)", margin: 0, fontSize: 14 }}>Tus ofertas, videos y novedades. Editá precio, descuento o vencimiento.</p>
        <Link href="/autoregistro" className="btn btn-primary btn-sm">Nueva oferta <Send /></Link>
      </div>
      {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
      {items.length === 0 && <p style={{ color: "var(--txt-3)" }}>Todavía no publicaste ofertas. Creá una desde “Nueva oferta”.</p>}
      {items.map((it) => {
        const e = PUB_ESTADO[it.estado] ?? { label: it.estado, color: "var(--txt-3)" };
        return (
          <div key={it.id} className="glass" style={{ padding: 14, borderRadius: 14, display: "flex", gap: 14, alignItems: "center" }}>
            <div style={{ width: 64, height: 64, borderRadius: 12, overflow: "hidden", background: "var(--panel)", flexShrink: 0, display: "grid", placeItems: "center", position: "relative" }}>
              {it.imagen_url ? <img src={it.imagen_url} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : <span style={{ fontSize: 24 }}>🏷️</span>}
              {it.descuento_pct != null && <span style={{ position: "absolute", top: 4, left: 4, background: "var(--neon)", color: "#04240f", fontSize: 10, fontWeight: 800, padding: "1px 5px", borderRadius: 6 }}>-{it.descuento_pct}%</span>}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 700, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{it.titulo ?? "(sin título)"}</div>
              <div style={{ fontSize: 13, color: "var(--txt-3)", marginTop: 2 }}>
                {it.precio != null ? `${it.moneda ?? ""} ${it.precio}` : "Sin precio"}{it.vence_el ? ` · vence ${it.vence_el}` : ""}
              </div>
              <span style={{ color: e.color, fontSize: 12, fontWeight: 700 }}>● {e.label}</span>
            </div>
            <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
              <button className="btn btn-sm" style={{ border: "1px solid var(--stroke)" }} onClick={() => setEditing(it)}><Edit style={{ width: 14, height: 14 }} /> Editar</button>
              <button className="btn btn-sm" style={{ border: "1px solid var(--stroke)", color: "var(--pink)" }} onClick={() => eliminar(it.id)}>Eliminar</button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function OfertaEditForm({ pub, onCancel, onSaved }: { pub: Publicacion; onCancel: () => void; onSaved: () => void }) {
  const [titulo, setTitulo] = useState(pub.titulo ?? "");
  const [descripcion, setDescripcion] = useState(pub.descripcion ?? "");
  const [precio, setPrecio] = useState(pub.precio != null ? String(pub.precio) : "");
  const [moneda, setMoneda] = useState(pub.moneda ?? "BOB");
  const [descuento, setDescuento] = useState(pub.descuento_pct != null ? String(pub.descuento_pct) : "");
  const [vence, setVence] = useState(pub.vence_el ?? "");
  const [imagen, setImagen] = useState(pub.imagen_url ?? "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const esOferta = pub.tipo === "oferta";

  async function guardar() {
    setSaving(true); setErr("");
    try {
      await editarPublicacion(pub.id, {
        titulo: titulo.trim() || null,
        descripcion: descripcion.trim() || null,
        precio: precio ? Number(precio) : null,
        moneda,
        imagen_url: imagen.trim() || null,
        descuento_pct: esOferta && descuento ? Math.max(1, Math.min(99, Number(descuento))) : null,
        vence_el: esOferta && vence ? vence : null,
      });
      onSaved();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Error al guardar");
      setSaving(false);
    }
  }

  return (
    <div className="glass" style={{ padding: 20, borderRadius: 16, maxWidth: 560, display: "flex", flexDirection: "column", gap: 12 }}>
      <button className="btn btn-sm" onClick={onCancel} style={{ alignSelf: "flex-start", border: "1px solid var(--stroke)" }}><Arrow style={{ width: 14, height: 14, transform: "rotate(180deg)" }} /> Volver</button>
      <h3 style={{ margin: 0 }}>Editar publicación</h3>
      <input className="adm-input" value={titulo} onChange={(e) => setTitulo(e.target.value)} placeholder="Título" />
      <textarea className="adm-input" rows={3} value={descripcion} onChange={(e) => setDescripcion(e.target.value)} placeholder="Descripción" style={{ resize: "vertical" }} />
      {esOferta && (
        <>
          <div style={{ display: "flex", gap: 10 }}>
            <input className="adm-input" type="number" inputMode="numeric" value={precio} onChange={(e) => setPrecio(e.target.value)} placeholder="Precio" style={{ flex: 2 }} />
            <select className="adm-input" value={moneda} onChange={(e) => setMoneda(e.target.value)} style={{ flex: 1 }}>
              <option value="BOB">Bs</option><option value="USD">USD</option><option value="ARS">$ ARS</option>
            </select>
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <div style={{ flex: 1 }}>
              <label className="campo-lbl">Descuento %</label>
              <input className="adm-input" type="number" inputMode="numeric" min={1} max={99} value={descuento} onChange={(e) => setDescuento(e.target.value)} placeholder="ej: 20 (opcional)" />
            </div>
            <div style={{ flex: 1 }}>
              <label className="campo-lbl">Válido hasta</label>
              <input className="adm-input" type="date" value={vence} onChange={(e) => setVence(e.target.value)} />
            </div>
          </div>
        </>
      )}
      <input className="adm-input" value={imagen} onChange={(e) => setImagen(e.target.value)} placeholder="Link de imagen (opcional)" />
      {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
      <div style={{ display: "flex", gap: 10 }}>
        <button className="btn btn-primary" onClick={guardar} disabled={saving}>{saving ? "Guardando…" : "Guardar cambios"}</button>
        <button className="btn btn-ghost" onClick={onCancel} disabled={saving}>Cancelar</button>
      </div>
      <small style={{ color: "var(--txt-3)" }}>Si tu comercio no es confiable, los cambios vuelven a revisión antes de publicarse.</small>
    </div>
  );
}

function Panel({ sess, onLogout }: { sess: ComercioSession; onLogout: () => void }) {
  const [vista, setVista] = useState<Vista>("inicio");
  const [sub, setSub] = useState<Suscripcion | null>(null);
  const [noLeidos, setNoLeidos] = useState(0);
  useEffect(() => {
    getSuscripcion().then(setSub).catch(() => {});
    getMensajes().then((r) => setNoLeidos(r.no_leidos)).catch(() => {});
  }, [vista]);

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <Sidebar vista={vista} setVista={setVista} sub={sub} onLogout={onLogout} noLeidos={noLeidos} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <Topbar titulo={TITULOS[vista]} noLeidos={noLeidos} onPublicar={() => setVista("productos")} />
        <div style={{ padding: "24px 26px", maxWidth: 1120 }}>
          {vista === "inicio" && <Overview onEditar={() => setVista("editar")} onProductos={() => setVista("productos")} onPlanes={() => setVista("suscripcion")} />}
          {vista === "editar" && <div style={{ maxWidth: 720 }}><button className="btn" onClick={() => setVista("inicio")} style={{ border: "1px solid var(--stroke)", marginBottom: 14 }}><Arrow style={{ width: 15, height: 15, transform: "rotate(180deg)" }} /> Volver</button><PerfilTab /></div>}
          {vista === "ofertas" && <div style={{ maxWidth: 780 }}><OfertasTab /></div>}
          {vista === "productos" && <div style={{ maxWidth: 780 }}><ProductosTab /></div>}
          {vista === "contactos" && <div style={{ maxWidth: 720 }}><ContactosView /></div>}
          {vista === "estadisticas" && <div style={{ maxWidth: 720 }}><EstadisticasView /></div>}
          {vista === "mensajes" && <div style={{ maxWidth: 760 }}><MensajesTab /></div>}
          {vista === "suscripcion" && <div style={{ maxWidth: 620 }}><SuscripcionTab /></div>}
          {vista === "config" && <div style={{ maxWidth: 620 }}><ConfiguracionView /></div>}
        </div>
      </div>
    </div>
  );
}

/* --------------------------------- Perfil tab --------------------------------- */
const CONTACTO: { k: keyof Perfil; label: string; ph: string }[] = [
  { k: "whatsapp", label: "WhatsApp", ph: "59170000000" },
  { k: "telefono", label: "Teléfono", ph: "Agregar" },
  { k: "email", label: "Email", ph: "Agregar" },
  { k: "direccion", label: "Dirección", ph: "Agregar" },
  { k: "horario", label: "Horario", ph: "Lun a Sáb 9–19" },
];
const REDES: { k: keyof Perfil; label: string; ph: string }[] = [
  { k: "instagram_url", label: "Instagram", ph: "instagram.com/tucomercio" },
  { k: "facebook_url", label: "Facebook", ph: "facebook.com/tucomercio" },
  { k: "tiktok_url", label: "TikTok", ph: "tiktok.com/@tucomercio" },
  { k: "sitio_web", label: "Sitio / otra página", ph: "tusitio.com" },
];
const EDITABLES: (keyof Perfil)[] = [
  "nombre", "descripcion", "modalidad",
  ...CONTACTO.map((c) => c.k), ...REDES.map((r) => r.k),
];
const MODALIDAD_OPT: { v: string; t: string }[] = [
  { v: "mayorista", t: "Mayorista" }, { v: "minorista", t: "Minorista" }, { v: "ambos", t: "Mayor y menor" },
];

function ChipToggle({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} style={{
      padding: "6px 12px", borderRadius: 20, fontSize: 13, border: "1px solid",
      borderColor: active ? "var(--neon)" : "var(--stroke)",
      background: active ? "rgba(57,255,158,.12)" : "transparent",
      color: active ? "var(--neon)" : "var(--txt-2)", cursor: "pointer",
    }}>
      {label}
    </button>
  );
}

// Fila editable estilo lista (no caja de formulario)
function CampoRow({ label, value, onChange, ph }: {
  label: string; value: string; onChange: (v: string) => void; ph: string;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "11px 2px", borderBottom: "1px solid var(--stroke)" }}>
      <span style={{ width: 92, flexShrink: 0, fontSize: 13, color: "var(--txt-3)" }}>{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={ph}
        style={{ flex: 1, background: "transparent", border: "none", outline: "none", color: "var(--txt)", fontSize: 15, minWidth: 0 }} />
    </div>
  );
}

function PerfilTab() {
  const [perfil, setPerfil] = useState<Perfil | null>(null);
  const [rubroSlugs, setRubroSlugs] = useState<string[]>([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [saving, setSaving] = useState(false);

  const [subiendoFoto, setSubiendoFoto] = useState(false);
  const [fotoErr, setFotoErr] = useState("");

  const [geoMsg, setGeoMsg] = useState("");
  const [ubicando, setUbicando] = useState(false);

  useEffect(() => {
    getPerfil().then((p) => { setPerfil(p); setRubroSlugs(p.rubro_slugs ?? []); }).catch((e) => setErr(e.message));
  }, []);
  const set = (k: keyof Perfil, v: string) => setPerfil((p) => (p ? { ...p, [k]: v } : p));

  // Lo que falta completar (todo opcional, pero se lo mostramos como pendiente).
  const faltantes = perfil ? [
    !perfil.portada_url && "Foto del negocio",
    !(perfil.lat && perfil.lng) && "Ubicación",
    rubroSlugs.length === 0 && "Categoría",
    !perfil.email && "Email",
    !perfil.direccion && "Dirección",
    !perfil.horario && "Horario",
    ![perfil.instagram_url, perfil.facebook_url, perfil.tiktok_url, perfil.sitio_web].some(Boolean) && "Redes sociales",
  ].filter(Boolean) as string[] : [];

  async function guardar() {
    if (!perfil) return;
    setSaving(true); setErr(""); setMsg("");
    try {
      const patch: Record<string, unknown> = Object.fromEntries(EDITABLES.map((k) => [k, perfil[k] ?? ""]));
      if (perfil.lat != null) patch.lat = perfil.lat;
      if (perfil.lng != null) patch.lng = perfil.lng;
      patch.rubro_slugs = rubroSlugs;
      const upd = await updatePerfil(patch);
      setPerfil(upd); setRubroSlugs(upd.rubro_slugs ?? rubroSlugs); setMsg("Guardado ✓");
      setTimeout(() => setMsg(""), 2500);
    } catch (e) { setErr(e instanceof Error ? e.message : "No se pudo guardar"); }
    finally { setSaving(false); }
  }

  async function onFoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    if (!file) return;
    setFotoErr(""); setSubiendoFoto(true);
    try {
      const comprimida = await comprimirImagen(file);
      const upd = await subirFotoPerfil(comprimida);
      setPerfil(upd);
    } catch (ex) { setFotoErr(ex instanceof Error ? ex.message : "No se pudo subir la foto"); }
    finally { setSubiendoFoto(false); }
  }

  function ubicar() {
    setGeoMsg(""); setUbicando(true);
    if (!navigator.geolocation) { setGeoMsg("Este dispositivo no tiene GPS disponible."); setUbicando(false); return; }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setPerfil((p) => (p ? { ...p, lat: pos.coords.latitude, lng: pos.coords.longitude } : p));
        setUbicando(false);
      },
      (e) => { setGeoMsg(geoErrorMsg(e)); setUbicando(false); },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  if (err && !perfil) return <p style={{ color: "var(--pink)" }}>{err}</p>;
  if (!perfil) return <p style={{ color: "var(--txt-3)" }}>Cargando…</p>;
  const inicial = (perfil.nombre || "?").trim().charAt(0).toUpperCase();
  const foto = perfil.portada_url || perfil.logo_url;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {!perfil.verificado && (
        <div style={{ fontSize: 13, color: "var(--amber)", background: "rgba(255,176,32,.08)", padding: "8px 12px", borderRadius: 10 }}>
          Tu comercio está <b>pendiente de verificación</b>. Mientras tanto tus ofertas pasan por moderación.
        </div>
      )}
      {faltantes.length > 0 && (
        <div style={{ fontSize: 13, color: "var(--blue-soft)", background: "rgba(91,157,255,.08)", padding: "10px 12px", borderRadius: 10 }}>
          Te falta completar (opcional, pero ayuda a que te encuentren más): <b>{faltantes.join(" · ")}</b>
        </div>
      )}

      {/* VIDRIERA — preview vivo, editás acá mismo */}
      <div>
        <div className="glass" style={{ padding: 20, borderRadius: 18, background: "linear-gradient(160deg, rgba(57,255,158,.06), transparent 60%)" }}>
          <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
            <label style={{ position: "relative", width: 58, height: 58, flexShrink: 0, cursor: "pointer" }}>
              {foto
                ? <img src={foto} alt="" style={{ width: 58, height: 58, borderRadius: 16, objectFit: "cover" }} />
                : <div style={{ width: 58, height: 58, borderRadius: 16, display: "grid", placeItems: "center", background: "rgba(57,255,158,.14)", color: "var(--neon)", fontSize: 26, fontWeight: 800 }}>{inicial}</div>}
              <div style={{ position: "absolute", inset: 0, borderRadius: 16, background: "rgba(0,0,0,.45)", display: "grid", placeItems: "center", opacity: subiendoFoto ? 1 : 0, transition: "opacity .15s" }}
                onMouseEnter={(e) => { if (!subiendoFoto) e.currentTarget.style.opacity = "1"; }}
                onMouseLeave={(e) => { if (!subiendoFoto) e.currentTarget.style.opacity = "0"; }}>
                <Edit style={{ width: 16, height: 16, color: "#fff" }} />
              </div>
              <input type="file" accept="image/*" hidden onChange={onFoto} disabled={subiendoFoto} />
            </label>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <input value={perfil.nombre ?? ""} onChange={(e) => set("nombre", e.target.value)} placeholder="Nombre de tu comercio"
                  style={{ flex: 1, background: "transparent", border: "none", outline: "none", color: "var(--txt)", fontSize: 22, fontWeight: 800, minWidth: 0 }} />
                {perfil.verificado && <span title="Verificado" style={{ color: "var(--neon)" }}>✔</span>}
              </div>
              <select value={perfil.modalidad ?? "mayorista"} onChange={(e) => set("modalidad", e.target.value)}
                style={{ marginTop: 6, background: "rgba(91,157,255,.12)", color: "var(--blue-soft)", border: "1px solid var(--stroke)", borderRadius: 999, padding: "3px 10px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                {MODALIDAD_OPT.map((m) => <option key={m.v} value={m.v}>{m.t}</option>)}
              </select>
            </div>
          </div>
          {subiendoFoto && <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 8 }}>Subiendo foto…</div>}
          {fotoErr && <div style={{ fontSize: 12, color: "var(--pink)", marginTop: 8 }}>{fotoErr}</div>}
          <textarea value={perfil.descripcion ?? ""} onChange={(e) => set("descripcion", e.target.value)} rows={2}
            placeholder="Contá qué vendés, en una línea o dos…"
            style={{ width: "100%", marginTop: 12, background: "transparent", border: "none", outline: "none", resize: "none", color: "var(--txt-2)", fontSize: 15, lineHeight: 1.5 }} />
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <span style={{ background: "rgba(57,255,158,.14)", color: "var(--neon)", padding: "6px 12px", borderRadius: 10, fontSize: 13, fontWeight: 700 }}>WhatsApp</span>
            <span style={{ background: "var(--panel)", color: "var(--txt-2)", padding: "6px 12px", borderRadius: 10, fontSize: 13, fontWeight: 700 }}>📍 Cómo llegar</span>
          </div>
        </div>
        <div style={{ fontSize: 12, color: "var(--txt-3)", textAlign: "center", marginTop: 8 }}>✎ Así te ven tus clientes — tocá la foto o el texto para editar</div>
      </div>

      {/* CATEGORÍA */}
      <div className="glass" style={{ padding: "14px 18px", borderRadius: 16 }}>
        <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700, marginBottom: 10 }}>CATEGORÍA</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {RUBROS.map((r) => (
            <ChipToggle key={r.slug} label={r.nombre} active={rubroSlugs.includes(r.slug)}
              onClick={() => setRubroSlugs((s) => s.includes(r.slug) ? s.filter((x) => x !== r.slug) : [...s, r.slug])} />
          ))}
        </div>
      </div>

      {/* UBICACIÓN */}
      <div className="glass" style={{ padding: "14px 18px", borderRadius: 16 }}>
        <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700, marginBottom: 10 }}>UBICACIÓN</div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <button type="button" className="btn btn-sm" style={{ border: "1px solid var(--stroke)" }} onClick={ubicar} disabled={ubicando}>
            {ubicando ? "Obteniendo…" : perfil.lat && perfil.lng ? "📍 Ubicación cargada — actualizar" : "📍 Usar mi ubicación actual"}
          </button>
          {perfil.lat && perfil.lng && (
            <a href={`https://www.google.com/maps/search/?api=1&query=${perfil.lat},${perfil.lng}`} target="_blank" rel="noopener" style={{ fontSize: 13, color: "var(--blue-soft)" }}>
              Ver en el mapa
            </a>
          )}
        </div>
        {geoMsg && <div style={{ fontSize: 12.5, color: "var(--amber)", marginTop: 6 }}>{geoMsg}</div>}
      </div>

      {/* CONTACTO */}
      <div className="glass" style={{ padding: "14px 18px", borderRadius: 16 }}>
        <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700, marginBottom: 2 }}>CÓMO TE CONTACTAN</div>
        {CONTACTO.map((c) => (
          <CampoRow key={c.k} label={c.label} ph={c.ph} value={(perfil[c.k] as string) ?? ""} onChange={(v) => set(c.k, v)} />
        ))}
      </div>

      {/* REDES */}
      <div className="glass" style={{ padding: "14px 18px", borderRadius: 16 }}>
        <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700, marginBottom: 2 }}>REDES Y LINKS</div>
        {REDES.map((r) => (
          <CampoRow key={r.k} label={r.label} ph={r.ph} value={(perfil[r.k] as string) ?? ""} onChange={(v) => set(r.k, v)} />
        ))}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <button className="btn btn-primary" onClick={guardar} disabled={saving}>{saving ? "Guardando…" : "Guardar cambios"}</button>
        <Link href="/autoregistro" className="btn" style={{ border: "1px solid var(--stroke)" }}><Send style={{ width: 15, height: 15 }} /> Publicar servicio/oferta</Link>
        {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
        {msg && <span style={{ color: "var(--neon)", fontSize: 13 }}>{msg}</span>}
      </div>
    </div>
  );
}

/* ------------------------------- Suscripción tab ------------------------------- */
const ESTADO: Record<Suscripcion["estado"], { label: string; color: string; bg: string }> = {
  gratis:     { label: "Plan gratis",  color: "var(--txt-2)", bg: "transparent" },
  activo:     { label: "Al día",       color: "var(--neon)",  bg: "rgba(57,255,158,.08)" },
  por_vencer: { label: "Por vencer",   color: "var(--amber)", bg: "rgba(255,176,32,.08)" },
  vencido:    { label: "Vencida",      color: "var(--pink)",  bg: "rgba(255,77,121,.08)" },
  suspendido: { label: "Suspendida",   color: "var(--pink)",  bg: "rgba(255,77,121,.08)" },
  sin_pago:   { label: "Sin pago aún", color: "var(--amber)", bg: "rgba(255,176,32,.08)" },
};

const QR_FIJOS = [
  { key: "bo", label: "Bolivia 🇧🇴", qr: "/qr-bolivia.png" },
  { key: "ar", label: "Argentina 🇦🇷", qr: "/qr-argentina.png" },
];

function SuscripcionTab() {
  const [sub, setSub] = useState<Suscripcion | null>(null);
  const [err, setErr] = useState("");
  // pago (inline, en la misma página)
  const [metodo, setMetodo] = useState("qr-bolivia");
  const [monto, setMonto] = useState("30000");
  const [moneda, setMoneda] = useState("ARS");
  const [referencia, setReferencia] = useState("");
  const [comprobante, setComprobante] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [pagoErr, setPagoErr] = useState("");
  const [enviado, setEnviado] = useState(false);

  function cargar() { getSuscripcion().then(setSub).catch((e) => setErr(e.message)); }
  useEffect(() => { cargar(); }, []);

  if (err) return <p style={{ color: "var(--pink)" }}>{err}</p>;
  if (!sub) return <p style={{ color: "var(--txt-3)" }}>Cargando…</p>;
  const e = ESTADO[sub.estado];
  const total = sub.total_cargos > 0 ? Number(monto || 0) + sub.total_cargos : Number(monto || 0);

  async function enviar() {
    if (!Number(monto)) { setPagoErr("Poné el monto que pagaste"); return; }
    setBusy(true); setPagoErr("");
    try {
      await pagarSuscripcion({ monto: Number(monto), moneda, metodo, referencia: referencia.trim() || undefined }, comprobante);
      setEnviado(true); cargar();
    } catch (ex) { setPagoErr(ex instanceof Error ? ex.message : "Error"); }
    finally { setBusy(false); }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* INDICADOR DE ESTADO */}
      <div className="glass" style={{ padding: 18, borderRadius: 16, background: e.bg, borderLeft: `3px solid ${e.color}`, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 800, color: e.color }}>● {e.label}</div>
          {sub.paga_hasta ? (
            <div style={{ color: "var(--txt-2)", fontSize: 14, marginTop: 4 }}>
              {sub.dias_restantes !== null && sub.dias_restantes >= 0
                ? <>Vence el <b>{sub.paga_hasta}</b> · faltan {sub.dias_restantes} días</>
                : <>Venció el <b>{sub.paga_hasta}</b></>}
            </div>
          ) : (
            <div style={{ color: "var(--txt-3)", fontSize: 14, marginTop: 4 }}>
              {sub.estado === "gratis" ? "Activá tu plan para aparecer y vender." : "Todavía no registramos un pago."}
            </div>
          )}
        </div>
        <span style={{ color: "var(--txt-3)", fontSize: 13, whiteSpace: "nowrap" }}>Plan {sub.plan}</span>
      </div>

      {/* RESUMEN DE CARGOS (solo si hay destacados pendientes) */}
      {sub.total_cargos > 0 && (
        <div className="glass" style={{ padding: "14px 18px", borderRadius: 16 }}>
          <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700, marginBottom: 6 }}>CARGOS PENDIENTES</div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14, color: "var(--txt-2)" }}>
            <span>{sub.cargos_pendientes.length} publicación(es) destacada(s)</span>
            <b style={{ color: "var(--amber)" }}>${sub.total_cargos.toLocaleString("es-AR")}</b>
          </div>
        </div>
      )}

      {/* PAGAR — todo en la misma página */}
      <div className="glass" style={{ padding: 20, borderRadius: 16, display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700 }}>PAGAR SUSCRIPCIÓN</div>

        {enviado ? (
          <div style={{ textAlign: "center", padding: "10px 0" }}>
            <div style={{ fontSize: 36 }}>📨</div>
            <h3 style={{ margin: "4px 0" }}>¡Comprobante enviado!</h3>
            <p style={{ color: "var(--txt-2)", fontSize: 14 }}>Lo revisamos y activamos tu suscripción en breve.</p>
            <button className="btn" onClick={() => { setEnviado(false); setComprobante(null); setReferencia(""); }} style={{ border: "1px solid var(--stroke)", marginTop: 10 }}>Cargar otro pago</button>
          </div>
        ) : (
          <>
            {/* Los DOS QR, siempre fijos */}
            <div style={{ display: "flex", gap: 16, justifyContent: "center", flexWrap: "wrap" }}>
              {QR_FIJOS.map((q) => (
                <div key={q.key} style={{ textAlign: "center" }}>
                  <img src={q.qr} alt={q.label} style={{ width: 150, height: 150, objectFit: "contain", borderRadius: 12, background: "#fff", padding: 8 }}
                    onError={(ev) => { (ev.target as HTMLImageElement).style.display = "none"; }} />
                  <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 4 }}>{q.label}</div>
                </div>
              ))}
            </div>
            <div style={{ fontSize: 13, color: "var(--txt-3)", textAlign: "center" }}>Escaneá el QR de tu país (o transferí), pagá y subí el comprobante.</div>

            <select className="adm-input" value={metodo} onChange={(ev) => setMetodo(ev.target.value)}>
              <option value="qr-bolivia">Pagué con QR Bolivia</option>
              <option value="qr-argentina">Pagué con QR Argentina</option>
              <option value="transferencia">Pagué por transferencia</option>
            </select>

            <div style={{ display: "flex", gap: 10 }}>
              <input className="adm-input" type="number" inputMode="numeric" value={monto} onChange={(ev) => setMonto(ev.target.value)} placeholder="Monto" style={{ flex: 2 }} />
              <select className="adm-input" value={moneda} onChange={(ev) => setMoneda(ev.target.value)} style={{ flex: 1 }}>
                {["ARS", "BOB", "USD"].map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            {sub.total_cargos > 0 && (
              <div style={{ fontSize: 13, color: "var(--txt-3)" }}>
                Suscripción + {sub.cargos_pendientes.length} destacado(s) = <b>{moneda} {total.toLocaleString("es-AR")}</b>
              </div>
            )}
            <input className="adm-input" value={referencia} onChange={(ev) => setReferencia(ev.target.value)} placeholder="N° de comprobante (opcional)" />

            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700 }}>FOTO DEL COMPROBANTE</span>
              <input className="adm-input" type="file" accept="image/*" onChange={(ev) => setComprobante(ev.target.files?.[0] ?? null)} />
            </label>

            {pagoErr && <span style={{ color: "var(--pink)", fontSize: 13 }}>{pagoErr}</span>}
            <button className="btn btn-primary" onClick={enviar} disabled={busy}>{busy ? "Enviando…" : "Enviar comprobante"}</button>
          </>
        )}
      </div>
    </div>
  );
}

/* ------------------------------- Resumen (header) ------------------------------ */
function Stat({ value, label, color }: { value: React.ReactNode; label: string; color?: string }) {
  return (
    <div>
      <div style={{ fontSize: 26, fontWeight: 800, lineHeight: 1, color: color ?? "var(--txt)" }}>{value}</div>
      <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 3 }}>{label}</div>
    </div>
  );
}

const TIPO_LABEL: Record<string, string> = { whatsapp: "WhatsApp", telefono: "Teléfono", email: "Email", web: "Web" };

function EstadisticasView() {
  const [m, setM] = useState<Metricas | null>(null);
  useEffect(() => { getMetricas().then(setM).catch(() => {}); }, []);
  if (!m) return <p style={{ color: "var(--txt-3)" }}>Cargando…</p>;
  const tipos = Object.entries(m.contactos_por_tipo);
  const estados = Object.entries(m.publicaciones_por_estado);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="glass" style={{ padding: 22, borderRadius: 16 }}>
        <h3 style={{ marginTop: 0 }}>Contactos · últimos 30 días</h3>
        <Stat color="var(--neon)" value={m.contactos_30d} label="contactos en total" />
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 14 }}>
          {tipos.length === 0
            ? <span style={{ color: "var(--txt-3)", fontSize: 14 }}>Todavía nadie te contactó por la app.</span>
            : tipos.map(([t, n]) => <span key={t} style={{ color: "var(--txt-2)", fontSize: 14 }}>{TIPO_LABEL[t] ?? t}: <b>{n}</b></span>)}
        </div>
      </div>
      <div className="glass" style={{ padding: 22, borderRadius: 16 }}>
        <h3 style={{ marginTop: 0 }}>Tus publicaciones</h3>
        <Stat value={m.publicaciones_total} label="publicaciones" />
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 14 }}>
          {estados.length === 0
            ? <span style={{ color: "var(--txt-3)", fontSize: 14 }}>Todavía no publicaste nada.</span>
            : estados.map(([s, n]) => <span key={s} style={{ color: "var(--txt-2)", fontSize: 14 }}>{s}: <b>{n}</b></span>)}
        </div>
      </div>
    </div>
  );
}

/* --------------------------------- Mensajes tab -------------------------------- */
function MensajesTab() {
  const [items, setItems] = useState<Mensaje[] | null>(null);
  const [err, setErr] = useState("");
  function cargar() { getMensajes().then((r) => setItems(r.items)).catch((e) => setErr(e.message)); }
  useEffect(() => { cargar(); }, []);

  async function leer(id: string) { try { await marcarLeido(id); cargar(); } catch { /* noop */ } }

  if (err) return <p style={{ color: "var(--pink)" }}>{err}</p>;
  if (!items) return <p style={{ color: "var(--txt-3)" }}>Cargando…</p>;
  if (items.length === 0) return <p style={{ color: "var(--txt-3)" }}>Todavía no tenés mensajes. Acá te llegan los avisos de Encontralo y las consultas de tus clientes.</p>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {items.map((m) => {
        const tel = (m.contacto ?? "").replace(/\D/g, "");
        return (
          <div key={m.id} className="glass" style={{ padding: 16, borderRadius: 14, borderLeft: m.leido ? "1px solid var(--stroke)" : "3px solid var(--neon)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
              <b>{m.autor === "admin" ? "📣 Encontralo" : (m.nombre || "Cliente")}{m.autor === "cliente" && m.contacto ? ` · ${m.contacto}` : ""}</b>
              <span style={{ fontSize: 12, color: "var(--txt-3)" }}>{new Date(m.created_at).toLocaleString("es-AR")}</span>
            </div>
            <p style={{ color: "var(--txt-2)", margin: "8px 0" }}>{m.cuerpo}</p>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {m.autor === "cliente" && tel.length >= 6 && (
                <a className="btn btn-sm" href={`https://wa.me/${tel}`} target="_blank" rel="noopener" style={{ border: "1px solid var(--wa)", color: "var(--wa)" }}>Responder por WhatsApp</a>
              )}
              {!m.leido && <button className="btn btn-sm" onClick={() => leer(m.id)} style={{ border: "1px solid var(--stroke)" }}>Marcar leído</button>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* -------------------------------- Productos tab -------------------------------- */
function ProductosTab() {
  const [items, setItems] = useState<ProductoRef[] | null>(null);
  const [err, setErr] = useState("");
  const [adding, setAdding] = useState(false);

  function cargar() { setErr(""); listProductos().then((r) => setItems(r.items)).catch((e) => setErr(e.message)); }
  useEffect(() => { cargar(); }, []);

  async function eliminar(id: string) {
    if (!window.confirm("¿Borrar este producto?")) return;
    try { await borrarProducto(id); cargar(); } catch (e) { setErr(e instanceof Error ? e.message : "Error"); }
  }

  async function destacar(id: string) {
    if (!window.confirm("Destacar este producto en el feed cuesta $1.000, que se suma a tu próxima factura. ¿Confirmás?")) return;
    try { await destacarProducto(id); cargar(); } catch (e) { setErr(e instanceof Error ? e.message : "Error"); }
  }

  if (adding) return <NuevoProducto onDone={() => { setAdding(false); cargar(); }} onCancel={() => setAdding(false)} />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <button className="btn btn-primary" onClick={() => setAdding(true)} style={{ alignSelf: "flex-start" }}>Publicar producto <Send /></button>
      {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
      {!items ? (
        <p style={{ color: "var(--txt-3)" }}>Cargando…</p>
      ) : items.length === 0 ? (
        <p style={{ color: "var(--txt-3)" }}>Todavía no cargaste productos. Sacá una foto, poné el precio y publicalo en segundos.</p>
      ) : (
        items.map((p) => (
          <div key={p.id} className="glass" style={{ padding: 14, borderRadius: 14, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
            <div>
              <div style={{ fontWeight: 700 }}>{p.titulo ?? "Producto"}</div>
              <div style={{ fontSize: 12, color: "var(--txt-3)" }}>
                {p.precio != null ? `${p.moneda ?? ""} ${p.precio}` : ""} · {p.estado}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {p.destacado_pub_id
                ? <span style={{ fontSize: 12, color: "var(--amber)", fontWeight: 700 }}>⭐ Destacado</span>
                : <button className="btn" onClick={() => destacar(p.id)} style={{ border: "1px solid var(--amber)", color: "var(--amber)" }}>Destacar $1.000</button>}
              {p.url && <a className="btn" href={p.url} target="_blank" rel="noopener" style={{ border: "1px solid var(--stroke)" }}>Ver</a>}
              <button className="btn" onClick={() => eliminar(p.id)} style={{ border: "1px solid var(--stroke)", color: "var(--pink)" }}>Borrar</button>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

const MONEDAS = ["ARS", "BOB", "USD"];

function NuevoProducto({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [fotos, setFotos] = useState<File[]>([]);
  const [titulo, setTitulo] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [precio, setPrecio] = useState("");
  const [moneda, setMoneda] = useState("ARS");
  const [draft, setDraft] = useState<ProductoDraft | null>(null);
  const [categoria, setCategoria] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const previews = useMemo(() => fotos.map((f) => URL.createObjectURL(f)), [fotos]);
  useEffect(() => () => previews.forEach((u) => URL.revokeObjectURL(u)), [previews]);

  function addFotos(list: FileList | null) {
    if (!list) return;
    setFotos((f) => [...f, ...Array.from(list)].slice(0, 3));
  }
  function quitarFoto(i: number) { setFotos((f) => f.filter((_, j) => j !== i)); }

  async function clasificar() {
    if (!titulo.trim()) { setErr("Poné un título"); return; }
    setBusy(true); setErr("");
    try {
      const d = await draftProducto({ titulo, descripcion, precio: precio ? Number(precio) : null, moneda });
      setDraft(d);
      setCategoria(d.categoria_slug ?? "");
    } catch (e) { setErr(e instanceof Error ? e.message : "Error"); }
    finally { setBusy(false); }
  }

  async function publicar() {
    if (!titulo.trim() || !precio || !categoria || fotos.length === 0) {
      setErr("Necesitás al menos 1 foto, título, precio y categoría."); return;
    }
    setBusy(true); setErr("");
    try {
      await crearProducto(
        { titulo: titulo.trim(), precio: Number(precio), moneda, categoria_slug: categoria, descripcion: descripcion.trim() || undefined },
        fotos,
      );
      onDone();
    } catch (e) { setErr(e instanceof Error ? e.message : "Error"); setBusy(false); }
  }

  return (
    <div className="glass" style={{ padding: 22, borderRadius: 16, display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <b>Nuevo producto</b>
        <button className="btn" onClick={onCancel} style={{ border: "1px solid var(--stroke)" }}>Cancelar</button>
      </div>

      <div>
        <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700, marginBottom: 6 }}>FOTOS (1 a 3)</div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {previews.map((u, i) => (
            <div key={i} style={{ position: "relative" }}>
              <img src={u} alt="" style={{ width: 72, height: 72, objectFit: "cover", borderRadius: 10 }} />
              <button onClick={() => quitarFoto(i)} aria-label="Quitar"
                style={{ position: "absolute", top: -6, right: -6, background: "var(--pink)", color: "#000", borderRadius: "50%", width: 20, height: 20, fontSize: 12, fontWeight: 800, lineHeight: 1 }}>×</button>
            </div>
          ))}
          {fotos.length < 3 && (
            <label className="adm-input" style={{ width: 72, height: 72, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", fontSize: 28, color: "var(--txt-3)" }}>
              +
              <input type="file" accept="image/*" multiple hidden onChange={(e) => addFotos(e.target.files)} />
            </label>
          )}
        </div>
      </div>

      <input className="adm-input" value={titulo} onChange={(e) => setTitulo(e.target.value)} placeholder="Título (ej: Campera de jean importada)" />
      <textarea className="adm-input" rows={3} value={descripcion} onChange={(e) => setDescripcion(e.target.value)} placeholder="Descripción (podés indicar los talles)" />
      <div style={{ display: "flex", gap: 10 }}>
        <input className="adm-input" type="number" inputMode="numeric" value={precio} onChange={(e) => setPrecio(e.target.value)} placeholder="Precio" style={{ flex: 2 }} />
        <select className="adm-input" value={moneda} onChange={(e) => setMoneda(e.target.value)} style={{ flex: 1 }}>
          {MONEDAS.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>

      {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}

      {!draft ? (
        <button className="btn btn-primary" onClick={clasificar} disabled={busy}>{busy ? "Clasificando…" : "Clasificar y ver preview"}</button>
      ) : (
        <>
          <div style={{ borderTop: "1px solid var(--stroke)", paddingTop: 12 }}>
            <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700, marginBottom: 6 }}>CATEGORÍA (la IA sugirió — podés cambiarla)</div>
            <select className="adm-input" value={categoria} onChange={(e) => setCategoria(e.target.value)}>
              {draft.categorias.map((c) => <option key={c.slug} value={c.slug}>{c.nombre}</option>)}
            </select>
          </div>
          <div className="glass" style={{ padding: 12, borderRadius: 12 }}>
            <div style={{ fontSize: 11, color: "var(--txt-3)", marginBottom: 6 }}>Así lo verá el comprador:</div>
            {previews[0] && <img src={previews[0]} alt="" style={{ width: "100%", maxHeight: 180, objectFit: "cover", borderRadius: 10 }} />}
            <div style={{ fontWeight: 700, marginTop: 8 }}>{titulo}</div>
            <div style={{ color: "var(--neon)", fontWeight: 800 }}>{moneda} {precio}</div>
            {descripcion && <div style={{ fontSize: 13, color: "var(--txt-2)", marginTop: 4 }}>{descripcion}</div>}
          </div>
          <button className="btn btn-primary" onClick={publicar} disabled={busy}>{busy ? "Publicando…" : "Publicar"}</button>
        </>
      )}
    </div>
  );
}
