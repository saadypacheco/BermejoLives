"use client";

import { useMemo, useState } from "react";
import { ponerHorarioEnLote, type ComercioPorVerificar } from "@/lib/api";

/**
 * Los comercios agrupados por CALLE, para cargar horarios de a cientos.
 *
 * De 1.248 comercios activos, 1.246 no tenían horario. Cargarlos de a uno no
 * iba a pasar nunca. Pero Bermejo se ordena sola por calle: la 23 de Marzo son
 * 139 y casi todos son mayoristas de ropa que abren de 6 a 16; la Barrientos
 * Ortuño son neumáticos y casas de cambio, que es otro horario. Elegís la
 * calle, destildás los rubros que no van, y ponés el horario a los que quedan.
 *
 * La calle sale del GPS contra OpenStreetMap (migración 0127/0128), no de la
 * dirección: 1.247 de 1.248 no tienen dirección cargada, y nadie va a tipear
 * mil.
 *
 * Los estilos van inline: el panel no carga `uruku.css`.
 */

/** Horarios que se repiten en Bermejo. Botones y no un desplegable: se tocan
 *  una vez por calle y con el dedo. */
const PRESETS: { etiqueta: string; valor: string }[] = [
  { etiqueta: "Mayorista · 6 a 16", valor: "Lun a Sáb 6-16" },
  { etiqueta: "Comercio · 8-12 y 14:30-20", valor: "Lun a Sáb 8-12 · 14:30-20" },
  { etiqueta: "Corrido · 8 a 20", valor: "Lun a Sáb 8-20" },
  { etiqueta: "Alimentos · 7 a 21", valor: "Lun a Dom 7-21" },
];

const SIN_CALLE = "(sin calle)";

type Grupo = {
  calle: string;
  items: ComercioPorVerificar[];
  conHorario: number;
  estimados: number;
};

export function AdminCalles({ comercios, onCambio }: {
  comercios: ComercioPorVerificar[];
  /** Para que la lista de afuera se entere y vuelva a pedir los datos. */
  onCambio: () => void;
}) {
  const [abierta, setAbierta] = useState<string | null>(null);

  const grupos = useMemo<Grupo[]>(() => {
    const m = new Map<string, ComercioPorVerificar[]>();
    for (const c of comercios) {
      const k = (c.calle ?? "").trim() || SIN_CALLE;
      const y = m.get(k);
      if (y) y.push(c); else m.set(k, [c]);
    }
    return [...m.entries()]
      .map(([calle, items]) => ({
        calle,
        items,
        conHorario: items.filter((c) => (c.horario ?? "").trim()).length,
        estimados: items.filter((c) => c.horario_estimado).length,
      }))
      .sort((a, b) => b.items.length - a.items.length);
  }, [comercios]);

  const sinHorarioTotal = comercios.filter((c) => !(c.horario ?? "").trim()).length;

  return (
    <div style={{ padding: 12, display: "grid", gap: 10 }}>
      <p style={{ color: "var(--txt-3)", fontSize: 13, margin: 0 }}>
        La calle sale del GPS de cada comercio. Abrí una, destildá los rubros que no correspondan
        y poné el horario a todos los demás de una vez.{" "}
        <b style={{ color: sinHorarioTotal ? "var(--amber)" : "var(--neon)" }}>
          {sinHorarioTotal} sin horario
        </b>{" "}
        de {comercios.length}.
      </p>

      {grupos.map((g) => (
        <FilaCalle key={g.calle} g={g}
                   abierta={abierta === g.calle}
                   onAbrir={() => setAbierta((x) => (x === g.calle ? null : g.calle))}
                   onCambio={onCambio} />
      ))}
    </div>
  );
}

function FilaCalle({ g, abierta, onAbrir, onCambio }: {
  g: Grupo; abierta: boolean; onAbrir: () => void; onCambio: () => void;
}) {
  const falta = g.items.length - g.conHorario;
  // Los rubros de la calle, del más común al menos. Es lo que decide si el
  // horario de la calle aplica: en la 23 de Marzo hay 55 de ropa y 10 baños
  // públicos, y los baños no abren de 6 a 16.
  const porRubro = useMemo(() => {
    const m = new Map<string, { nombre: string; items: ComercioPorVerificar[] }>();
    for (const c of g.items) {
      const slug = c.rubros?.slug ?? "";
      const nombre = c.rubros?.nombre ?? "Sin rubro";
      const y = m.get(slug) ?? { nombre, items: [] };
      y.items.push(c);
      m.set(slug, y);
    }
    return [...m.entries()].sort((a, b) => b[1].items.length - a[1].items.length);
  }, [g.items]);

  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
      <button type="button" onClick={onAbrir}
              style={{ width: "100%", display: "flex", gap: 12, alignItems: "center", padding: "12px 14px",
                       background: abierta ? "rgba(255,255,255,.03)" : "transparent",
                       border: "none", cursor: "pointer", textAlign: "left", color: "inherit" }}>
        <b style={{ fontSize: 15, flex: "1 1 auto", minWidth: 0 }}>{g.calle}</b>
        <span style={{ fontSize: 13, color: "var(--txt-3)", whiteSpace: "nowrap" }}>
          {g.items.length} comercios
        </span>
        {falta > 0 ? (
          <span style={{ fontSize: 12, fontWeight: 700, color: "var(--amber)", whiteSpace: "nowrap" }}>
            {falta} sin horario
          </span>
        ) : (
          <span style={{ fontSize: 12, fontWeight: 700, color: "var(--neon)", whiteSpace: "nowrap" }}>
            con horario{g.estimados ? ` · ${g.estimados} estimados` : ""}
          </span>
        )}
        <span style={{ color: "var(--txt-3)", fontSize: 12 }}>{abierta ? "▲" : "▼"}</span>
      </button>

      {abierta && <PanelCalle calle={g.calle} porRubro={porRubro} onCambio={onCambio} />}
    </div>
  );
}

