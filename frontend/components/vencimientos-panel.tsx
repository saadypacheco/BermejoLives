"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getVencimientos, guardarVencimiento, borrarVencimiento,
  type PanelVencimientos,
} from "@/lib/api";

/** Colores por estado.
 *
 *  `sin_fecha` NO es verde, a propósito: no está tranquilo, está sin vigilar.
 *  Pintarlo como sano es la forma más fácil de que un tablero mienta. */
const COLOR: Record<string, string> = {
  vencido: "var(--pink)",
  critico: "var(--pink)",
  por_vencer: "var(--amber)",
  sin_fecha: "var(--txt-3)",
  sin_dato: "var(--amber)",
  ok: "var(--neon)",
};

const ETIQUETA: Record<string, string> = {
  vencido: "VENCIDO",
  critico: "vence ya",
  por_vencer: "por vencer",
  sin_fecha: "falta la fecha",
  sin_dato: "no responde",
  ok: "al día",
};

function cuando(v: { dias?: number | null }): string {
  if (v.dias == null) return "—";
  if (v.dias < 0) return `hace ${Math.abs(v.dias)} día${Math.abs(v.dias) === 1 ? "" : "s"}`;
  if (v.dias === 0) return "hoy";
  return `en ${v.dias} día${v.dias === 1 ? "" : "s"}`;
}

