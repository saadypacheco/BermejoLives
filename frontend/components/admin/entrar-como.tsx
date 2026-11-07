"use client";

import { useState } from "react";
import { Ic } from "@/components/ic";
import { adminEntrarComoComercio } from "@/lib/api";
import { getComercioSession, guardarEntradaAdmin } from "@/lib/comercio";
import { sesionAjena } from "@/lib/entrar-como";
import { mensajeDeError } from "@/lib/acceso";

/**
 * «Entrar como este comercio», en Admin › Editar negocio. Sólo se monta con el permiso `equipo` (el servidor
 * igual contesta 403 sin él).
 *
 * Confirma (con un motivo opcional que queda registrado), pide `POST /admin/comercios/{id}/entrar` y abre
 * «Mi comercio» en una pestaña NUEVA con la sesión de comerciante de 30 minutos. La sesión del admin no se toca.
 * Si en este navegador ya hay otra sesión de comerciante, avisa antes de reemplazarla.
 */
export function EntrarComoComercio({ comercioId, nombre }: { comercioId: string; nombre: string }) {
  const [paso, setPaso] = useState<"reposo" | "confirmar" | "entrando" | "listo">("reposo");
  const [motivo, setMotivo] = useState("");
  const [ajena, setAjena] = useState<string | null>(null);
  const [err, setErr] = useState("");

  function pedirConfirmacion() {
    setErr("");
    let actual = null;
    try { actual = getComercioSession(); } catch { /* almacenamiento bloqueado */ }
    setAjena(sesionAjena(actual, comercioId));
    setPaso("confirmar");
  }

  async function entrar() {
    setPaso("entrando"); setErr("");
    // La pestaña se abre ACÁ, con el clic: después del pedido el navegador la bloquearía por no venir de un gesto.
    const pestana = window.open("about:blank", "_blank");
    try {
      const entrada = await adminEntrarComoComercio(comercioId, motivo);
      guardarEntradaAdmin(entrada);
      if (pestana) { pestana.location.href = "/mi-comercio"; setPaso("reposo"); setMotivo(""); }
      else setPaso("listo"); // el navegador bloqueó la ventana: queda el enlace para abrirla a mano
    } catch (ex) {
      pestana?.close();
      setErr(mensajeDeError(ex, "No se pudo entrar al comercio. Probá de nuevo."));
      setPaso("confirmar");
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {paso === "confirmar" || paso === "entrando" ? (
        <div role="alertdialog" aria-label="Confirmar entrada como comercio"
          style={{ display: "flex", flexDirection: "column", gap: 10, padding: 12, borderRadius: 12, border: "1px solid var(--amber)", background: "rgba(255,176,32,.08)" }}>
          <span style={{ fontSize: 13.5, color: "var(--txt)" }}>
            <Ic n="aviso" s={15} /> Vas a entrar a «{nombre}» como si fueras el dueño, durante 30 minutos. Todo lo que cambies queda registrado a tu nombre.
          </span>
          {ajena && (
            <span role="alert" style={{ fontSize: 13.5, color: "var(--txt)" }}>
              <Ic n="aviso" s={15} /> En este navegador ya hay una sesión de «{ajena}» abierta en Mi comercio: se va a reemplazar.
            </span>
          )}
          <label style={{ fontSize: 12, color: "var(--txt-3)" }}>Motivo (opcional)
            <input className="adm-input" style={{ marginTop: 4 }} value={motivo} maxLength={200} disabled={paso === "entrando"}
              onChange={(e) => setMotivo(e.target.value)} placeholder="Ej.: ayudar a cargar las fotos" />
          </label>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="btn btn-primary btn-sm" style={{ minHeight: 44 }} disabled={paso === "entrando"} onClick={entrar}>
              {paso === "entrando" ? "Entrando…" : "Sí, entrar"}
            </button>
            <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} disabled={paso === "entrando"} onClick={() => setPaso("reposo")}>Cancelar</button>
          </div>
        </div>
      ) : paso === "listo" ? (
        <div role="status" style={{ display: "flex", flexDirection: "column", gap: 8, padding: 12, borderRadius: 12, border: "1px solid var(--stroke)" }}>
          <span style={{ fontSize: 13.5 }}><Ic n="listo" s={15} /> Listo, pero el navegador bloqueó la pestaña nueva. Abrila desde acá:</span>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <a className="btn btn-primary btn-sm" style={{ minHeight: 44 }} href="/mi-comercio" target="_blank" rel="noopener" onClick={() => setPaso("reposo")}>
              <Ic n="abrir" s={14} /> Abrir Mi comercio
            </a>
            <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} onClick={() => setPaso("reposo")}>Cerrar</button>
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} onClick={pedirConfirmacion}>
            <Ic n="abrir" s={14} /> Entrar como este comercio
          </button>
          <span style={{ fontSize: 12, color: "var(--txt-3)" }}>Abre «Mi comercio» en otra pestaña, 30 minutos, a tu nombre</span>
        </div>
      )}
      {err && <div role="alert" style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={14} /> {err}</div>}
    </div>
  );
}
