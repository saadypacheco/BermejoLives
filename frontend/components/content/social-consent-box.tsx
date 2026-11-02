"use client";

import { useState } from "react";
import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE, Insignia, Cargando } from "@/components/content/content-ui";
import {
  mensajeContent, type ConsentApi, type SocialConsentResponse, type SocialConsentRevokeResponse, type SocialConsentUpdate,
} from "@/lib/content";
import { CONSENT_VIA_LABEL, fechaBo, fechaCortaBo, redLabel } from "@/lib/content-pure";

/** Lo que devuelve el backend al guardar: la autorización, o (al retirar) además
 *  lo que hay que borrar a mano de las redes. */
function esRetiro(r: SocialConsentResponse | SocialConsentRevokeResponse): r is SocialConsentRevokeResponse {
  return typeof (r as SocialConsentRevokeResponse).pieces_skipped === "number";
}

const VIAS: { v: SocialConsentUpdate["via"]; t: string }[] = [
  { v: "whatsapp_reply", t: "Me lo dijo por WhatsApp" },
  { v: "admin", t: "Me lo dijo en persona o por teléfono" },
  { v: "subscription", t: "Lo aceptó al suscribirse" },
];

/**
 * La autorización de un comercio para aparecer en las redes y la página de URUKU (§1.6 de la
 * spec funcional; es una BITÁCORA: cada alta o retiro queda con fecha y vía).
 *
 * Lo usan el Banco de contenido, el detalle de un suscriptor y «Completar
 * comercio» de la app de campo; por eso el guardado llega inyectado (`api`): el
 * panel y el agente hablan con endpoints y tokens distintos.
 *
 * Sin autorización las fotos se guardan igual, pero ninguna pieza sale en redes.
 */
