"use client";

/**
 * La ficha de una calle tocada en el mapa: qué calle es, cuánto está cubierta,
 * cuántos comercios tiene, quién pasó por última vez, y los botones para
 * marcarla. Sirve igual al panel y a la app del agente (spec docs/mapa-calles.md).
 *
 * El estado se dice con texto + ícono + trazo en el mapa, nunca sólo con color.
 * Los estilos van inline porque el panel de administración no carga `uruku.css`.
 */
import { useEffect, useState } from "react";
import { Ic, type NombreIcono } from "@/components/ic";
import {
  COLOR_CALLE, ESTADOS_CALLE, ETIQUETA_CALLE, TRAZO_CALLE, fechaCalle, kmTxt, nombreCalle, quienCorto,
  type EstadoCalle, type EstadoMarca, type TramoCalle,
} from "@/lib/calles";

export const ICONO_ESTADO_CALLE: Record<EstadoCalle, NombreIcono> = {
  recorrida: "listo", parcial: "reloj", pendiente: "aviso", sin_comercios: "inicio",
};

/** El estado como etiqueta: ícono + texto + color. */
export function EstadoCalleTag({ estado }: { estado: EstadoCalle }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12.5, fontWeight: 700, color: COLOR_CALLE[estado], whiteSpace: "nowrap" }}>
      <Ic n={ICONO_ESTADO_CALLE[estado]} s={15} /> {ETIQUETA_CALLE[estado]}
    </span>
  );
}

/** La leyenda del mapa: color, trazo de muestra, ícono y texto. El color solo no
 *  alcanza (daltonismo, sol en la pantalla). Con `porEstado` suma cuántos hay. */
export function LeyendaCalles({ porEstado }: { porEstado?: Record<EstadoCalle, { n: number; km: number }> }) {
  return (
    <ul aria-label="Leyenda del mapa" style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "6px 12px" }}>
      {ESTADOS_CALLE.map((e) => (
        <li key={e} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12.5, color: "var(--txt-2)" }}>
          <svg width="30" height="8" aria-hidden>
            <line x1="2" y1="4" x2="28" y2="4" stroke={COLOR_CALLE[e]} strokeWidth="5" strokeLinecap="round"
                  strokeDasharray={TRAZO_CALLE[e]?.split(" ").map((x) => Number(x) / 2).join(" ")} />
          </svg>
          <Ic n={ICONO_ESTADO_CALLE[e]} s={14} />
          <span><b>{ETIQUETA_CALLE[e]}</b>{porEstado ? ` · ${porEstado[e].n} (${kmTxt(porEstado[e].km)} km)` : ""}</span>
        </li>
      ))}
    </ul>
  );
}

const BOTONES: { estado: EstadoMarca; texto: string; icono: NombreIcono }[] = [
  { estado: "recorrida", texto: "Recorrida", icono: "listo" },
  { estado: "sin_comercios", texto: "Sin comercios", icono: "inicio" },
  { estado: "pendiente", texto: "Pendiente", icono: "aviso" },
];

