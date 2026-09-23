"use client";

import { useEffect, useRef, useState } from "react";
import { getCotizaciones, getClima, getRedes, getFronteraEstado, getCiudades, type Cotizacion, type Clima, type Red, type FronteraEstado } from "@/lib/data";
import type { Ciudad } from "@/lib/types";
import {
  publicadorLogin, hayPub, clearPub, editarCotizacion, overrideClima, refrescarClima, editarFrontera,
  listarVideosPromo, subirVideoPromo, borrarVideoPromo, editarRed, type VideoPromoItem,
} from "@/lib/publicador";

export default function ContenidoPage() {
  const [authed, setAuthed] = useState(false);
  const [ready, setReady] = useState(false);
  // Por qué venció la sesión, para decirlo en el formulario. Sin esto, la
  // pantalla vuelve al login sin explicación y parece que se deslogueó sola.
  const [aviso, setAviso] = useState("");
  useEffect(() => { setAuthed(hayPub()); setReady(true); }, []);
  if (!ready) return null;
  if (!authed) return <Login aviso={aviso} onOk={() => { setAviso(""); setAuthed(true); }} />;
  return <Panel onLogout={(motivo) => { clearPub(); setAviso(motivo ?? ""); setAuthed(false); }} />;
}

function Login({ onOk, aviso = "" }: { onOk: () => void; aviso?: string }) {
  const [email, setEmail] = useState(""); const [pass, setPass] = useState(""); const [err, setErr] = useState(aviso);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr("");
    try { await publicadorLogin(email, pass); onOk(); } catch { setErr("Credenciales incorrectas"); }
  }
  return (
    <div className="campo-wrap">
      <span className="eyebrow"><span className="dot-live" /> Contenido del sitio</span>
      <h1 style={{ fontSize: 24, margin: "8px 0 16px" }}>Contenido de la home</h1>
      <form onSubmit={submit} className="glass" style={{ padding: 20, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 }}>
        <input className="adm-input" type="email" inputMode="email" autoCapitalize="none"
                 autoCorrect="off" spellCheck={false} autoComplete="username"
                 value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
        <input className="adm-input" type="password" value={pass} onChange={(e) => setPass(e.target.value)} placeholder="Contraseña" />
        {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
        <button className="btn btn-primary" type="submit">Entrar</button>
      </form>
    </div>
  );
}

