"use client";

import { useEffect, useState } from "react";
import { crearAgente, editarAgente, getAgentes, type AgenteAdmin } from "@/lib/api";
import { getCiudades } from "@/lib/data";
import type { Ciudad } from "@/lib/types";

/**
 * Admin › Agentes: las cuentas de los que cargan comercios en la calle.
 *
 * Cada agente tiene SU ciudad, y lo que carga nace ahí sin que tenga que
 * elegirla en el formulario del celular: el que anda en Santa Cruz no puede
 * cargar medio día en Bermejo por un selector que quedó como estaba.
 *
 * La contraseña se escribe una sola vez y no se puede volver a ver (se guarda
 * cifrada). Si se pierde, se pone una nueva desde acá.
 */
export function AgentesPanel() {
  const [items, setItems] = useState<AgenteAdmin[]>([]);
  const [ciudades, setCiudades] = useState<Ciudad[]>([]);
  const [err, setErr] = useState("");
  const [nuevo, setNuevo] = useState({ email: "", password: "", nombre: "", ciudad_slug: "" });
  const [creando, setCreando] = useState(false);
  const [creado, setCreado] = useState<{ email: string; password: string } | null>(null);

  const cargar = () => getAgentes().then(setItems).catch((e) => setErr(e instanceof Error ? e.message : "No se pudo cargar"));
  useEffect(() => {
    cargar();
    getCiudades().then((cs) => setCiudades(cs.filter((c) => c.activa))).catch(() => {});
  }, []);

  async function crear() {
    setErr(""); setCreando(true);
    try {
      await crearAgente({ ...nuevo, nombre: nuevo.nombre || undefined, ciudad_slug: nuevo.ciudad_slug || undefined });
      setCreado({ email: nuevo.email.trim().toLowerCase(), password: nuevo.password });
      setNuevo({ email: "", password: "", nombre: "", ciudad_slug: "" });
      cargar();
    } catch (e) { setErr(e instanceof Error ? e.message : "No se pudo crear"); }
    finally { setCreando(false); }
  }

  return (
    <div style={{ display: "grid", gap: 16, maxWidth: 900 }}>
      <p style={{ margin: 0, fontSize: 13, opacity: .75 }}>
        Las cuentas de la <a href="/publicar" target="_blank" rel="noopener">app de campo</a>. Cada agente carga en
        <b> su ciudad</b>: lo que sube nace ahí, sin elegir nada. Se ve quién cargó cada comercio.
      </p>
      {err && <p style={{ color: "#c33", margin: 0 }}>{err}</p>}

      <div className="panel-card glass" style={{ padding: 16, display: "grid", gap: 10 }}>
        <b>Agregar un agente</b>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 10 }}>
          <label style={{ display: "grid", gap: 3, fontSize: 12 }}>
            <span style={{ opacity: .7 }}>Correo (con el que entra) *</span>
            <input className="adm-input" value={nuevo.email} onChange={(e) => setNuevo((s) => ({ ...s, email: e.target.value }))} placeholder="ana@uruku.bo" />
          </label>
          <label style={{ display: "grid", gap: 3, fontSize: 12 }}>
            <span style={{ opacity: .7 }}>Contraseña *</span>
            <input className="adm-input" value={nuevo.password} onChange={(e) => setNuevo((s) => ({ ...s, password: e.target.value }))} placeholder="mínimo 6 letras" />
          </label>
          <label style={{ display: "grid", gap: 3, fontSize: 12 }}>
            <span style={{ opacity: .7 }}>Nombre</span>
            <input className="adm-input" value={nuevo.nombre} onChange={(e) => setNuevo((s) => ({ ...s, nombre: e.target.value }))} placeholder="Ana" />
          </label>
          <label style={{ display: "grid", gap: 3, fontSize: 12 }}>
            <span style={{ opacity: .7 }}>Ciudad donde carga</span>
            <select className="adm-input" value={nuevo.ciudad_slug} onChange={(e) => setNuevo((s) => ({ ...s, ciudad_slug: e.target.value }))}>
              <option value="">— elegir —</option>
              {ciudades.map((c) => <option key={c.slug} value={c.slug}>{c.nombre}</option>)}
            </select>
          </label>
        </div>
        <div>
          <button className="btn btn-primary" onClick={crear} disabled={creando || !nuevo.email.trim() || nuevo.password.length < 6}>
            {creando ? "Creando…" : "Crear agente"}
          </button>
        </div>
        {creado && (
          <div style={{ fontSize: 13, background: "rgba(34,197,94,.12)", border: "1px solid var(--neon)", borderRadius: 10, padding: "10px 12px" }}>
            <b>Listo. Pasale estos datos al agente</b> — la contraseña no se puede volver a ver:
            <div style={{ marginTop: 6, fontFamily: "monospace", fontSize: 14 }}>
              uruku.bo/publicar<br />usuario: {creado.email}<br />contraseña: {creado.password}
            </div>
            <button className="btn btn-ghost btn-sm" style={{ marginTop: 8 }}
                    onClick={() => navigator.clipboard?.writeText(`App de carga: https://uruku.bo/publicar\nUsuario: ${creado.email}\nContraseña: ${creado.password}`)}>
              Copiar para mandar por WhatsApp
            </button>
          </div>
        )}
      </div>

      <div className="panel-card glass" style={{ padding: 16 }}>
        <b>Agentes</b>
        <div style={{ overflowX: "auto", marginTop: 8 }}>
          <table className="adm-table" style={{ fontSize: 13 }}>
            <thead><tr><th>Correo</th><th>Nombre</th><th>Ciudad</th><th>Último acceso</th><th></th></tr></thead>
            <tbody>
              {items.map((a) => <FilaAgente key={a.id} a={a} ciudades={ciudades} onCambio={cargar} />)}
              {items.length === 0 && <tr><td colSpan={5} style={{ opacity: .6 }}>Todavía no hay agentes cargados acá. La cuenta vieja del `.env` sigue funcionando.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function FilaAgente({ a, ciudades, onCambio }: { a: AgenteAdmin; ciudades: Ciudad[]; onCambio: () => void }) {
  const [clave, setClave] = useState("");
  const [ciudad, setCiudad] = useState(a.ciudad_slug ?? "");
  const [msg, setMsg] = useState("");

  async function guardar(patch: { activo?: boolean; password?: string; ciudad_slug?: string }) {
    setMsg("");
    try {
      await editarAgente(a.id, { email: a.email, activo: patch.activo ?? a.activo, ...patch });
      setClave(""); setMsg("✓"); onCambio();
    } catch (e) { setMsg(e instanceof Error ? e.message : "no se pudo"); }
  }

  return (
    <tr style={{ opacity: a.activo ? 1 : .5 }}>
      <td>{a.email}{!a.activo && " · apagado"}</td>
      <td>{a.nombre ?? "—"}</td>
      <td>
        <select className="adm-input" style={{ width: "auto", fontSize: 12 }} value={ciudad}
                onChange={(e) => { setCiudad(e.target.value); guardar({ ciudad_slug: e.target.value }); }}>
          <option value="">— sin ciudad —</option>
          {ciudades.map((c) => <option key={c.slug} value={c.slug}>{c.nombre}</option>)}
        </select>
      </td>
      <td style={{ fontSize: 12, opacity: .7 }}>{a.ultimo_acceso ? new Date(a.ultimo_acceso).toLocaleDateString() : "nunca entró"}</td>
      <td style={{ whiteSpace: "nowrap" }}>
        <input className="adm-input" style={{ width: 130, fontSize: 12, display: "inline-block" }} value={clave}
               onChange={(e) => setClave(e.target.value)} placeholder="clave nueva" />
        <button className="btn btn-ghost btn-sm" disabled={clave.length < 6} onClick={() => guardar({ password: clave })}>Cambiar</button>
        <button className="btn btn-ghost btn-sm" onClick={() => guardar({ activo: !a.activo })}>{a.activo ? "Apagar" : "Encender"}</button>
        {msg && <span style={{ fontSize: 12, marginLeft: 6 }}>{msg}</span>}
      </td>
    </tr>
  );
}