export function CallePanel({ tramo, onMarcar, onCerrar, verQuien = true }: {
  tramo: TramoCalle;
  /** Marca la calle. Si lanza, el mensaje se muestra y la calle queda como estaba. */
  onMarcar: (estado: EstadoMarca, nota: string) => Promise<void>;
  onCerrar: () => void;
  /** El agente ve sólo la parte del nombre antes de la @; el admin ve el actor completo. */
  verQuien?: boolean;
}) {
  const [nota, setNota] = useState("");
  const [ocupado, setOcupado] = useState<EstadoMarca | null>(null);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");

  // Otra calle: la nota y los avisos de la anterior no le corresponden.
  useEffect(() => { setNota(""); setErr(""); setOk(""); setOcupado(null); }, [tramo.id]);

  async function marcar(estado: EstadoMarca) {
    setErr(""); setOk(""); setOcupado(estado);
    try {
      await onMarcar(estado, nota.trim());
      setOk(`Marcada como «${ETIQUETA_CALLE[estado].toLowerCase()}».`);
      setNota("");
    } catch (e) {
      // fetch sin red lanza TypeError («Failed to fetch» / «Load failed»); el
      // servidor, en cambio, contesta con un error que ya trae su mensaje.
      const sinRed = e instanceof TypeError || (typeof navigator !== "undefined" && navigator.onLine === false);
      setErr(sinRed
        ? "Sin señal: no se pudo marcar. La marca se hace con conexión, probá de nuevo cuando vuelva."
        : e instanceof Error && e.message ? e.message : "No se pudo marcar la calle.");
    } finally {
      setOcupado(null);
    }
  }

  const quien = (q: string | null) => (q ? (verQuien ? quienCorto(q) : "") : "");
  const ult = tramo.ultimo;
  const m = tramo.marca;
  const largo = tramo.longitud_m >= 1000 ? `${(tramo.longitud_m / 1000).toFixed(1).replace(".", ",")} km` : `${Math.round(tramo.longitud_m)} m`;

  return (
    <section aria-label={`Calle ${nombreCalle(tramo)}`}
             style={{ border: "1px solid var(--stroke)", borderLeft: `5px solid ${COLOR_CALLE[tramo.estado]}`, borderRadius: 12, padding: 12,
                      background: "var(--panel, rgba(255,255,255,.04))", display: "grid", gap: 8, color: "var(--txt)" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "flex-start", justifyContent: "space-between" }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 800, fontSize: 16, overflowWrap: "anywhere", color: tramo.nombre ? "var(--txt)" : "var(--txt-3)" }}>
            {nombreCalle(tramo)}
          </div>
          <div style={{ marginTop: 2 }}><EstadoCalleTag estado={tramo.estado} /></div>
        </div>
        <button type="button" onClick={onCerrar} aria-label="Cerrar la ficha de la calle"
                style={{ minWidth: 44, minHeight: 44, display: "grid", placeItems: "center", background: "transparent", border: "none", color: "var(--txt-2)", cursor: "pointer", flexShrink: 0 }}>
          <Ic n="cerrar" s={18} />
        </button>
      </div>

      <dl style={{ margin: 0, display: "grid", gridTemplateColumns: "auto 1fr", gap: "3px 12px", fontSize: 13, color: "var(--txt-2)" }}>
        <dt style={{ color: "var(--txt-3)" }}>Cobertura</dt>
        <dd style={{ margin: 0 }}><b>{Math.round(tramo.cobertura)} %</b> de la calle tiene un comercio cerca</dd>
        <dt style={{ color: "var(--txt-3)" }}>Comercios</dt>
        <dd style={{ margin: 0 }}><b>{tramo.comercios}</b> · tramo de {largo}</dd>
        <dt style={{ color: "var(--txt-3)" }}>Último paso</dt>
        <dd style={{ margin: 0 }}>
          {ult
            ? <><b>{fechaCalle(ult.fecha) || "fecha sin dato"}</b>{quien(ult.quien) ? ` · ${quien(ult.quien)}` : ""}</>
            : "Nadie cargó nada acá todavía"}
        </dd>
        {m && (
          <>
            <dt style={{ color: "var(--txt-3)" }}>Marca</dt>
            <dd style={{ margin: 0 }}>
              «{ETIQUETA_CALLE[m.estado]}»{fechaCalle(m.created_at) ? ` el ${fechaCalle(m.created_at)}` : ""}{quien(m.actor) ? ` · ${quien(m.actor)}` : ""}
              {m.nota ? <span style={{ display: "block", color: "var(--txt-3)", fontStyle: "italic", overflowWrap: "anywhere" }}>{m.nota}</span> : null}
            </dd>
          </>
        )}
      </dl>

      <label style={{ display: "grid", gap: 3, fontSize: 12, color: "var(--txt-3)" }}>
        Nota (opcional)
        <input className="adm-input" value={nota} maxLength={200} onChange={(e) => setNota(e.target.value)}
               placeholder="Ej.: son casas, no hay locales" style={{ minHeight: 44 }} />
      </label>

      <div role="group" aria-label="Marcar la calle" style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {BOTONES.map((b) => {
          const vigente = m?.estado === b.estado;
          return (
            <button key={b.estado} type="button" disabled={ocupado !== null} onClick={() => marcar(b.estado)}
                    aria-pressed={vigente}
                    style={{ flex: "1 1 110px", minHeight: 48, padding: "8px 10px", borderRadius: 10, cursor: ocupado ? "wait" : "pointer", fontWeight: 700, fontSize: 13.5,
                             display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6,
                             border: `2px solid ${vigente ? COLOR_CALLE[b.estado] : "var(--stroke-2, var(--stroke))"}`,
                             background: vigente ? "rgba(128,128,128,.14)" : "transparent", color: "var(--txt)", opacity: ocupado && ocupado !== b.estado ? 0.55 : 1 }}>
              <Ic n={ocupado === b.estado ? "actualizar" : b.icono} s={16} /> {ocupado === b.estado ? "Guardando…" : b.texto}
            </button>
          );
        })}
      </div>

      {ok && <div role="status" style={{ color: "var(--neon)", fontSize: 13 }}><Ic n="listo" s={14} /> {ok}</div>}
      {err && <div role="alert" style={{ color: "var(--pink, #e03a3e)", fontSize: 13 }}><Ic n="aviso" s={14} /> {err}</div>}
    </section>
  );
}