function PanelCalle({ calle, porRubro, onCambio }: {
  calle: string;
  porRubro: [string, { nombre: string; items: ComercioPorVerificar[] }][];
  onCambio: () => void;
}) {
  // Arranca con TODO tildado menos lo que claramente no es un comercio con
  // horario de local (baños, cajeros, estacionamientos): esos vienen del mapa
  // de servicios y ponerles «6 a 16» sería inventar.
  const NO_LOCAL = new Set(["banos", "cajeros", "estacionamiento", "wifi", "taxis", "emergencias"]);
  const [elegidos, setElegidos] = useState<Set<string>>(
    () => new Set(porRubro.map(([s]) => s).filter((s) => !NO_LOCAL.has(s))),
  );
  const [horario, setHorario] = useState("");
  const [soloVacios, setSoloVacios] = useState(true);
  const [estimado, setEstimado] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const afectados = porRubro
    .filter(([slug]) => elegidos.has(slug))
    .flatMap(([, v]) => v.items)
    .filter((c) => (soloVacios ? !(c.horario ?? "").trim() : true));

  async function aplicar() {
    setErr(""); setMsg(""); setGuardando(true);
    try {
      const n = await ponerHorarioEnLote(afectados.map((c) => c.id), horario.trim(), estimado);
      setMsg(`Listo: ${n} comercios de ${calle} con horario «${horario.trim()}».`);
      onCambio();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  const toggle = (slug: string) =>
    setElegidos((s) => {
      const n = new Set(s);
      if (n.has(slug)) n.delete(slug); else n.add(slug);
      return n;
    });

  return (
    <div style={{ padding: "0 14px 14px", display: "grid", gap: 12 }}>
      <div>
        <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 6 }}>
          ¿A qué rubros de esta calle les va el mismo horario?
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {porRubro.map(([slug, v]) => {
            const on = elegidos.has(slug);
            const faltan = v.items.filter((c) => !(c.horario ?? "").trim()).length;
            return (
              <button key={slug || "sin"} type="button" onClick={() => toggle(slug)}
                      style={{ padding: "5px 10px", borderRadius: 999, fontSize: 12.5, cursor: "pointer",
                               border: `1px solid ${on ? "var(--neon)" : "var(--border)"}`,
                               background: on ? "rgba(57,255,158,.12)" : "transparent",
                               color: on ? "var(--neon)" : "var(--txt-3)" }}>
                {on ? "✓ " : ""}{v.nombre} ({v.items.length}{faltan !== v.items.length ? ` · ${faltan} sin` : ""})
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 6 }}>Horario</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
          {PRESETS.map((p) => (
            <button key={p.valor} type="button" onClick={() => setHorario(p.valor)}
                    style={{ padding: "5px 10px", borderRadius: 8, fontSize: 12.5, cursor: "pointer",
                             border: `1px solid ${horario === p.valor ? "var(--neon)" : "var(--border)"}`,
                             background: "transparent",
                             color: horario === p.valor ? "var(--neon)" : "var(--txt-2)" }}>
              {p.etiqueta}
            </button>
          ))}
        </div>
        <input className="adm-input" value={horario} onChange={(e) => setHorario(e.target.value)}
               placeholder="Lun a Sáb 6-16 · Dom 8-12" />
        <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginTop: 4 }}>
          Hora de Bolivia. Se puede escribir a mano: «Lun a Vie 8-12 · 15-19 · Sáb 8-13».
        </div>
      </div>

      <label style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 13, cursor: "pointer" }}>
        <input type="checkbox" checked={soloVacios} onChange={(e) => setSoloVacios(e.target.checked)} />
        <span>
          Sólo a los que <b>no tienen horario</b>
          <small style={{ display: "block", color: "var(--txt-3)" }}>
            Destildalo sólo si querés pisar los que ya tienen uno cargado.
          </small>
        </span>
      </label>

      <label style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 13, cursor: "pointer" }}>
        <input type="checkbox" checked={estimado} onChange={(e) => setEstimado(e.target.checked)} />
        <span>
          Marcarlo como <b>estimado</b>
          <small style={{ display: "block", color: "var(--txt-3)" }}>
            La ficha va a decir «horario habitual de la calle, confirmá antes de ir». Destildalo
            sólo si sabés que ese es el horario real de todos. Alguien que cruzó el puente y manejó
            veinte cuadras porque URUKU dijo «abierto» no vuelve.
          </small>
        </span>
      </label>

      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <button type="button" className="btn btn-primary" disabled={guardando || !horario.trim() || afectados.length === 0}
                onClick={aplicar}>
          {guardando ? "Guardando…" : `Poner el horario a ${afectados.length} comercios`}
        </button>
        {afectados.length === 0 && (
          <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>
            No queda ninguno para tocar con esta selección.
          </span>
        )}
      </div>

      {msg && <div style={{ color: "var(--neon)", fontSize: 13 }}>{msg}</div>}
      {err && <div style={{ color: "var(--pink)", fontSize: 13 }}>{err}</div>}
    </div>
  );
}
