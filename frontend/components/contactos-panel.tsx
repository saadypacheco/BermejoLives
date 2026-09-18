"use client";

import { useEffect, useMemo, useState } from "react";
import { getResumenContactos, importarContactos, type ResumenContactos } from "@/lib/api";

/**
 * Admin › Compradores: el Excel de compradores y sus grupos.
 *
 * El archivo se lee ACÁ, en el navegador (xlsx o csv), se eligen las
 * columnas y se manda fila por fila al backend, que normaliza los números
 * (549…, 591…) y guarda lo nuevo. Ningún número se muestra después: el
 * panel es de conteos —por grupo, por ciudad, cuántos ya usan URUKU— y del
 * enlace `?ref=grupo-<slug>` que le toca a cada grupo.
 *
 * Y lo que NO hace, a propósito: escribirle a nadie. Ver docs/que-falta.md
 * y la nota de la 0117.
 */
type Fila = Record<string, unknown>;

const PISTAS: Record<"telefono" | "grupo" | "ciudad" | "nombre", RegExp> = {
  telefono: /tel|cel|whats|wa\b|numero|número|phone|movil|móvil/i,
  grupo: /grupo|group|tour|lista|origen/i,
  ciudad: /ciudad|localidad|city|provincia|zona/i,
  nombre: /nombre|name|contacto/i,
};

function adivinar(cols: string[]) {
  const pick = (re: RegExp) => cols.find((c) => re.test(c)) ?? "";
  return { telefono: pick(PISTAS.telefono) || cols[0] || "", grupo: pick(PISTAS.grupo), ciudad: pick(PISTAS.ciudad), nombre: pick(PISTAS.nombre) };
}

