"use client";

import { useEffect, useState } from "react";
import { crearUsuarioPanel, editarUsuarioPanel, getEquipo, guardarRol, borrarRol, type EquipoData, type UsuarioPanel, type RolAdmin } from "@/lib/api";
import { getCiudades } from "@/lib/data";
import type { Ciudad } from "@/lib/types";

/**
 * Admin › Equipo: quién entra, con qué rol, y qué puede hacer cada rol.
 *
 * Antes eran tres pares correo/clave en el `.env` del servidor, compartidos:
 * sumar a alguien era editar un archivo y reiniciar, y no se sabía quién hizo
 * qué. Ahora cada persona tiene su cuenta y sus roles, y los roles se arman
 * acá eligiendo permisos del catálogo (el catálogo lo define el código: un
 * tilde que no corresponde a ningún endpoint sería mentira).
 */
export function EquipoPanel() {
  const [data, setData] = useState<EquipoData | null>(null);
  const [ciudades, setCiudades] = useState<Ciudad[]>([]);
  const [err, setErr] = useState("");
  const [vista, setVista] = useState<"personas" | "roles">("personas");

  const cargar = () => getEquipo().then(setData).catch((e) => setErr(e instanceof Error ? e.message : "No se pudo cargar"));
  useEffect(() => {
    cargar();
    getCiudades().then((cs) => setCiudades(cs.filter((c) => c.activa))).catch(() => {});
  }, []);

  return (
    <div style={{ display: "grid", gap: 16, maxWidth: 980 }}>
      <div style={{ display: "flex", gap: 8 }}>
        <button className={`btn btn-sm ${vista === "personas" ? "btn-primary" : "btn-ghost"}`} onClick={() => setVista("personas")}>Personas</button>
        <button className={`btn btn-sm ${vista === "roles" ? "btn-primary" : "btn-ghost"}`} onClick={() => setVista("roles")}>Roles y permisos</button>
      </div>
      {err && <p style={{ color: "#c33", margin: 0 }}>{err}</p>}
      {data && vista === "personas" && <Personas data={data} ciudades={ciudades} onCambio={cargar} setErr={setErr} />}
      {data && vista === "roles" && <Roles data={data} onCambio={cargar} setErr={setErr} />}
    </div>
  );
}

