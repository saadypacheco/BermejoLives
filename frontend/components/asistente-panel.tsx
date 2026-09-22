"use client";

import { getCiudades } from "@/lib/data";
import { useCallback, useEffect, useState } from "react";
import {
  borrarSaberLocal, getAsistenteConversaciones, getSaberLocal, guardarSaberLocal, responderAsistente,
  type ConversacionAsistente, type SaberLocal,
} from "@/lib/api";

// Las secciones de la guía (uruku.bo/guia). Lo que se guarda con sección
// aparece ahí; "general" sólo lo contesta el asistente.
const SECCIONES: [string, string][] = [
  ["general", "General (sólo el asistente)"], ["frontera", "Frontera"], ["documentos", "Documentos"], ["aduana", "Aduana"],
  ["comercios", "Comercios y pagos"], ["transporte", "Transporte"], ["seguridad", "Seguridad"], ["conectividad", "Chip e internet"],
];
/** De qué frontera es lo que se está cargando. Vacío = todas: la aduana
 *  boliviana o cómo funciona URUKU sirven en cualquier ciudad; las chalanas,
 *  sólo en Bermejo (0124). */
function SelectCiudad({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [ciudades, setCiudades] = useState<{ slug: string; nombre: string }[]>([]);
  useEffect(() => { getCiudades().then((cs) => setCiudades(cs.filter((c) => c.es_frontera && c.activa))).catch(() => {}); }, []);
  if (ciudades.length < 2 && !value) return null;
  return (
    <select className="adm-input" style={{ width: "auto" }} value={value} onChange={(e) => onChange(e.target.value)} title="De qué ciudad es">
      <option value="">Todas las fronteras</option>
      {ciudades.map((c) => <option key={c.slug} value={c.slug}>{c.nombre}</option>)}
    </select>
  );
}

function SelectSeccion({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <select className="adm-input" value={value} onChange={(e) => onChange(e.target.value)} aria-label="Sección de la guía">
      {SECCIONES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  );
}

/**
 * Admin › Ayuda. Dos listas y una regla.
 *
 * Arriba, lo que la gente preguntó y el asistente NO supo contestar: es la
 * cola de trabajo. Cada una se contesta una vez y —esa es la regla— la
 * respuesta pasa a ser saber local: la próxima vez la contesta el Nivel 0,
 * sin modelo y sin nadie. Así el asistente aprende de lo que la gente
 * pregunta, no de lo que alguien imaginó que iba a preguntar.
 *
 * Abajo, el saber local entero, para corregir o sacar lo que ya no vale.
 */
export function AsistentePanel() {
  const [pendientes, setPendientes] = useState<ConversacionAsistente[]>([]);
  const [todas, setTodas] = useState<ConversacionAsistente[]>([]);
  const [saber, setSaber] = useState<SaberLocal[]>([]);
  const [verTodas, setVerTodas] = useState(false);
  const [err, setErr] = useState("");

  const cargar = useCallback(async () => {
    try {
      const [p, s] = await Promise.all([getAsistenteConversaciones("sin_respuesta"), getSaberLocal()]);
      setPendientes(p); setSaber(s); setErr("");
    } catch (e) { setErr(e instanceof Error ? e.message : "No se pudo cargar"); }
  }, []);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { if (verTodas) getAsistenteConversaciones("todas").then(setTodas).catch(() => {}); }, [verTodas]);

  const niveles = todas.reduce((acc, c) => { acc[c.nivel] = (acc[c.nivel] ?? 0) + 1; return acc; }, {} as Record<number, number>);
  const utiles = todas.filter((c) => c.util === true).length;
  const noUtiles = todas.filter((c) => c.util === false).length;

  return (
    <div style={{ display: "grid", gap: 22, maxWidth: 900 }}>
      {err && <p style={{ color: "#c33" }}>{err}</p>}

      <section>
        <h3 style={{ margin: "0 0 4px" }}>Sin respuesta ({pendientes.length})</h3>
        <p style={{ margin: "0 0 12px", fontSize: 13, opacity: .75 }}>
          Lo que la gente preguntó y el asistente no supo. Contestalo una vez: queda guardado como saber local
          y la próxima vez lo contesta solo. Las etiquetas son las palabras por las que se va a encontrar.
        </p>
        {pendientes.length === 0 && <p style={{ opacity: .6 }}>Nada pendiente.</p>}
        <div style={{ display: "grid", gap: 10 }}>
          {pendientes.map((c) => <Pendiente key={c.id} c={c} onHecho={cargar} />)}
        </div>
      </section>

      <section>
        <h3 style={{ margin: "0 0 4px" }}>Saber local ({saber.length})</h3>
        <p style={{ margin: "0 0 12px", fontSize: 13, opacity: .75 }}>
          Lo que el asistente sabe de Bermejo porque alguien lo escribió. Se contesta tal cual está acá.
        </p>
        <NuevoSaber onGuardado={cargar} />
        <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
          {saber.map((s) => <FilaSaber key={s.id} s={s} onCambio={cargar} />)}
        </div>
      </section>

      <section>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setVerTodas((v) => !v)}>
          {verTodas ? "Ocultar las últimas 200" : "Ver las últimas 200 preguntas"}
        </button>
        {verTodas && (
          <div style={{ marginTop: 10 }}>
            <p style={{ fontSize: 13, opacity: .75, margin: "0 0 8px" }}>
              Por nivel: sin modelo {niveles[0] ?? 0} · con modelo {niveles[1] ?? 0} · sin respuesta {niveles[3] ?? 0}
              · 👍 {utiles} · 👎 {noUtiles}
            </p>
            <div style={{ display: "grid", gap: 6, fontSize: 13 }}>
              {todas.map((c) => (
                <div key={c.id} style={{ padding: "8px 10px", border: "1px solid var(--stroke)", borderRadius: 8 }}>
                  <div><b>{c.pregunta}</b> <span style={{ opacity: .5 }}>· N{c.nivel} · {c.intent ?? "-"} · {c.canal}{c.util === true ? " · 👍" : c.util === false ? " · 👎" : ""}</span></div>
                  <div style={{ opacity: .8, whiteSpace: "pre-wrap" }}>{c.respuesta}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function Pendiente({ c, onHecho }: { c: ConversacionAsistente; onHecho: () => void }) {
  const [respuesta, setRespuesta] = useState("");
  const [etiquetas, setEtiquetas] = useState("");
  const [seccion, setSeccion] = useState("general");
  const [ciudadSaber, setCiudadSaber] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [err, setErr] = useState("");
  async function enviar(guardar: boolean) {
    setGuardando(true); setErr("");
    try {
      await responderAsistente(c.id, respuesta.trim() || "(sin respuesta)", etiquetas.split(",").map((e) => e.trim()).filter(Boolean), guardar, seccion, ciudadSaber);
      onHecho();
    } catch (e) { setErr(e instanceof Error ? e.message : "No se pudo"); }
    finally { setGuardando(false); }
  }
  return (
    <div style={{ padding: 12, border: "1px solid var(--stroke)", borderRadius: 10, display: "grid", gap: 8 }}>
      <div><b>{c.pregunta}</b> <span style={{ fontSize: 12, opacity: .5 }}>· {c.canal} · {new Date(c.created_at).toLocaleString("es-BO")}</span></div>
      <div style={{ fontSize: 12.5, opacity: .7 }}>Contestó: {c.respuesta}</div>
      <textarea className="adm-input" rows={2} value={respuesta} onChange={(e) => setRespuesta(e.target.value)}
                placeholder="La respuesta, como se la dirías a alguien que llega a Bermejo" />
      <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8 }}>
        <input className="adm-input" value={etiquetas} onChange={(e) => setEtiquetas(e.target.value)}
               placeholder="Etiquetas, separadas por coma (feria, jueves, avenida)" />
        <SelectSeccion value={seccion} onChange={setSeccion} />
        <SelectCiudad value={ciudadSaber} onChange={setCiudadSaber} />
      </div>
      {err && <span style={{ color: "#c33", fontSize: 12.5 }}>{err}</span>}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" className="btn btn-primary btn-sm" disabled={guardando || respuesta.trim().length < 3} onClick={() => enviar(true)}>
          Responder y guardar como saber local
        </button>
        <button type="button" className="btn btn-ghost btn-sm" disabled={guardando} onClick={() => enviar(false)} title="Sacarla de la lista sin guardar nada">
          Descartar
        </button>
      </div>
    </div>
  );
}

function NuevoSaber({ onGuardado }: { onGuardado: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [pregunta, setPregunta] = useState("");
  const [respuesta, setRespuesta] = useState("");
  const [etiquetas, setEtiquetas] = useState("");
  const [seccion, setSeccion] = useState("general");
  const [ciudadSaber, setCiudadSaber] = useState("");
  const [err, setErr] = useState("");
  async function guardar() {
    try {
      await guardarSaberLocal({ pregunta: pregunta.trim(), respuesta: respuesta.trim(), etiquetas: etiquetas.split(",").map((e) => e.trim()).filter(Boolean), seccion, ciudad: ciudadSaber || undefined });
      setPregunta(""); setRespuesta(""); setEtiquetas(""); setSeccion("general"); setAbierto(false); setErr(""); onGuardado();
    } catch (e) { setErr(e instanceof Error ? e.message : "No se pudo"); }
  }
  if (!abierto) return <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAbierto(true)}>+ Agregar algo que el asistente tenga que saber</button>;
  return (
    <div style={{ padding: 12, border: "1px dashed var(--stroke)", borderRadius: 10, display: "grid", gap: 8 }}>
      <input className="adm-input" value={pregunta} onChange={(e) => setPregunta(e.target.value)} placeholder="Cómo lo pregunta la gente: ¿Dónde está la terminal?" />
      <textarea className="adm-input" rows={2} value={respuesta} onChange={(e) => setRespuesta(e.target.value)} placeholder="La respuesta" />
      <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8 }}>
        <input className="adm-input" value={etiquetas} onChange={(e) => setEtiquetas(e.target.value)} placeholder="Etiquetas, separadas por coma" />
        <SelectSeccion value={seccion} onChange={setSeccion} />
        <SelectCiudad value={ciudadSaber} onChange={setCiudadSaber} />
      </div>
      {err && <span style={{ color: "#c33", fontSize: 12.5 }}>{err}</span>}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" className="btn btn-primary btn-sm" disabled={pregunta.trim().length < 3 || respuesta.trim().length < 3} onClick={guardar}>Guardar</button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAbierto(false)}>Cancelar</button>
      </div>
    </div>
  );
}

function FilaSaber({ s, onCambio }: { s: SaberLocal; onCambio: () => void }) {
  const [editando, setEditando] = useState(false);
  const [respuesta, setRespuesta] = useState(s.respuesta);
  const [etiquetas, setEtiquetas] = useState(s.etiquetas.join(", "));
  const [seccion, setSeccion] = useState(s.seccion ?? "general");
  async function guardar(activo = s.activo) {
    await guardarSaberLocal({ id: s.id, pregunta: s.pregunta, respuesta: respuesta.trim(), etiquetas: etiquetas.split(",").map((e) => e.trim()).filter(Boolean), activo, seccion });
    setEditando(false); onCambio();
  }
  async function borrar() {
    if (!window.confirm("¿Borrar esta entrada?")) return;
    await borrarSaberLocal(s.id); onCambio();
  }
  return (
    <div style={{ padding: "10px 12px", border: "1px solid var(--stroke)", borderRadius: 10, opacity: s.activo ? 1 : .55, display: "grid", gap: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "baseline" }}>
        <b>{s.pregunta}</b>
        <span style={{ fontSize: 11.5, opacity: .55, whiteSpace: "nowrap" }}>{s.seccion && s.seccion !== "general" ? `[${s.seccion}] ` : ""}{s.etiquetas.join(" · ")}{!s.activo ? " · apagada" : ""}</span>
      </div>
      {editando ? (
        <>
          <textarea className="adm-input" rows={3} value={respuesta} onChange={(e) => setRespuesta(e.target.value)} />
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8 }}>
            <input className="adm-input" value={etiquetas} onChange={(e) => setEtiquetas(e.target.value)} placeholder="Etiquetas, separadas por coma" />
            <SelectSeccion value={seccion} onChange={setSeccion} />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" className="btn btn-primary btn-sm" onClick={() => guardar()}>Guardar</button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditando(false)}>Cancelar</button>
          </div>
        </>
      ) : (
        <>
          <div style={{ fontSize: 13.5, whiteSpace: "pre-wrap" }}>{s.respuesta}</div>
          <div style={{ display: "flex", gap: 10, fontSize: 12.5 }}>
            <button type="button" className="link-more" onClick={() => setEditando(true)}>Editar</button>
            <button type="button" className="link-more" onClick={() => guardar(!s.activo)}>{s.activo ? "Apagar" : "Encender"}</button>
            <button type="button" className="link-more" onClick={borrar} style={{ color: "#c33" }}>Borrar</button>
          </div>
        </>
      )}
    </div>
  );
}
