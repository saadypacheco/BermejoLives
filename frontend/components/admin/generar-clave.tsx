"use client";

import { useState } from "react";
import { Ic } from "@/components/ic";
import { ClaveUnaVez } from "@/components/clave-una-vez";
import { adminGenerarClaveComercio } from "@/lib/api";
import { mensajeDeError } from "@/lib/acceso";

/**
 * «Generar clave nueva» del comercio, en Admin › Editar negocio. Sólo se monta
 * con el permiso `comercios.cuenta` (el servidor igual contesta 403 sin él).
 *
 * Pide confirmación (la clave anterior deja de servir), llama a
 * `POST /admin/comercio/{id}/clave` y muestra la clave UNA vez. Vive sólo en
 * el estado de este componente: no va a localStorage ni a la consola.
 */
export function GenerarClaveComercio({ comercioId, nombre }: { comercioId: string; nombre: string }) {
  const [paso, setPaso] = useState<"reposo" | "confirmar" | "generando">("reposo");
  const [clave, setClave] = useState<string | null>(null);
  const [err, setErr] = useState("");

  async function generar() {
    setPaso("generando"); setErr("");
    try { setClave(await adminGenerarClaveComercio(comercioId)); }
    catch (ex) { setErr(mensajeDeError(ex, "No se pudo generar la clave. Probá de nuevo.")); }
    finally { setPaso("reposo"); }
  }

  if (clave) {
    return (
      <ClaveUnaVez clave={clave} titulo={`Clave nueva de ${nombre}`} compacta onListo={() => setClave(null)} textoListo="Listo"
        aviso="Anotala y entregásela al dueño en un papel aparte; no se vuelve a mostrar. La clave anterior ya no sirve." />
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {paso === "confirmar" ? (
        <div role="alertdialog" aria-label="Confirmar clave nueva"
          style={{ display: "flex", flexDirection: "column", gap: 10, padding: 12, borderRadius: 12, border: "1px solid var(--amber)", background: "rgba(255,176,32,.08)" }}>
          <span style={{ fontSize: 13.5, color: "var(--txt)" }}>
            <Ic n="aviso" s={15} /> La clave anterior deja de servir. ¿Generar una clave nueva para {nombre}?
          </span>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="btn btn-primary btn-sm" style={{ minHeight: 44 }} onClick={generar}>Sí, generar clave nueva</button>
            <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} onClick={() => setPaso("reposo")}>Cancelar</button>
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} disabled={paso === "generando"}
            onClick={() => setPaso("confirmar")}>
            <Ic n="seguridad" s={14} /> {paso === "generando" ? "Generando…" : "Generar clave nueva"}
          </button>
          <span style={{ fontSize: 12, color: "var(--txt-3)" }}>Clave de acceso del comercio (se ve una sola vez)</span>
        </div>
      )}
      {err && <div role="alert" style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={14} /> {err}</div>}
    </div>
  );
}