function Personas({ data, ciudades, onCambio, setErr }: { data: EquipoData; ciudades: Ciudad[]; onCambio: () => void; setErr: (s: string) => void }) {
  const [nuevo, setNuevo] = useState({ email: "", password: "", nombre: "", ciudad_slug: "", roles: [] as string[] });
  const [creando, setCreando] = useState(false);
  const [creado, setCreado] = useState<{ email: string; password: string } | null>(null);

  async function crear() {
    setErr(""); setCreando(true);
    try {
      await crearUsuarioPanel({ ...nuevo, nombre: nuevo.nombre || undefined, ciudad_slug: nuevo.ciudad_slug || undefined });
      setCreado({ email: nuevo.email.trim().toLowerCase(), password: nuevo.password });
      setNuevo({ email: "", password: "", nombre: "", ciudad_slug: "", roles: [] });
      onCambio();
    } catch (e) { setErr(e instanceof Error ? e.message : "No se pudo crear"); }
    finally { setCreando(false); }
  }

  const esAgente = nuevo.roles.includes("agente") || nuevo.roles.some((r) => (data.roles.find((x) => x.slug === r)?.permisos ?? []).includes("comercios.cargar"));

  return (
    <>
      <div className="panel-card glass" style={{ padding: 16, display: "grid", gap: 10 }}>
        <b>Agregar a alguien</b>
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
          {esAgente && (
            <label style={{ display: "grid", gap: 3, fontSize: 12 }}>
              <span style={{ opacity: .7 }}>Ciudad donde carga</span>
              <select className="adm-input" value={nuevo.ciudad_slug} onChange={(e) => setNuevo((s) => ({ ...s, ciudad_slug: e.target.value }))}>
                <option value="">— elegir —</option>
                {ciudades.map((c) => <option key={c.slug} value={c.slug}>{c.nombre}</option>)}
              </select>
            </label>
          )}
        </div>
        <div style={{ display: "grid", gap: 4 }}>
          <span style={{ fontSize: 12, opacity: .7 }}>Roles * (puede tener más de uno)</span>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {data.roles.map((r) => (
              <label key={r.slug} className="chip" style={{ cursor: "pointer", fontSize: 13 }} title={r.descripcion ?? ""}>
                <input type="checkbox" checked={nuevo.roles.includes(r.slug)}
                       onChange={(e) => setNuevo((s) => ({ ...s, roles: e.target.checked ? [...s.roles, r.slug] : s.roles.filter((x) => x !== r.slug) }))} />
                {" "}{r.nombre}
              </label>
            ))}
          </div>
        </div>
        <div>
          <button className="btn btn-primary" onClick={crear} disabled={creando || !nuevo.email.trim() || nuevo.password.length < 6 || nuevo.roles.length === 0}>
            {creando ? "Creando…" : "Crear"}
          </button>
        </div>
        {creado && (
          <div style={{ fontSize: 13, background: "rgba(34,197,94,.12)", border: "1px solid var(--neon)", borderRadius: 10, padding: "10px 12px" }}>
            <b>Listo. Pasale estos datos</b> — la contraseña no se puede volver a ver:
            <div style={{ marginTop: 6, fontFamily: "monospace", fontSize: 14 }}>
              uruku.bo/admin (o /publicar si carga en la calle)<br />usuario: {creado.email}<br />contraseña: {creado.password}
            </div>
            <button className="btn btn-ghost btn-sm" style={{ marginTop: 8 }}
                    onClick={() => navigator.clipboard?.writeText(`URUKU\nEntrás en: https://uruku.bo/publicar\nUsuario: ${creado.email}\nContraseña: ${creado.password}`)}>
              Copiar para mandar por WhatsApp
            </button>
          </div>
        )}
      </div>

      <div className="panel-card glass" style={{ padding: 16 }}>
        <b>El equipo</b>
        <div style={{ overflowX: "auto", marginTop: 8 }}>
          <table className="adm-table" style={{ fontSize: 13 }}>
            <thead><tr><th>Correo</th><th>Nombre</th><th>Roles</th><th>Ciudad</th><th>Último acceso</th><th></th></tr></thead>
            <tbody>
              {data.usuarios.map((u) => <FilaPersona key={u.id} u={u} data={data} ciudades={ciudades} onCambio={onCambio} />)}
              {data.usuarios.length === 0 && (
                <tr><td colSpan={6} style={{ opacity: .6 }}>
                  Todavía no hay nadie cargado acá: se entra con las cuentas del `.env`. Agregá a alguien arriba.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function FilaPersona({ u, data, ciudades, onCambio }: { u: UsuarioPanel; data: EquipoData; ciudades: Ciudad[]; onCambio: () => void }) {
  const [clave, setClave] = useState("");
  const [msg, setMsg] = useState("");
  const [roles, setRoles] = useState<string[]>(u.roles ?? []);

  async function guardar(patch: Partial<{ activo: boolean; password: string; ciudad_slug: string; roles: string[] }>) {
    setMsg("");
    try {
      await editarUsuarioPanel(u.id, { email: u.email, activo: patch.activo ?? u.activo, roles: patch.roles ?? roles, ...patch });
      setClave(""); setMsg("✓"); onCambio();
    } catch (e) { setMsg(e instanceof Error ? e.message : "no se pudo"); }
  }

  return (
    <tr style={{ opacity: u.activo ? 1 : .5 }}>
      <td>{u.email}{!u.activo && " · apagado"}</td>
      <td>{u.nombre ?? "—"}</td>
      <td>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {data.roles.map((r) => (
            <label key={r.slug} style={{ fontSize: 11.5, cursor: "pointer" }}>
              <input type="checkbox" checked={roles.includes(r.slug)}
                     onChange={(e) => {
                       const next = e.target.checked ? [...roles, r.slug] : roles.filter((x) => x !== r.slug);
                       setRoles(next); guardar({ roles: next });
                     }} />
              {" "}{r.nombre}
            </label>
          ))}
        </div>
      </td>
      <td>
        <select className="adm-input" style={{ width: "auto", fontSize: 12 }} value={u.ciudad_slug ?? ""}
                onChange={(e) => guardar({ ciudad_slug: e.target.value })}>
          <option value="">— sin ciudad —</option>
          {ciudades.map((c) => <option key={c.slug} value={c.slug}>{c.nombre}</option>)}
        </select>
      </td>
      <td style={{ fontSize: 12, opacity: .7 }}>{u.ultimo_acceso ? new Date(u.ultimo_acceso).toLocaleDateString() : "nunca entró"}</td>
      <td style={{ whiteSpace: "nowrap" }}>
        <input className="adm-input" style={{ width: 120, fontSize: 12, display: "inline-block" }} value={clave}
               onChange={(e) => setClave(e.target.value)} placeholder="clave nueva" />
        <button className="btn btn-ghost btn-sm" disabled={clave.length < 6} onClick={() => guardar({ password: clave })}>Cambiar</button>
        <button className="btn btn-ghost btn-sm" onClick={() => guardar({ activo: !u.activo })}>{u.activo ? "Apagar" : "Encender"}</button>
        {msg && <span style={{ fontSize: 12, marginLeft: 6 }}>{msg}</span>}
      </td>
    </tr>
  );
}

function Roles({ data, onCambio, setErr }: { data: EquipoData; onCambio: () => void; setErr: (s: string) => void }) {
  const [nuevo, setNuevo] = useState("");
  const grupos = Array.from(new Set(data.permisos.map((p) => p.grupo)));

  async function crear() {
    const nombre = nuevo.trim();
    if (!nombre) return;
    const slug = nombre.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    try { await guardarRol(slug, { slug, nombre, permisos: [] }); setNuevo(""); onCambio(); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo crear"); }
  }

  return (
    <>
      <p style={{ margin: 0, fontSize: 13, opacity: .75 }}>
        Un rol es una lista de permisos. Los cuatro de arriba vienen con el sistema y no se borran; podés crear los
        que quieras (por ejemplo «Cargador de Santa Cruz»). Lo que cambies acá vale la próxima vez que esa persona entre.
      </p>
      <div className="panel-card glass" style={{ padding: 16, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <input className="adm-input" style={{ maxWidth: 260 }} value={nuevo} onChange={(e) => setNuevo(e.target.value)} placeholder="Nombre del rol nuevo" />
        <button className="btn btn-primary btn-sm" onClick={crear} disabled={!nuevo.trim()}>Crear rol</button>
      </div>
      {data.roles.map((r) => <FilaRol key={r.slug} r={r} grupos={grupos} permisos={data.permisos} onCambio={onCambio} setErr={setErr} />)}
    </>
  );
}

function FilaRol({ r, grupos, permisos, onCambio, setErr }: {
  r: RolAdmin; grupos: string[]; permisos: EquipoData["permisos"]; onCambio: () => void; setErr: (s: string) => void;
}) {
  const [sel, setSel] = useState<string[]>(r.permisos ?? []);
  const [msg, setMsg] = useState("");
  const todo = sel.includes("*");

  async function guardar(next: string[]) {
    setSel(next); setMsg("");
    try { await guardarRol(r.slug, { slug: r.slug, nombre: r.nombre, descripcion: r.descripcion ?? undefined, permisos: next }); setMsg("✓"); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo guardar"); }
  }

  return (
    <div className="panel-card glass" style={{ padding: 16, display: "grid", gap: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "baseline", flexWrap: "wrap" }}>
        <b>{r.nombre} {r.del_sistema && <span style={{ fontSize: 11, opacity: .6 }}>· del sistema</span>}</b>
        <span style={{ fontSize: 12, opacity: .7 }}>{r.descripcion} {msg}</span>
        {!r.del_sistema && (
          <button className="btn btn-ghost btn-sm" onClick={async () => {
            if (!window.confirm(`¿Borrar el rol ${r.nombre}? Los que lo tengan se quedan sin él.`)) return;
            try { await borrarRol(r.slug); onCambio(); } catch (e) { setErr(e instanceof Error ? e.message : "No se pudo borrar"); }
          }}>Borrar</button>
        )}
      </div>
      {todo ? (
        <span style={{ fontSize: 13, opacity: .8 }}>Puede hacer <b>todo</b>. Es el rol de quien maneja URUKU.</span>
      ) : grupos.map((g) => (
        <div key={g} style={{ display: "grid", gap: 4 }}>
          <span style={{ fontSize: 11.5, opacity: .6, textTransform: "uppercase", letterSpacing: ".05em" }}>{g}</span>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 4 }}>
            {permisos.filter((p) => p.grupo === g).map((p) => (
              <label key={p.clave} style={{ fontSize: 13, cursor: "pointer" }}>
                <input type="checkbox" checked={sel.includes(p.clave)}
                       onChange={(e) => guardar(e.target.checked ? [...sel, p.clave] : sel.filter((x) => x !== p.clave))} />
                {" "}{p.que_hace}
              </label>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
