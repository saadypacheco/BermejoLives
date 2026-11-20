"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { adminEditarPlato, adminListarPlatos } from "@/lib/api";
import type { Ciudad } from "@/lib/types";
import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE, Cargando, Insignia } from "@/components/content/content-ui";
import {
  ESTADOS_PLATO, MAX_DESCRIPCION_PLATO, MAX_NOMBRE_PLATO, NOMBRE_TIPO_PLATO, cambiosDeEdicion, puedeAprobarPlato,
  type CambiosPlato, type EstadoPlato, type PlatoTipico,
} from "@/lib/platos-pure";

const CAMPO: React.CSSProperties = {
  width: "100%", padding: "8px 10px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--panel)",
  color: "var(--txt-1)", fontSize: 14, fontFamily: "inherit",
};

/**
 * Admin › «Platos típicos» (docs/home-ciudades.md §15): los platos, la repostería y las bebidas que importa
 * `importar_gastronomia` y que la IA describe con texto original. Quedan PENDIENTES hasta que alguien los revisa acá:
 * se puede corregir el nombre y el texto, aprobar (aparecen en `/{ciudad}/sabores`) y rechazar. Rechazar no borra nada
 * (borrado lógico): se puede volver a aprobar.
 */
export function PlatosPanel({ ciudad }: { ciudad: Ciudad | null }) {
  const [estado, setEstado] = useState<EstadoPlato>("pendiente");
  const [platos, setPlatos] = useState<PlatoTipico[]>([]);
  const [cargando, setCargando] = useState(true);
  const [err, setErr] = useState("");
  const [aviso, setAviso] = useState("");
  // Una respuesta vieja (otra ciudad u otro estado) no pisa la lista nueva.
  const pedido = useRef(0);
  const ciudadId = ciudad?.id ?? null;

  const cargar = useCallback(async () => {
    if (!ciudadId) { setPlatos([]); setCargando(false); return; }
    const mio = ++pedido.current;
    setCargando(true); setErr("");
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      setPlatos([]); setCargando(false);
      setErr("Sin conexión. Cuando vuelva internet, tocá «Reintentar».");
      return;
    }
    try {
      const filas = await adminListarPlatos(ciudadId, estado);
      if (mio !== pedido.current) return;
      setPlatos(filas);
    } catch (e) {
      if (mio !== pedido.current) return;
      // La lista anterior se va: con el error a la vista no se puede aprobar algo de otra ciudad.
      setPlatos([]);
      setErr(`No se pudieron cargar los platos: ${e instanceof Error ? e.message : "error desconocido"}`);
    } finally {
      if (mio === pedido.current) setCargando(false);
    }
  }, [ciudadId, estado]);

  useEffect(() => { setPlatos([]); setAviso(""); void cargar(); }, [cargar]);

  /** Guarda lo que cambió (y el estado, si va). La fila sale de la lista si ya no es del estado que se está viendo. */
  async function guardar(p: PlatoTipico, cambios: CambiosPlato): Promise<void> {
    await adminEditarPlato(p.id, cambios);
    const nuevo: PlatoTipico = { ...p, ...cambios };
    setPlatos((lista) => lista.flatMap((x) => (x.id !== p.id ? [x] : nuevo.estado === estado ? [nuevo] : [])));
    if (cambios.estado === "aprobado") setAviso(`«${nuevo.nombre}» ya está en la página de sabores (puede tardar hasta una hora en verse).`);
    else if (cambios.estado === "rechazado") setAviso(`«${nuevo.nombre}» se rechazó. Lo encontrás en «Rechazados» si querés volver a aprobarlo.`);
    else setAviso(`«${nuevo.nombre}» se guardó.`);
  }

  return (
    <div>
      <p style={{ color: "var(--txt-3)", fontSize: 13, lineHeight: 1.5, margin: "0 0 10px" }}>
        Platos, repostería y bebidas típicas de la ciudad, con un texto escrito por la IA a partir del nombre. Revisá que el texto sea
        correcto y no copie a la fuente; recién al <b>aprobar</b> aparecen en <code>/{ciudad?.slug ?? "ciudad"}/sabores</code>.
      </p>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
        {ESTADOS_PLATO.map((e) => (
          <button key={e.key} type="button" aria-pressed={estado === e.key} style={{ minHeight: 40 }}
                  className={`btn btn-sm ${estado === e.key ? "btn-primary" : "btn-ghost"}`} onClick={() => setEstado(e.key)}>
            {e.label}
          </button>
        ))}
      </div>

      {!ciudad && <Aviso tono="info">Elegí una ciudad en el selector de arriba: los platos se revisan de a una ciudad.</Aviso>}
      {ciudad && aviso && (
        <div style={{ marginBottom: 10 }}>
          <Aviso tono="ok" accion={<button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 40 }} onClick={() => setAviso("")}>Cerrar</button>}>
            {aviso}
          </Aviso>
        </div>
      )}
      {ciudad && cargando && <Cargando texto="Cargando platos…" />}
      {ciudad && err && (
        <Aviso tono="error" accion={<button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 40 }} onClick={() => void cargar()}>Reintentar</button>}>
          {err}
        </Aviso>
      )}
      {/* «Nada acá» sólo sin error: con la carga fallida afirmaría un vacío que nadie midió. */}
      {ciudad && !cargando && !err && platos.length === 0 && (
        <p style={{ color: "var(--txt-3)", fontSize: 13.5 }}>
          {estado === "pendiente"
            ? <>No hay platos pendientes. Se cargan en el servidor con <code>python -m app.services.importar_gastronomia --ciudad {ciudad.slug}</code>.</>
            : estado === "aprobado" ? "Todavía no hay platos aprobados en esta ciudad." : "No hay platos rechazados."}
        </p>
      )}
      {ciudad && !err && (
        <div style={{ display: "grid", gap: 12 }}>
          {platos.map((p) => <FilaPlato key={p.id} plato={p} onGuardar={(c) => guardar(p, c)} />)}
        </div>
      )}
    </div>
  );
}