export function VencimientosPanel() {
  const [data, setData] = useState<PanelVencimientos | null>(null);
  const [err, setErr] = useState("");
  const [editando, setEditando] = useState<string | null>(null);
  const [borrador, setBorrador] = useState<Record<string, unknown>>({});

  const cargar = useCallback(async () => {
    try { setData(await getVencimientos()); setErr(""); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo cargar"); }
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  async function guardar(id: string | null) {
    try {
      await guardarVencimiento(id, borrador);
      setEditando(null); setBorrador({});
      await cargar();
    } catch (e) { setErr(e instanceof Error ? e.message : "No se pudo guardar"); }
  }

  async function dejarDeVigilar(id: string, nombre: string) {
    if (!confirm(`¿Dejar de vigilar ${nombre}?`)) return;
    try { await borrarVencimiento(id); await cargar(); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo borrar"); }
  }

  if (!data) {
    return (
      <div className="panel-card glass" style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>
        {err || "Cargando…"}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {err && <div style={{ color: "var(--pink)", fontSize: 13 }}>{err}</div>}

      {/* Lo cargado a mano: dominios, VPS, chips. Nada de esto lo puede
          averiguar el sistema, así que si no lo carga alguien, no existe. */}
      <div className="panel-card glass">
        <div className="ph">
          <h3>Vencimientos</h3>
          <button className="btn btn-ghost btn-sm"
            onClick={() => { setEditando("nuevo"); setBorrador({ aviso_dias: 30, tipo: "otro" }); }}>
            + Agregar
          </button>
        </div>

        {editando === "nuevo" && (
          <div style={{ padding: "8px 16px", borderBottom: "1px solid var(--border)" }}>
            <FormFila borrador={borrador} setBorrador={setBorrador}
              onGuardar={() => guardar(null)}
              onCancelar={() => { setEditando(null); setBorrador({}); }} />
          </div>
        )}

        {data.items.map((v) => (
          <div key={v.id} style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
            {editando === v.id ? (
              <FormFila borrador={borrador} setBorrador={setBorrador}
                onGuardar={() => guardar(v.id)}
                onCancelar={() => { setEditando(null); setBorrador({}); }} />
            ) : (
              <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                <span style={{ width: 4, alignSelf: "stretch", minHeight: 34, borderRadius: 3,
                               background: COLOR[v.estado] ?? "var(--txt-3)" }} />
                <div style={{ flex: "1 1 220px", minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 14.5 }}>{v.nombre}</div>
                  <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 2 }}>
                    {v.proveedor ? `${v.proveedor} · ` : ""}{v.tipo}
                    {v.vence_el ? ` · ${v.vence_el}` : ""}
                  </div>
                  {v.notas && <div style={{ fontSize: 12, color: "var(--txt-2)", marginTop: 4 }}>{v.notas}</div>}
                </div>
                <div style={{ textAlign: "right", flexShrink: 0 }}>
                  <div style={{ color: COLOR[v.estado], fontWeight: 700, fontSize: 13 }}>
                    {ETIQUETA[v.estado] ?? v.estado}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--txt-3)" }}>{cuando(v)}</div>
                </div>
                <button className="btn btn-ghost btn-sm" onClick={() => {
                  setEditando(v.id);
                  setBorrador({
                    nombre: v.nombre, tipo: v.tipo, vence_el: v.vence_el ?? "",
                    aviso_dias: v.aviso_dias, proveedor: v.proveedor ?? "",
                    url: v.url ?? "", notas: v.notas ?? "",
                  });
                }}>Editar</button>
                <button className="btn btn-ghost btn-sm" title="Dejar de vigilar"
                  onClick={() => dejarDeVigilar(v.id, v.nombre)}>✕</button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Los certificados NO se cargan a mano: se miden. Un dato que se puede
          medir y además se escribe termina, algún día, diciendo algo distinto
          de la realidad — y lo sigue diciendo con confianza. */}
      <div className="panel-card glass">
        <div className="ph">
          <h3>Certificados HTTPS</h3>
          <span style={{ color: "var(--txt-3)", fontSize: 12.5 }}>medidos en vivo</span>
        </div>
        <div style={{ padding: "4px 16px 12px" }}>
          <p style={{ fontSize: 12.5, color: "var(--txt-3)", margin: "8px 0 12px" }}>
            No hay nada que renovar acá: los renueva Traefik solo. Esto sirve para enterarse
            el día que la renovación automática deje de funcionar, que es un fallo silencioso
            — todo anda hasta que vence.
          </p>
          {data.certificados.map((c) => (
            <div key={c.host} style={{ display: "flex", gap: 10, alignItems: "center",
                                       padding: "7px 0", borderTop: "1px solid var(--border)" }}>
              <span style={{ width: 4, alignSelf: "stretch", minHeight: 26, borderRadius: 3,
                             background: COLOR[c.estado] ?? "var(--txt-3)" }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13.5, fontFamily: "monospace" }}>{c.host}</div>
                <div style={{ fontSize: 11.5, color: "var(--txt-3)" }}>{c.que_sirve}</div>
              </div>
              <div style={{ textAlign: "right", fontSize: 12.5 }}>
                {c.ok ? (
                  <>
                    <span style={{ color: COLOR[c.estado], fontWeight: 700 }}>{cuando(c)}</span>
                    <div style={{ color: "var(--txt-3)", fontSize: 11.5 }}>{c.vence_el}</div>
                  </>
                ) : (
                  <span style={{ color: "var(--amber)" }} title={c.error}>no responde</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function FormFila({ borrador, setBorrador, onGuardar, onCancelar }: {
  borrador: Record<string, unknown>;
  setBorrador: (v: Record<string, unknown>) => void;
  onGuardar: () => void;
  onCancelar: () => void;
}) {
  const set = (k: string, v: unknown) => setBorrador({ ...borrador, [k]: v });
  const s = (k: string) => (borrador[k] as string) ?? "";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 8 }}>
      <input className="adm-input" placeholder="Nombre" value={s("nombre")}
             onChange={(e) => set("nombre", e.target.value)} />
      <select className="adm-input" value={s("tipo") || "otro"} onChange={(e) => set("tipo", e.target.value)}>
        <option value="dominio">Dominio</option>
        <option value="hosting">Hosting / VPS</option>
        <option value="servicio">Servicio</option>
        <option value="sim">Chip / SIM</option>
        <option value="plan">Plan</option>
        <option value="otro">Otro</option>
      </select>
      <input className="adm-input" type="date" value={s("vence_el")}
             onChange={(e) => set("vence_el", e.target.value)} />
      <label style={{ fontSize: 11.5, color: "var(--txt-3)" }}>Avisar días antes
        <input className="adm-input" type="number" min={1} max={365}
               value={(borrador.aviso_dias as number) ?? 30}
               onChange={(e) => set("aviso_dias", Number(e.target.value) || 30)} />
      </label>
      <input className="adm-input" placeholder="Proveedor" value={s("proveedor")}
             onChange={(e) => set("proveedor", e.target.value)} />
      <input className="adm-input" style={{ gridColumn: "1 / -1" }}
             placeholder="Notas: qué se cae si esto vence"
             value={s("notas")} onChange={(e) => set("notas", e.target.value)} />
      <div style={{ display: "flex", gap: 8, gridColumn: "1 / -1" }}>
        <button className="btn btn-primary btn-sm" onClick={onGuardar}>Guardar</button>
        <button className="btn btn-ghost btn-sm" onClick={onCancelar}>Cancelar</button>
      </div>
    </div>
  );
}