export function ContactosPanel() {
  const [resumen, setResumen] = useState<ResumenContactos | null>(null);
  const [err, setErr] = useState("");
  const [archivo, setArchivo] = useState("");
  const [filas, setFilas] = useState<Fila[]>([]);
  const [cols, setCols] = useState<string[]>([]);
  const [mapa, setMapa] = useState({ telefono: "", grupo: "", ciudad: "", nombre: "" });
  const [grupoFijo, setGrupoFijo] = useState("");
  const [pais, setPais] = useState<"AR" | "BO">("AR");
  const [estado, setEstado] = useState<"" | "leyendo" | "importando" | "ok" | "error">("");
  const [resultado, setResultado] = useState<{ nuevos: number; repetidos: number; invalidos: number; ejemplos_invalidos: { telefono: string; grupo: string; motivo: string }[] } | null>(null);

  const cargar = () => getResumenContactos().then(setResumen).catch((e) => setErr(e instanceof Error ? e.message : "No se pudo cargar"));
  useEffect(() => { cargar(); }, []);

  async function leer(f: File) {
    setEstado("leyendo"); setErr(""); setResultado(null);
    try {
      const XLSX = await import("xlsx");
      const buf = await f.arrayBuffer();
      const wb = XLSX.read(buf, { type: "array", raw: false });
      // Todas las hojas: un Excel de grupos suele tener una hoja por grupo,
      // y ahí el nombre de la hoja ES el grupo.
      const todas: Fila[] = [];
      for (const nombre of wb.SheetNames) {
        const hoja = XLSX.utils.sheet_to_json<Fila>(wb.Sheets[nombre], { defval: "" });
        for (const r of hoja) todas.push({ ...r, __hoja: nombre });
      }
      const columnas = Array.from(new Set(todas.flatMap((r) => Object.keys(r)))).filter((c) => c !== "__hoja");
      setArchivo(f.name); setFilas(todas); setCols(columnas);
      const m = adivinar(columnas);
      // Sin columna de grupo pero con varias hojas: el grupo es la hoja.
      setMapa({ ...m, grupo: m.grupo || (wb.SheetNames.length > 1 ? "__hoja" : "") });
      setEstado("");
    } catch (e) {
      setEstado("error"); setErr(e instanceof Error ? e.message : "No se pudo leer el archivo");
    }
  }

  const vista = useMemo(() => filas.slice(0, 5), [filas]);

  async function importar() {
    if (!mapa.telefono) { setErr("Elegí la columna del teléfono."); return; }
    setEstado("importando"); setErr("");
    try {
      const cuerpo = filas.map((r) => ({
        telefono: String(r[mapa.telefono] ?? ""),
        grupo: grupoFijo.trim() || String((mapa.grupo && r[mapa.grupo]) ?? ""),
        ciudad: mapa.ciudad ? String(r[mapa.ciudad] ?? "") : "",
        nombre: mapa.nombre ? String(r[mapa.nombre] ?? "") : "",
      })).filter((x) => x.telefono.trim());
      // De a tandas: un Excel de miles de filas en un solo pedido es un
      // pedido que un celular con 3G no termina.
      const total = { nuevos: 0, repetidos: 0, invalidos: 0, ejemplos_invalidos: [] as { telefono: string; grupo: string; motivo: string }[] };
      for (let i = 0; i < cuerpo.length; i += 2000) {
        const r = await importarContactos(cuerpo.slice(i, i + 2000), archivo, pais);
        total.nuevos += r.nuevos; total.repetidos += r.repetidos; total.invalidos += r.invalidos;
        if (total.ejemplos_invalidos.length < 20) total.ejemplos_invalidos.push(...r.ejemplos_invalidos.slice(0, 20 - total.ejemplos_invalidos.length));
      }
      setResultado(total); setEstado("ok"); setFilas([]); setCols([]); setArchivo("");
      cargar();
    } catch (e) {
      setEstado("error"); setErr(e instanceof Error ? e.message : "No se pudo importar");
    }
  }

  const sel = (k: keyof typeof mapa, label: string, obligatorio = false) => (
    <label style={{ display: "grid", gap: 3, fontSize: 12 }}>
      <span style={{ opacity: .7 }}>{label}{obligatorio ? " *" : ""}</span>
      <select className="adm-input" value={mapa[k]} onChange={(e) => setMapa((m) => ({ ...m, [k]: e.target.value }))}>
        <option value="">{obligatorio ? "— elegir —" : "— no hay —"}</option>
        {cols.map((c) => <option key={c} value={c}>{c}</option>)}
        {k === "grupo" && <option value="__hoja">(el nombre de la hoja)</option>}
      </select>
    </label>
  );

  return (
    <div style={{ display: "grid", gap: 16, maxWidth: 980 }}>
      <p style={{ margin: 0, fontSize: 13, opacity: .75 }}>
        La base de compradores y los grupos de los que vienen. Se usa para saber <b>de dónde llega la gente</b>, cruzar
        con los que ya entran a URUKU y darle a cada grupo su enlace. <b>No se le escribe a nadie desde acá</b>: un número
        de URUKU que le manda a miles de desconocidos es un número baneado.
      </p>
      {err && <p style={{ color: "#c33", margin: 0 }}>{err}</p>}

      {/* ---- subir ---- */}
      <div className="panel-card glass" style={{ padding: 16, display: "grid", gap: 12 }}>
        <b>Importar un Excel o CSV</b>
        <input type="file" accept=".xlsx,.xls,.csv,.txt" onChange={(e) => { const f = e.target.files?.[0]; if (f) leer(f); }} />
        {estado === "leyendo" && <span style={{ fontSize: 13 }}>Leyendo…</span>}
        {cols.length > 0 && (
          <>
            <div style={{ fontSize: 13 }}>
              <b>{archivo}</b>: {filas.length} filas. Decime qué columna es cada cosa (adiviné lo que pude):
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
              {sel("telefono", "Teléfono / WhatsApp", true)}
              {sel("grupo", "Grupo")}
              {sel("ciudad", "Ciudad")}
              {sel("nombre", "Nombre")}
              <label style={{ display: "grid", gap: 3, fontSize: 12 }}>
                <span style={{ opacity: .7 }}>País de los números sin código</span>
                <select className="adm-input" value={pais} onChange={(e) => setPais(e.target.value as "AR" | "BO")}>
                  <option value="AR">Argentina (549…)</option>
                  <option value="BO">Bolivia (591…)</option>
                </select>
              </label>
              <label style={{ display: "grid", gap: 3, fontSize: 12 }}>
                <span style={{ opacity: .7 }}>O un grupo fijo para todo el archivo</span>
                <input className="adm-input" value={grupoFijo} onChange={(e) => setGrupoFijo(e.target.value)} placeholder="ej. Tours Salta" />
              </label>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table className="adm-table" style={{ fontSize: 12 }}>
                <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                <tbody>
                  {vista.map((r, i) => (
                    <tr key={i}>{cols.map((c) => <td key={c} style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{String(r[c] ?? "")}</td>)}</tr>
                  ))}
                </tbody>
              </table>
              <div style={{ fontSize: 11, opacity: .6, marginTop: 4 }}>Las primeras 5 filas, para ver que las columnas sean las que son.</div>
            </div>
            <div>
              <button className="btn btn-primary" onClick={importar} disabled={estado === "importando" || !mapa.telefono}>
                {estado === "importando" ? "Importando…" : `Importar ${filas.length} filas`}
              </button>
            </div>
          </>
        )}
        {resultado && (
          <div style={{ fontSize: 13, display: "grid", gap: 4 }}>
            <b style={{ color: "var(--neon)" }}>Listo: {resultado.nuevos} nuevos · {resultado.repetidos} ya estaban · {resultado.invalidos} con número raro</b>
            {resultado.ejemplos_invalidos.length > 0 && (
              <details>
                <summary style={{ cursor: "pointer" }}>Ver los números que no se entendieron (se guardaron igual, marcados)</summary>
                <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                  {resultado.ejemplos_invalidos.map((m, i) => <li key={i}>{m.telefono || "(vacío)"} — {m.grupo || "sin grupo"} · {m.motivo}</li>)}
                </ul>
              </details>
            )}
          </div>
        )}
      </div>

      {/* ---- resumen ---- */}
      {resumen && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
            <Cifra label="Contactos" n={resumen.total} sub={`${resumen.telefonos_distintos} números distintos`} />
            <Cifra label="Grupos" n={resumen.grupos.length} />
            <Cifra label="Ya usan URUKU" n={resumen.en_uruku} sub={resumen.total ? `${Math.round((resumen.en_uruku / Math.max(1, resumen.telefonos_distintos)) * 100)} % de la base` : ""} color="var(--neon)" />
            <Cifra label="Números raros" n={resumen.invalidos} sub="marcados, sin país claro" color={resumen.invalidos ? "var(--amber)" : undefined} />
          </div>

          <div className="panel-card glass" style={{ padding: 16 }}>
            <b>Por grupo</b>
            <p style={{ fontSize: 12, opacity: .7, margin: "4px 0 10px" }}>
              Cada grupo tiene su enlace. Se lo das al <b>administrador del grupo</b> para que lo publique él (con la imagen del QR):
              lo que entre por ahí se cuenta en Panel › Llegadas por QR.
            </p>
            <div style={{ overflowX: "auto" }}>
              <table className="adm-table" style={{ fontSize: 13 }}>
                <thead><tr><th>Grupo</th><th>Contactos</th><th>Ya en URUKU</th><th>Enlace para el grupo</th></tr></thead>
                <tbody>
                  {resumen.grupos.map((g) => {
                    const url = `https://uruku.bo/?ref=grupo-${g.slug}`;
                    return (
                      <tr key={g.slug}>
                        <td>{g.grupo || <i>sin grupo</i>}</td>
                        <td>{g.contactos}</td>
                        <td>{g.en_uruku}</td>
                        <td style={{ whiteSpace: "nowrap" }}>
                          <code style={{ fontSize: 12 }}>{url}</code>{" "}
                          <button className="btn btn-ghost btn-sm" onClick={() => navigator.clipboard?.writeText(url)}>Copiar</button>
                        </td>
                      </tr>
                    );
                  })}
                  {resumen.grupos.length === 0 && <tr><td colSpan={4} style={{ opacity: .6 }}>Todavía no hay nada importado.</td></tr>}
                </tbody>
              </table>
            </div>
          </div>

          {resumen.ciudades.length > 0 && (
            <div className="panel-card glass" style={{ padding: 16 }}>
              <b>Por ciudad</b>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8, fontSize: 13 }}>
                {resumen.ciudades.map((c) => <span key={c.ciudad} className="chip">{c.ciudad} · {c.contactos}</span>)}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Cifra({ label, n, sub, color }: { label: string; n: number; sub?: string; color?: string }) {
  return (
    <div className="panel-card glass" style={{ padding: 14, borderLeft: `3px solid ${color ?? "var(--blue-soft)"}` }}>
      <div style={{ fontSize: 12, color: "var(--txt-3)" }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, color }}>{n}</div>
      {sub && <div style={{ fontSize: 11, color: "var(--txt-3)" }}>{sub}</div>}
    </div>
  );
}
