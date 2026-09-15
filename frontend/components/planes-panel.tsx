"use client";

import { useEffect, useState } from "react";
import { getPlanesAdmin, guardarPlan, type PlanAdmin } from "@/lib/api";

/**
 * Admin › Planes: precio, cuota, extra, meses gratis, la frase y las viñetas
 * de cada plan. Es lo que muestra /planes y lo que el sistema cobra, en un
 * solo lugar. Un precio se cambia acá el día que se decide, sin deploy.
 */
export function PlanesPanel() {
  const [planes, setPlanes] = useState<PlanAdmin[]>([]);
  const [err, setErr] = useState("");
  const cargar = () => getPlanesAdmin().then(setPlanes).catch((e) => setErr(e instanceof Error ? e.message : "No se pudo cargar"));
  useEffect(() => { cargar(); }, []);

  return (
    <div style={{ display: "grid", gap: 14, maxWidth: 980 }}>
      <p style={{ margin: 0, fontSize: 13, opacity: .75 }}>
        Lo que se ve en <a href="/planes" target="_blank" rel="noopener">uruku.bo/planes</a> y lo que el sistema cobra.
        Las funciones (redes, chatbot, agentes) las decide el código por la clave del plan; acá se cambian precios, cuotas y textos.
      </p>
      {err && <p style={{ color: "#c33" }}>{err}</p>}
      {planes.map((p) => <FilaPlan key={p.slug} p={p} onGuardado={cargar} />)}
    </div>
  );
}

function FilaPlan({ p, onGuardado }: { p: PlanAdmin; onGuardado: () => void }) {
  const [v, setV] = useState({
    nombre: p.nombre, precio_mes: String(p.precio_mes), publicaciones_mes: p.publicaciones_mes == null ? "" : String(p.publicaciones_mes),
    precio_publicacion_extra: String(p.precio_publicacion_extra), permite_extras: p.permite_extras,
    publica_meses: p.publica_meses == null ? "" : String(p.publica_meses), descripcion: p.descripcion ?? "",
    incluye: (p.incluye ?? []).join("\n"), visible: p.visible,
  });
  const [estado, setEstado] = useState<"" | "guardando" | "ok" | "error">("");
  const [msg, setMsg] = useState("");
  const funciones = Object.keys(p.funciones ?? {}).filter((k) => p.funciones[k]);

  async function guardar() {
    setEstado("guardando"); setMsg("");
    try {
      await guardarPlan(p.slug, {
        nombre: v.nombre.trim(), precio_mes: Number(v.precio_mes || 0),
        publicaciones_mes: v.publicaciones_mes.trim() === "" ? null : Number(v.publicaciones_mes),
        precio_publicacion_extra: Number(v.precio_publicacion_extra || 0), permite_extras: v.permite_extras,
        publica_meses: v.publica_meses.trim() === "" ? null : Number(v.publica_meses),
        descripcion: v.descripcion.trim(), incluye: v.incluye.split("\n").map((s) => s.trim()).filter(Boolean),
        visible: v.visible,
      });
      setEstado("ok"); onGuardado();
    } catch (e) { setEstado("error"); setMsg(e instanceof Error ? e.message : "No se pudo guardar"); }
  }

  const campo = (label: string, key: keyof typeof v, extra: Record<string, unknown> = {}) => (
    <label style={{ display: "grid", gap: 3, fontSize: 12 }}>
      <span style={{ opacity: .7 }}>{label}</span>
      <input className="adm-input" value={String(v[key])} onChange={(e) => setV((s) => ({ ...s, [key]: e.target.value }))} {...extra} />
    </label>
  );

  return (
    <div style={{ padding: 14, border: "1px solid var(--stroke)", borderRadius: 12, opacity: p.visible ? 1 : .6, display: "grid", gap: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
        <b style={{ fontSize: 15 }}>{p.nombre} <span style={{ opacity: .5, fontWeight: 400 }}>· {p.slug}</span></b>
        <span style={{ fontSize: 12, opacity: .6 }}>{funciones.length ? funciones.join(" · ") : "sin funciones (sólo el mapa)"}</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 8 }}>
        {campo("Nombre", "nombre")}
        {campo("Precio/mes (Bs)", "precio_mes", { type: "number", inputMode: "decimal" })}
        {campo("Publicaciones/mes (vacío = sin límite)", "publicaciones_mes", { type: "number", inputMode: "numeric" })}
        {campo("Extra (Bs c/u)", "precio_publicacion_extra", { type: "number", inputMode: "decimal" })}
        {campo("Meses que puede publicar (vacío = siempre)", "publica_meses", { type: "number", inputMode: "numeric" })}
      </div>
      <label style={{ display: "grid", gap: 3, fontSize: 12 }}>
        <span style={{ opacity: .7 }}>Qué es, en una frase</span>
        <input className="adm-input" value={v.descripcion} onChange={(e) => setV((s) => ({ ...s, descripcion: e.target.value }))} />
      </label>
      <label style={{ display: "grid", gap: 3, fontSize: 12 }}>
        <span style={{ opacity: .7 }}>Qué incluye (una línea por viñeta)</span>
        <textarea className="adm-input" rows={4} value={v.incluye} onChange={(e) => setV((s) => ({ ...s, incluye: e.target.value }))} />
      </label>
      <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap", fontSize: 13 }}>
        <label><input type="checkbox" checked={v.permite_extras} onChange={(e) => setV((s) => ({ ...s, permite_extras: e.target.checked }))} /> Cobra extras al pasarse (si no, se corta)</label>
        <label><input type="checkbox" checked={v.visible} onChange={(e) => setV((s) => ({ ...s, visible: e.target.checked }))} /> Se muestra en /planes</label>
        <button type="button" className="btn btn-primary btn-sm" onClick={guardar} disabled={estado === "guardando"} style={{ marginLeft: "auto" }}>
          {estado === "guardando" ? "Guardando…" : "Guardar"}
        </button>
        {estado === "ok" && <span style={{ color: "var(--uk-green, #1f7a4d)" }}>Guardado ✓</span>}
        {estado === "error" && <span style={{ color: "#c33" }}>{msg}</span>}
      </div>
    </div>
  );
}
