"use client";

import { useEffect, useState } from "react";
import { Ic } from "@/components/ic";
import { getConsentComercio, guardarConsentComercio, mensajeContent, type SocialConsentResponse } from "@/lib/content";
import { fechaBo } from "@/lib/content-pure";

/**
 * Mi comercio › Perfil: el interruptor con el que el comerciante autoriza (o
 * deja de autorizar) a URUKU a mostrar su comercio y sus fotos en sus redes
 * (docs/contenido-redes-tecnico.md §9.6). Cada cambio queda con fecha en una
 * bitácora del lado del servidor.
 *
 * Al apagarlo se pide confirmación: URUKU deja de armar videos de su comercio.
 */
export function SocialConsentToggle() {
  const [c, setC] = useState<SocialConsentResponse | null>(null);
  const [err, setErr] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [cargando, setCargando] = useState(true);

  function cargar() {
    setCargando(true); setErr("");
    getConsentComercio()
      .then(setC)
      .catch((ex) => setErr(mensajeContent(ex, "No se pudo cargar tu autorización")))
      .finally(() => setCargando(false));
  }
  useEffect(cargar, []);

  const activo = c?.granted === true;

  async function cambiar() {
    if (!c || guardando) return;
    const nuevo = !activo;
    if (!nuevo && !window.confirm("Si lo apagás, no armamos más videos de tu comercio. Lo que ya se publicó lo borramos si nos lo pedís por WhatsApp.")) return;
    setGuardando(true); setErr("");
    try { setC(await guardarConsentComercio(nuevo)); }
    catch (ex) { setErr(mensajeContent(ex, "No se pudo guardar tu autorización")); }
    finally { setGuardando(false); }
  }

  return (
    <div className="glass" style={{ padding: "14px 18px", borderRadius: 16, display: "grid", gap: 8 }}>
      <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700 }}>REDES DE URUKU</div>

      {cargando && !c && <p style={{ margin: 0, fontSize: 13.5, color: "var(--txt-3)" }}>Cargando…</p>}

      {c && (
        <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
          <button type="button" role="switch" aria-checked={activo} aria-label="Autorizo a URUKU a mostrar mi comercio y mis fotos en sus redes"
                  onClick={() => void cambiar()} disabled={guardando}
                  style={{ flex: "none", width: 58, height: 34, borderRadius: 17, border: "1px solid var(--stroke)", cursor: "pointer", position: "relative", padding: 0,
                           background: activo ? "var(--neon)" : "var(--panel)", transition: "background .15s" }}>
            <span aria-hidden style={{ position: "absolute", top: 3, left: activo ? 27 : 3, width: 26, height: 26, borderRadius: 13, background: "#fff", boxShadow: "0 1px 3px rgba(0,0,0,.4)", transition: "left .15s" }} />
          </button>
          <div style={{ minWidth: 0 }}>
            <b style={{ fontSize: 14 }}>Autorizo a URUKU a mostrar mi comercio y mis fotos en sus redes</b>
            <div style={{ fontSize: 12.5, color: "var(--txt-3)", marginTop: 2 }}>
              {guardando
                ? "Guardando…"
                : activo
                  ? <><Ic n="listo" s={13} /> Autorizado{c.recorded_at ? ` el ${fechaBo(c.recorded_at)}` : ""}</>
                  : <><Ic n="cerrar" s={13} /> {c.granted === false ? `No autorizado${c.recorded_at ? ` (lo retiraste el ${fechaBo(c.recorded_at)})` : ""}` : "Todavía no autorizaste"}</>}
            </div>
          </div>
        </div>
      )}

      {err && (
        <div role="alert" style={{ fontSize: 13, color: "var(--pink)" }}>
          <Ic n="aviso" s={14} /> {err}{" "}
          {!c && <button type="button" className="link-more" style={{ minHeight: 44 }} onClick={cargar}>Reintentar</button>}
        </div>
      )}
    </div>
  );
}
