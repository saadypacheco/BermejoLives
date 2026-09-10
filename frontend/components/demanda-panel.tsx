"use client";

import { useCallback, useEffect, useState } from "react";
import { getDemanda, type Demanda } from "@/lib/api";

/**
 * Qué busca la gente en Bermejo y qué no encuentra.
 *
 * POR QUÉ ESTA PANTALLA ANTES QUE CUALQUIER AGENTE
 * ================================================
 * Es lo único de Uruku AI que se puede construir hoy: no necesita catálogo, ni
 * modelo de IA, ni permisos de Meta. Las búsquedas ya se registran.
 *
 * Y antes que un producto es una herramienta de venta. Lo que se le lleva a un
 * comerciante no es el ranking —eso le importa a URUKU, no a él— sino la lista
 * de lo que NO se encontró: demanda que hoy se va de la ciudad sin comprar.
 */
export function DemandaPanel() {
  const [dias, setDias] = useState(7);
  const [d, setD] = useState<Demanda | null>(null);
  const [err, setErr] = useState("");
  const [cargando, setCargando] = useState(true);
  const [copiado, setCopiado] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try { setD(await getDemanda(dias)); setErr(""); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo cargar"); }
    finally { setCargando(false); }
  }, [dias]);

  useEffect(() => { cargar(); }, [cargar]);

  const copiar = async () => {
    if (!d?.frase) return;
    try {
      await navigator.clipboard.writeText(d.frase);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch { /* sin portapapeles: la frase igual se ve y se puede leer */ }
  };

  const lista = (filas: Demanda["top"], campo: "veces" | "sin_resultado") => {
    const max = Math.max(1, ...filas.map((f) => f[campo]));
    return (
      <div style={{ padding: "4px 16px 16px", display: "flex", flexDirection: "column", gap: 6 }}>
        {filas.length === 0 && (
          <span style={{ color: "var(--txt-3)", fontSize: 13 }}>
            Nada todavía en estos {dias} días.
          </span>
        )}
        {filas.map((f) => (
          <div key={f.termino} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 13, minWidth: 160, overflow: "hidden",
                           textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {f.termino}
            </span>
            {/* La barra hace comparable de un vistazo lo que una columna de
                números obliga a leer entero. */}
            <span style={{ flex: 1, height: 8, background: "var(--line)", borderRadius: 4 }}>
              <span style={{
                display: "block", height: "100%", borderRadius: 4,
                width: `${(f[campo] / max) * 100}%`,
                background: campo === "sin_resultado" ? "var(--amber)" : "var(--neon)",
              }} />
            </span>
            <b style={{ fontSize: 13, minWidth: 30, textAlign: "right" }}>{f[campo]}</b>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {err && <div className="panel-card glass" style={{ padding: 14, color: "var(--pink)", fontSize: 13 }}>{err}</div>}

      <div className="panel-card glass">
        <div className="ph">
          <h3>Qué busca la gente</h3>
          <span style={{ color: "var(--txt-3)", fontSize: 12.5 }}>
            {d ? `${d.busquedas} búsquedas · ${d.terminos} términos` : "…"}
          </span>
        </div>
        <div style={{ display: "flex", gap: 8, padding: "12px 16px", flexWrap: "wrap" }}>
          {[7, 30, 90].map((n) => (
            <button key={n} className={`btn btn-sm ${dias === n ? "btn-primary" : "btn-ghost"}`}
                    onClick={() => setDias(n)}>
              {n} días
            </button>
          ))}
          <button className="btn btn-ghost btn-sm" onClick={cargar} disabled={cargando}>
            {cargando ? "…" : "↻ Actualizar"}
          </button>
        </div>
      </div>

      {/* La frase para decir en el mostrador. Es el producto de esta pantalla:
          el resto son números, esto es una conversación que se puede tener. */}
      {d?.frase && (
        <div className="panel-card glass" style={{ padding: 16 }}>
          <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 6 }}>
            Para decirle a un comerciante
          </div>
          <div style={{ fontSize: 16, lineHeight: 1.4 }}>«{d.frase}»</div>
          <button className="btn btn-sm btn-ghost" style={{ marginTop: 10 }} onClick={copiar}>
            {copiado ? "✓ Copiada" : "Copiar"}
          </button>
        </div>
      )}

      <div className="panel-card glass">
        <div className="ph">
          <h3>No encontraron nada</h3>
          <span style={{ color: "var(--amber)", fontSize: 12.5 }}>
            {d?.sin_resultado ?? 0} búsquedas
          </span>
        </div>
        <div style={{ padding: "10px 16px 0", fontSize: 12, color: "var(--txt-3)" }}>
          Es lo que vale de acá: demanda que hoy se va sin comprar. Cada línea es un
          local que falta, o uno que está y no publicó lo que vende.
        </div>
        {lista(d?.oportunidades ?? [], "sin_resultado")}
      </div>

      <div className="panel-card glass">
        <div className="ph"><h3>Lo más buscado</h3></div>
        {lista(d?.top ?? [], "veces")}
        {!!d?.descartados_por_tecleo && (
          <div style={{ padding: "0 16px 14px", fontSize: 11.5, color: "var(--txt-3)" }}>
            Se descartaron {d.descartados_por_tecleo} términos por ser tecleo a medio
            escribir («zap» de «zapatillas»). Si algún día son la mayoría, el buscador
            está registrando de más y hay que arreglarlo allá.
          </div>
        )}
      </div>
    </div>
  );
}
