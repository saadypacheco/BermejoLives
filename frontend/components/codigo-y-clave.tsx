"use client";

import { useState } from "react";
import { Ic } from "@/components/ic";
import { ClaveUnaVez } from "@/components/clave-una-vez";
import { generarClaveNueva } from "@/lib/comercio";

/**
 * «Tu código y tu clave», en Mi comercio.
 *
 * El código (`URUKU-KPXN`) NO es una clave: está impreso en el volante y se
 * manda en el grupo. Sólo sirve para publicar (y eso va a moderación) y para
 * atar un grupo de WhatsApp al negocio. La clave de 6 números es lo que abre el
 * panel; el servidor sólo guarda su hash, así que no se puede mostrar de nuevo:
 * si se perdió, se genera otra (y la anterior deja de servir).
 */
export function CodigoYClave({ codigoFormateado }: { codigoFormateado?: string | null }) {
  const [paso, setPaso] = useState<"reposo" | "confirmar" | "generando">("reposo");
  const [clave, setClave] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const [copiado, setCopiado] = useState(false);

  async function copiarCodigo() {
    if (!codigoFormateado) return;
    try { await navigator.clipboard.writeText(codigoFormateado); setCopiado(true); } catch { /* el código está a la vista */ }
  }

  async function generar() {
    setPaso("generando"); setErr("");
    try { setClave(await generarClaveNueva()); setPaso("reposo"); }
    catch (ex) {
      setErr(ex instanceof TypeError ? "Sin conexión. Revisá tu internet y probá de nuevo." : ex instanceof Error ? ex.message : "No se pudo generar la clave.");
      setPaso("reposo");
    }
  }

  if (clave) {
    return (
      <ClaveUnaVez clave={clave} titulo="Tu clave nueva"
        aviso="Guardala: no se vuelve a mostrar. La clave anterior ya no sirve. Con tu celular y esta clave entrás a tu panel."
        onListo={() => setClave(null)} />
    );
  }

  return (
    <div className="glass" style={{ padding: 20, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <h3 style={{ margin: 0 }}>Tu código y tu clave</h3>

      {codigoFormateado && (
        <div>
          <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700 }}>TU CÓDIGO</div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginTop: 4 }}>
            <span style={{ fontSize: 26, fontWeight: 800, letterSpacing: ".04em", color: "var(--neon)", fontFamily: "monospace" }}
              aria-label={`Código ${codigoFormateado}`}>{codigoFormateado}</span>
            <button type="button" className="btn btn-sm" onClick={copiarCodigo} style={{ border: "1px solid var(--stroke)" }}>
              {copiado ? <><Ic n="listo" s={14} /> Copiado</> : "Copiar"}
            </button>
          </div>
          <p style={{ color: "var(--txt-2)", fontSize: 13.5, margin: "6px 0 0" }}>
            Mandalo en un WhatsApp para publicar o para atar tu grupo.
          </p>
        </div>
      )}

      <div style={{ borderTop: codigoFormateado ? "1px solid var(--stroke)" : undefined, paddingTop: codigoFormateado ? 12 : 0 }}>
        <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700 }}>TU CLAVE</div>
        <p style={{ color: "var(--txt-2)", fontSize: 13.5, margin: "4px 0 10px" }}>
          Con tu celular y tu clave de 6 números entrás a este panel. No la podemos mostrar de nuevo;
          si la perdiste, generá una nueva (la anterior deja de servir).
        </p>

        {paso === "confirmar" ? (
          <div role="alertdialog" aria-label="Confirmar clave nueva"
            style={{ display: "flex", flexDirection: "column", gap: 10, padding: 12, borderRadius: 12, border: "1px solid var(--amber)", background: "rgba(255,176,32,.08)" }}>
            <span style={{ fontSize: 13.5, color: "var(--txt)" }}>
              <Ic n="aviso" s={15} /> Si generás una clave nueva, la que usabas deja de funcionar. ¿Seguimos?
            </span>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button type="button" className="btn btn-primary btn-sm" onClick={generar}>Sí, generar clave nueva</button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPaso("reposo")}>Cancelar</button>
            </div>
          </div>
        ) : (
          <button type="button" className="btn btn-sm" disabled={paso === "generando"} onClick={() => setPaso("confirmar")}
            style={{ border: "1px solid var(--stroke)" }}>
            {paso === "generando" ? "Generando…" : <><Ic n="seguridad" s={15} /> Generar clave nueva</>}
          </button>
        )}
        {err && <div role="alert" style={{ color: "var(--pink)", fontSize: 13, marginTop: 8 }}><Ic n="aviso" s={14} /> {err}</div>}
      </div>
    </div>
  );
}