export function SocialConsentBox({ consent, api, onChange, compacto, estadoDesconocido }: {
  consent: SocialConsentResponse;
  api: ConsentApi;
  onChange: (c: SocialConsentResponse) => void;
  /** Sin el recuadro (cuando ya va dentro de otra tarjeta). */
  compacto?: boolean;
  /** Todavía no se leyó la autorización del servidor: se dice «sin dato» en vez
   *  de afirmar que falta. */
  estadoDesconocido?: boolean;
}) {
  const [abierto, setAbierto] = useState(false);
  const [via, setVia] = useState<SocialConsentUpdate["via"]>("whatsapp_reply");
  const [nota, setNota] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [err, setErr] = useState("");
  const [retiro, setRetiro] = useState<SocialConsentRevokeResponse | null>(null);
  const [historial, setHistorial] = useState<SocialConsentResponse[] | null>(null);
  const [cargandoHist, setCargandoHist] = useState(false);

  const vigente = consent.granted === true;
  const retirada = consent.granted === false;

  async function guardar(granted: boolean) {
    setGuardando(true); setErr(""); setRetiro(null);
    try {
      // Al retirar la vía es «admin»: la persona de URUKU que lo registra.
      const r = await api.guardar(granted, granted ? via : "admin", nota.trim() || null);
      if (esRetiro(r)) { setRetiro(r); onChange(r.consent); }
      else onChange(r);
      setAbierto(false); setNota(""); setHistorial(null);
    } catch (ex) { setErr(mensajeContent(ex, "No se pudo guardar la autorización")); }
    finally { setGuardando(false); }
  }

  function retirar() {
    if (!window.confirm("¿Retirar la autorización de redes y página de este comercio? Las piezas planificadas o listas pasan a «saltadas» y no se arman más videos suyos.")) return;
    void guardar(false);
  }

  async function verHistorial() {
    if (!api.historial) return;
    if (historial) { setHistorial(null); return; }
    setCargandoHist(true); setErr("");
    try { setHistorial(await api.historial()); }
    catch (ex) { setErr(mensajeContent(ex, "No se pudo cargar el historial")); }
    finally { setCargandoHist(false); }
  }

  return (
    <div style={{ display: "grid", gap: 10, ...(compacto ? {} : { padding: 12, border: "1px solid var(--stroke)", borderRadius: 12 }) }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <b style={{ fontSize: 13.5 }}>Redes y página de URUKU:</b>
        {vigente && (
          <Insignia tono="ok" icono="listo">
            AUTORIZADO {fechaCortaBo(consent.recorded_at)}{consent.via ? ` (${CONSENT_VIA_LABEL[consent.via] ?? consent.via})` : ""}
          </Insignia>
        )}
        {retirada && <Insignia tono="error" icono="aviso">RETIRADA {fechaCortaBo(consent.recorded_at)}</Insignia>}
        {consent.granted === null && !estadoDesconocido && <Insignia tono="error" icono="aviso">SIN AUTORIZAR</Insignia>}
        {consent.granted === null && estadoDesconocido && <Insignia tono="info" icono="dato">SIN DATO TODAVÍA</Insignia>}
      </div>

      {!vigente && !abierto && (
        <p style={{ margin: 0, fontSize: 12.5, color: "var(--txt-3)", lineHeight: 1.4 }}>
          Sin la autorización del comercio no sale ninguna pieza en las redes ni en la página de URUKU. Las fotos se guardan igual.
        </p>
      )}
      {consent.note && vigente && <p style={{ margin: 0, fontSize: 12.5, color: "var(--txt-3)" }}>Nota: {consent.note}</p>}

      {abierto && (
        <form onSubmit={(e) => { e.preventDefault(); void guardar(true); }} style={{ display: "grid", gap: 8 }}>
          {api.eligeVia && (
            <label style={{ display: "grid", gap: 3, fontSize: 12.5 }}>
              <span style={{ color: "var(--txt-3)" }}>¿Cómo lo aceptó?</span>
              <select className="adm-input" style={{ minHeight: 48 }} value={via} onChange={(e) => setVia(e.target.value as SocialConsentUpdate["via"])}>
                {VIAS.map((v) => <option key={v.v} value={v.v}>{v.t}</option>)}
              </select>
            </label>
          )}
          <label style={{ display: "grid", gap: 3, fontSize: 12.5 }}>
            <span style={{ color: "var(--txt-3)" }}>Nota (opcional)</span>
            <textarea className="adm-input" rows={2} maxLength={300} value={nota} onChange={(e) => setNota(e.target.value)}
                      placeholder="Ej: me escribió el 02/11 desde su WhatsApp" />
          </label>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="submit" className="btn btn-primary btn-sm" style={BTN_GRANDE} disabled={guardando}>
              <Ic n="si" s={15} /> {guardando ? "Guardando…" : api.eligeVia ? "Registrar autorización" : "Registrar que aceptó"}
            </button>
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => { setAbierto(false); setErr(""); }} disabled={guardando}>Cancelar</button>
          </div>
        </form>
      )}

      {!abierto && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {!vigente && (
            <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} onClick={() => { setAbierto(true); setErr(""); }}>
              <Ic n="si" s={15} /> {api.eligeVia ? "Registrar autorización" : "Registrar que aceptó"}
            </button>
          )}
          {vigente && api.eligeVia && (
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={retirar} disabled={guardando}>
              <Ic n="cerrar" s={15} /> Retirar autorización
            </button>
          )}
          {api.historial && (
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={verHistorial} disabled={cargandoHist}>
              <Ic n="reloj" s={15} /> {historial ? "Ocultar historial" : "Ver historial"}
            </button>
          )}
        </div>
      )}

      {cargandoHist && <Cargando texto="Cargando el historial…" />}
      {historial && (
        historial.length === 0
          ? <p style={{ margin: 0, fontSize: 12.5, color: "var(--txt-3)" }}>Todavía no hay movimientos.</p>
          : (
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, color: "var(--txt-2)", display: "grid", gap: 3 }}>
              {historial.map((h, i) => (
                <li key={i}>
                  {fechaBo(h.recorded_at)} · {h.granted ? "Autorizó" : "Retiró"}
                  {h.via ? ` (${CONSENT_VIA_LABEL[h.via] ?? h.via})` : ""}{h.recorded_by ? ` · ${h.recorded_by}` : ""}{h.note ? ` · ${h.note}` : ""}
                </li>
              ))}
            </ul>
          )
      )}

      {retiro && (
        <Aviso tono="aviso">
          Autorización retirada. {retiro.pieces_skipped === 0 ? "No había piezas para saltar." : `Se saltaron ${retiro.pieces_skipped} piezas.`}
          {retiro.published_posts.length > 0 && (
            <>
              {" "}Lo que ya salió en las redes hay que borrarlo a mano:
              <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                {retiro.published_posts.map((p, i) => (
                  <li key={i}>
                    {redLabel(p.network)}{" "}
                    {p.post_url && /^https:\/\//.test(p.post_url)
                      ? <a href={p.post_url} target="_blank" rel="noopener noreferrer">abrir el posteo</a>
                      : "(sin link)"}
                  </li>
                ))}
              </ul>
            </>
          )}
        </Aviso>
      )}
      {err && <Aviso tono="error">{err}</Aviso>}
    </div>
  );
}