function Panel({ onLogout }: { onLogout: (motivo?: string) => void }) {
  const [cotiz, setCotiz] = useState<Cotizacion[]>([]);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [clima, setClima] = useState<Clima | null>(null);
  const [videos, setVideos] = useState<VideoPromoItem[]>([]);
  const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  const [ct, setCt] = useState(""); const [cd, setCd] = useState(""); const [ch, setCh] = useState("12");
  const [titulo, setTitulo] = useState(""); const [prog, setProg] = useState<number | null>(null);
  const [redes, setRedes] = useState<Red[]>([]);
  const [redVals, setRedVals] = useState<Record<string, string>>({});
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getCotizaciones().then((c) => { setCotiz(c); setVals(Object.fromEntries(c.map((x) => [x.clave, x.valor != null ? String(x.valor) : ""]))); });
    getClima().then(setClima);
    listarVideosPromo().then(setVideos).catch(() => {});
    getRedes().then((r) => { setRedes(r); setRedVals(Object.fromEntries(r.map((x) => [x.clave, x.url ?? ""]))); });
  }, []);
  async function guardarRed(clave: string) {
    try { await editarRed(clave, redVals[clave] || ""); flash("Red guardada ✓"); } catch (e) { fail(e); }
  }
  const flash = (m: string) => { setMsg(m); setErr(""); setTimeout(() => setMsg(""), 2500); };
  const fail = (e: unknown) => {
    const msg = e instanceof Error ? e.message : "Error";
    setErr(msg);
    // Si el 401 borró el token, volver al login. Quedarse en un panel que ya no
    // puede guardar nada es peor que pedir la contraseña de nuevo.
    if (!hayPub()) onLogout(msg);
  };

  async function guardarCotiz(clave: string) {
    try { await editarCotizacion(clave, Number(vals[clave] || 0)); flash("Cotización guardada ✓"); } catch (e) { fail(e); }
  }
  async function actualizarClima() {
    try { const r = await refrescarClima(); setClima(r.clima); flash("Clima actualizado desde open-meteo ✓"); } catch (e) { fail(e); }
  }
  async function guardarClimaManual() {
    try {
      const r = await overrideClima({ temp_c: ct ? Number(ct) : undefined, descripcion: cd || undefined, horas: Number(ch || 12) });
      setClima(r.clima); flash("Clima corregido a mano ✓"); setCt(""); setCd("");
    } catch (e) { fail(e); }
  }
  async function onVideo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; e.target.value = "";
    if (!file) return;
    setErr(""); setProg(0);
    try { const v = await subirVideoPromo(file, titulo, setProg); setVideos((s) => [...s, v]); setTitulo(""); flash("Video subido ✓"); }
    catch (ex) { fail(ex); } finally { setProg(null); }
  }
  async function eliminarVideo(id: string) {
    if (!window.confirm("¿Borrar este video?")) return;
    try { await borrarVideoPromo(id); setVideos((s) => s.filter((v) => v.id !== id)); } catch (e) { fail(e); }
  }

  const box: React.CSSProperties = { padding: 18, borderRadius: 16, marginBottom: 16 };
  return (
    <div className="campo-wrap" style={{ maxWidth: 560 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <h1 style={{ fontSize: 22, margin: 0 }}>Contenido de la home</h1>
        <button className="link-more" onClick={() => onLogout()}>Salir</button>
      </div>
      {msg && <div style={{ color: "var(--neon)", fontSize: 13, marginBottom: 10 }}>{msg}</div>}
      {err && <div style={{ color: "var(--pink)", fontSize: 13, marginBottom: 10 }}>{err}</div>}

      {/* Cotizaciones */}
      <div className="glass" style={box}>
        <h3 style={{ marginTop: 0 }}>💵 Cotizaciones (carga diaria)</h3>
        {cotiz.map((c) => (
          <div key={c.clave} style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
            <div style={{ flex: 1 }}>
              <b style={{ fontSize: 14 }}>{c.etiqueta}</b>
              <div style={{ fontSize: 11, color: "var(--txt-3)" }}>
                {c.detalle} → {c.unidad}
                {/* Cuánto hace: el sitio y el conversor la muestran como "de hoy"
                    sólo si lo es. Pasados dos días avisa en naranja. */}
                {c.actualizado_en && (() => {
                  const d = Math.floor((Date.now() - new Date(c.actualizado_en).getTime()) / 86400000);
                  return <span style={{ marginLeft: 6, color: d > 2 ? "var(--pink)" : "inherit", fontWeight: d > 2 ? 700 : 400 }}>· {d === 0 ? "hoy" : `hace ${d} día${d === 1 ? "" : "s"}`}</span>;
                })()}
              </div>
            </div>
            <input className="adm-input" style={{ width: 110 }} type="number" inputMode="decimal" value={vals[c.clave] ?? ""} onChange={(e) => setVals((s) => ({ ...s, [c.clave]: e.target.value }))} />
            <button className="btn btn-primary btn-sm" onClick={() => guardarCotiz(c.clave)}>Guardar</button>
          </div>
        ))}
      </div>

      {/* La frontera hoy: lo primero que pregunta el que está por cruzar, y
          no hay ninguna fuente automática. Lo carga una persona, con fecha. */}
      <FronteraBox flash={flash} fail={fail} />

      {/* Clima */}
      <div className="glass" style={box}>
        <h3 style={{ marginTop: 0 }}>🌤️ Clima de Bermejo</h3>
        <div style={{ fontSize: 14, color: "var(--txt-2)", marginBottom: 10 }}>
          Ahora: {clima?.icono ?? "🌡️"} {clima?.temp_c != null ? `${Math.round(clima.temp_c)}°` : "—"} {clima?.descripcion ?? ""}
        </div>
        <button className="btn btn-ghost btn-sm" onClick={actualizarClima} style={{ marginBottom: 12 }}>↻ Traer de open-meteo</button>
        <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 6 }}>O corregilo a mano (si la API no coincide):</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input className="adm-input" style={{ width: 90 }} type="number" placeholder="°C" value={ct} onChange={(e) => setCt(e.target.value)} />
          <input className="adm-input" style={{ flex: 1, minWidth: 120 }} placeholder="Descripción (ej: Soleado)" value={cd} onChange={(e) => setCd(e.target.value)} />
          <input className="adm-input" style={{ width: 70 }} type="number" placeholder="hs" value={ch} onChange={(e) => setCh(e.target.value)} title="Horas antes de que open-meteo vuelva a pisar" />
          <button className="btn btn-primary btn-sm" onClick={guardarClimaManual}>Corregir</button>
        </div>
      </div>

      {/* Videos promocionales */}
      <div className="glass" style={box}>
        <h3 style={{ marginTop: 0 }}>🎬 Recorrimos Bermejo (videos)</h3>
        <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
          <input className="adm-input" style={{ flex: 1 }} placeholder="Título (ej: Centro de Bermejo)" value={titulo} onChange={(e) => setTitulo(e.target.value)} />
          <button className="btn btn-primary btn-sm" onClick={() => fileRef.current?.click()} disabled={prog !== null}>+ Video</button>
          <input ref={fileRef} type="file" accept="video/*" hidden onChange={onVideo} />
        </div>
        {prog !== null && <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 8 }}>Subiendo… {prog}%</div>}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(100px,1fr))", gap: 8 }}>
          {videos.map((v) => (
            <div key={v.id} style={{ position: "relative", borderRadius: 10, overflow: "hidden", border: "1px solid var(--stroke)" }}>
              <video src={v.url} preload="metadata" style={{ width: "100%", aspectRatio: "9/16", objectFit: "cover", background: "#000", display: "block" }} />
              <button onClick={() => eliminarVideo(v.id)} style={{ position: "absolute", top: 3, right: 3, width: 20, height: 20, borderRadius: "50%", background: "rgba(0,0,0,.65)", color: "#fff", fontSize: 11 }}>✕</button>
            </div>
          ))}
        </div>
        {videos.length === 0 && <p style={{ color: "var(--txt-3)", fontSize: 13 }}>Todavía no subiste videos.</p>}
      </div>

      {/* Redes sociales */}
      <div className="glass" style={box}>
        <h3 style={{ marginTop: 0 }}>🔗 Redes sociales</h3>
        {redes.map((r) => (
          <div key={r.clave} style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
            <span style={{ width: 130, fontSize: 13, fontWeight: 600 }}>{r.etiqueta}</span>
            <input className="adm-input" style={{ flex: 1 }} placeholder="https://…" value={redVals[r.clave] ?? ""} onChange={(e) => setRedVals((s) => ({ ...s, [r.clave]: e.target.value }))} />
            <button className="btn btn-primary btn-sm" onClick={() => guardarRed(r.clave)}>Guardar</button>
          </div>
        ))}
      </div>
    </div>
  );
}