function FilaPlato({ plato, onGuardar }: { plato: PlatoTipico; onGuardar: (cambios: CambiosPlato) => Promise<void> }) {
  const [nombre, setNombre] = useState(plato.nombre);
  const [descripcion, setDescripcion] = useState(plato.descripcion);
  const [ocupado, setOcupado] = useState(false);
  const [err, setErr] = useState("");

  const { cambios, error: errorEdicion } = cambiosDeEdicion(plato, { nombre, descripcion });
  const hayCambios = Object.keys(cambios).length > 0;
  const puedeAprobar = puedeAprobarPlato({ nombre, descripcion });

  async function enviar(extra: CambiosPlato) {
    if (errorEdicion) { setErr(errorEdicion); return; }
    setOcupado(true); setErr("");
    try {
      await onGuardar({ ...cambios, ...extra });
    } catch (e) {
      setErr(`No se pudo guardar: ${e instanceof Error ? e.message : "error desconocido"}`);
      setOcupado(false);
    }
  }

  const ESTADO_INSIGNIA = { pendiente: { tono: "aviso", icono: "reloj", texto: "Pendiente" }, aprobado: { tono: "ok", icono: "listo", texto: "Aprobado" }, rechazado: { tono: "error", icono: "aviso", texto: "Rechazado" } } as const;
  const ins = ESTADO_INSIGNIA[plato.estado];

  return (
    <div style={{ display: "grid", gap: 8, padding: 12, border: "1px solid var(--border)", borderRadius: 12, opacity: ocupado ? 0.6 : 1 }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <Insignia tono={ins.tono} icono={ins.icono}>{ins.texto}</Insignia>
        <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>{NOMBRE_TIPO_PLATO[plato.tipo]}</span>
        {plato.fuente_url && (
          <a href={plato.fuente_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12.5, marginLeft: "auto" }}>
            <Ic n="enlace" s={13} /> Ver la nota de origen
          </a>
        )}
      </div>
      <label style={{ display: "grid", gap: 4, fontSize: 12.5, color: "var(--txt-3)" }}>
        Nombre
        <input value={nombre} maxLength={MAX_NOMBRE_PLATO} onChange={(e) => setNombre(e.target.value)} style={CAMPO} />
      </label>
      <label style={{ display: "grid", gap: 4, fontSize: 12.5, color: "var(--txt-3)" }}>
        Texto (2 a 3 frases)
        <textarea value={descripcion} maxLength={MAX_DESCRIPCION_PLATO} rows={4} onChange={(e) => setDescripcion(e.target.value)} style={{ ...CAMPO, resize: "vertical" }} />
      </label>
      {!puedeAprobar && plato.estado !== "aprobado" && (
        <p style={{ margin: 0, fontSize: 12.5, color: "var(--amber)" }}><Ic n="aviso" s={13} /> Falta el texto: sin él no se puede aprobar.</p>
      )}
      {err && <p role="alert" style={{ margin: 0, fontSize: 13, color: "var(--pink)" }}><Ic n="aviso" s={13} /> {err}</p>}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {plato.estado !== "aprobado" && (
          <button type="button" className="btn btn-primary" style={BTN_GRANDE} disabled={ocupado || !puedeAprobar}
                  onClick={() => void enviar({ estado: "aprobado" })}>
            <Ic n="listo" s={16} /> Aprobar
          </button>
        )}
        {plato.estado !== "rechazado" && (
          <button type="button" className="btn btn-ghost" style={BTN_GRANDE} disabled={ocupado}
                  onClick={() => void enviar({ estado: "rechazado" })}>
            <Ic n="cerrar" s={16} /> Rechazar
          </button>
        )}
        {hayCambios && (
          <button type="button" className="btn btn-ghost" style={BTN_GRANDE} disabled={ocupado} onClick={() => void enviar({})}>
            <Ic n="si" s={16} /> Guardar cambios
          </button>
        )}
      </div>
    </div>
  );
}