function FronteraBox({ flash, fail }: { flash: (m: string) => void; fail: (e: unknown) => void }) {
  const [f, setF] = useState<FronteraEstado | null>(null);
  const [nota, setNota] = useState("");
  const [horarioChalanas, setHorarioChalanas] = useState("");
  // Una frontera por ciudad (0124): se elige cuál se está cargando.
  const [fronteras, setFronteras] = useState<Ciudad[]>([]);
  const [ciudadSlug, setCiudadSlug] = useState("bermejo");
  useEffect(() => { getCiudades().then((cs) => setFronteras(cs.filter((c) => c.es_frontera && c.activa))).catch(() => {}); }, []);
  const ciudadSel = fronteras.find((c) => c.slug === ciudadSlug);
  useEffect(() => {
    getFronteraEstado(ciudadSel?.id).then((x) => { setF(x); setNota(x?.nota ?? ""); setHorarioChalanas(x?.chalanas_horario ?? ""); });
  }, [ciudadSel?.id]);
  async function guardar(patch: Record<string, string>) {
    try {
      await editarFrontera({ ...patch, ciudad: ciudadSlug });
      const x = await getFronteraEstado(ciudadSel?.id);
      setF(x); flash("Frontera actualizada ✓");
    } catch (e) { fail(e); }
  }
  const opciones: [keyof FronteraEstado, string, string[]][] = [
    ["puente", "Puente internacional", ["normal", "demoras", "cerrado"]],
    // "no aplica" para la frontera que no tiene chalanas ni río (Villazón
    // cruza por un puente peatonal): así no se muestra el renglón.
    ["chalanas", "Chalanas", ["operando", "limitadas", "suspendidas", "no_aplica"]],
    ["rio", "Río", ["normal", "crecido", "no_aplica"]],
  ];
  const hace = f?.actualizado_en ? Math.floor((Date.now() - new Date(f.actualizado_en).getTime()) / 3600000) : null;
  return (
    <div className="glass" style={{ padding: 18, borderRadius: 16, marginBottom: 14 }}>
      <h3 style={{ marginTop: 0, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        🌉 La frontera hoy
        {fronteras.length > 1 && (
          <select className="adm-input" style={{ width: "auto", fontSize: 13 }} value={ciudadSlug} onChange={(e) => setCiudadSlug(e.target.value)}>
            {fronteras.map((c) => <option key={c.slug} value={c.slug}>{c.nombre}{c.paso_nombre ? ` → ${c.paso_nombre}` : ""}</option>)}
          </select>
        )}
      </h3>
      <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 10 }}>
        Se ve en uruku.bo/guia y lo contesta el asistente ("¿cómo está el paso?"). Cada frontera tiene el suyo.
        {ciudadSel && !ciudadSel.guia_activa && <> <b style={{ color: "var(--amber)" }}>La guía de {ciudadSel.nombre} todavía no está activa</b> — se prende cuando tenga su saber local cargado (Admin › Ayuda).</>}
        {hace != null && <> Última carga: {hace < 1 ? "hace menos de una hora" : hace < 48 ? `hace ${hace} h` : `hace ${Math.floor(hace / 24)} días`}{hace >= 24 ? " — está vieja, cargala de nuevo" : ""}.</>}
      </div>
      <div style={{ display: "grid", gap: 8 }}>
        {opciones.map(([k, label, vals]) => (
          <div key={k} style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <b style={{ fontSize: 13, width: 150 }}>{label}</b>
            {vals.map((v) => (
              <button key={v} className={`btn btn-sm ${f?.[k] === v ? "btn-primary" : ""}`} style={f?.[k] === v ? {} : { border: "1px solid var(--stroke)" }}
                      onClick={() => guardar({ [k]: v })}>{v === "no_aplica" ? "no aplica" : v}</button>
            ))}
          </div>
        ))}
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <b style={{ fontSize: 13, width: 150 }}>Horario chalanas</b>
          <input className="adm-input" style={{ flex: 1 }} value={horarioChalanas} onChange={(e) => setHorarioChalanas(e.target.value)} maxLength={160}
                 placeholder="ej. 6:00 a 18:00 todas · hasta las 20:00 queda una cooperativa (rota cada semana)" />
          <button className="btn btn-primary btn-sm" onClick={() => guardar({ chalanas_horario: horarioChalanas })}>Guardar horario</button>
        </div>
        <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginTop: -4 }}>
          Escribilo como se lo dirías a alguien. Si hay turnos, ponelos: «6:00 a 18:00 todas · hasta las 20:00 queda
          una cooperativa». Sale en la guía, en el home y en la Ayuda. Vacío = no se muestra.
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input className="adm-input" style={{ flex: 1 }} value={nota} onChange={(e) => setNota(e.target.value)} maxLength={300}
                 placeholder="Nota (opcional): filas de dos horas por el feriado, migraciones sin sistema…" />
          <button className="btn btn-primary btn-sm" onClick={() => guardar({ nota })}>Guardar nota</button>
        </div>
      </div>
    </div>
  );
}
