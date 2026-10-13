"use client";

/**
 * Lo que el agente hace PARADO frente al dueño para ofrecerle URUKU
 * (spec docs/que-hay-aca.md):
 *
 *  1. «Mostrale cómo se ven otros»: 2 o 3 comercios completos de la ciudad.
 *  2. «Le interesa un plan»: elige el plan (sólo nombres) y deja una nota; queda
 *     anotado para el admin en Suscripciones.
 *  3. «Mandarle su ficha por WhatsApp»: abre el chat desde el celular del agente
 *     con el mensaje armado (sin precios).
 *
 * Se usa en la ficha del local («Qué hay acá») y en la pantalla de «listo» que
 * sigue a un alta nueva. NO muestra precios en ningún lado.
 */
import { useEffect, useState } from "react";
import {
  ejemplosCampo, planesCampo, anotarInteresPlan,
  type EjemploCampo, type PlanCampo,
} from "@/lib/campo";
import { linkWhatsapp, mensajeFicha, soloDigitos } from "@/lib/ficha-whatsapp";
import { Ic, type NombreIcono } from "@/components/ic";

export type ComercioOfrecible = {
  id: string; nombre: string; slug: string;
  /** El WhatsApp guardado del comercio (con prefijo de país). Null = no tiene. */
  whatsapp: string | null;
  /** Para preferir ejemplos del mismo rubro. */
  rubroSlug?: string | null;
};

const PREFIJOS = [
  { p: "591", label: "+591 Bolivia" },
  { p: "549", label: "+549 Argentina" },
];

/** Un error de red se dice como lo que es; el resto, con su mensaje. */
function textoError(e: unknown, algo: string): string {
  const sinRed = (typeof navigator !== "undefined" && !navigator.onLine) || e instanceof TypeError;
  if (sinRed) return `Sin conexión: ${algo}. Probá de nuevo cuando haya señal.`;
  return e instanceof Error && e.message ? e.message : `No se pudo: ${algo}.`;
}

function Caja({ icono, titulo, children }: { icono: NombreIcono; titulo: string; children: React.ReactNode }) {
  return (
    <section style={{ padding: 12, borderRadius: 12, background: "var(--panel)", border: "1px solid var(--stroke)", textAlign: "left", minWidth: 0 }}>
      <h2 style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 14, fontWeight: 700, margin: "0 0 10px" }}>
        <Ic n={icono} s={16} /> {titulo}
      </h2>
      {children}
    </section>
  );
}

// ─────────────────────────────────────────────
/** «Mostrale cómo se ven otros». */
export function EjemplosCompletos({ comercioId, rubroSlug }: { comercioId: string; rubroSlug?: string | null }) {
  const [items, setItems] = useState<EjemploCampo[] | null>(null);
  const [err, setErr] = useState("");
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    let vivo = true;
    setItems(null); setErr("");
    ejemplosCampo(rubroSlug, comercioId)
      .then((xs) => { if (vivo) setItems(xs); })
      .catch((e) => { if (vivo) setErr(textoError(e, "no se pudieron traer los ejemplos")); });
    return () => { vivo = false; };
  }, [comercioId, rubroSlug, intento]);

  return (
    <Caja icono="comercios" titulo="Mostrale cómo se ven otros">
      <p style={{ color: "var(--txt-3)", fontSize: 12.5, margin: "0 0 10px", lineHeight: 1.4 }}>
        Locales de la ciudad bien cargados: con foto, horario y todo. Tocá uno para abrir su ficha.
      </p>
      {items === null && !err && <p style={{ color: "var(--txt-3)", fontSize: 13, margin: 0 }}><Ic n="reloj" s={13} /> Buscando ejemplos…</p>}
      {err && (
        <div role="alert" style={{ color: "var(--pink)", fontSize: 13 }}>
          <Ic n="aviso" s={13} /> {err}{" "}
          <button type="button" className="link-more" style={{ minHeight: 44 }} onClick={() => setIntento((n) => n + 1)}>Reintentar</button>
        </div>
      )}
      {items && items.length === 0 && (
        <p style={{ color: "var(--txt-3)", fontSize: 13, margin: 0 }}>Todavía no hay locales completos de la ciudad para mostrar.</p>
      )}
      {items && items.length > 0 && (
        <div style={{ display: "flex", gap: 10, overflowX: "auto", paddingBottom: 4, scrollSnapType: "x proximity" }}>
          {items.map((e) => (
            // Otra pestaña: el agente no puede perder lo que tiene en pantalla.
            <a key={e.id} href={`/comercios/${encodeURIComponent(e.slug)}`} target="_blank" rel="noopener noreferrer"
               style={{ flex: "0 0 150px", scrollSnapAlign: "start", display: "flex", flexDirection: "column", textDecoration: "none", color: "inherit",
                        border: "1px solid var(--stroke)", borderRadius: 12, overflow: "hidden", background: "var(--panel-2, transparent)" }}>
              <div style={{ height: 96, flexShrink: 0, overflow: "hidden", background: "#0b1411", display: "grid", placeItems: "center", color: "var(--txt-3)" }}>
                {e.portada_thumb_url
                  // eslint-disable-next-line @next/next/no-img-element
                  ? <img src={e.portada_thumb_url} alt="" loading="lazy" onError={(ev) => { ev.currentTarget.style.display = "none"; }} style={{ width: "100%", height: 96, objectFit: "cover", display: "block" }} />
                  : <Ic n="comercios" s={28} />}
              </div>
              <div style={{ padding: "8px 10px", minHeight: 64 }}>
                <div style={{ fontWeight: 700, fontSize: 13.5, lineHeight: 1.25, overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>{e.nombre}</div>
                <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginTop: 2 }}>{e.rubro_nombre ?? "Sin rubro"}</div>
                <div style={{ fontSize: 11.5, color: "var(--neon)", fontWeight: 700, marginTop: 4 }}><Ic n="abrir" s={12} /> Ver ficha</div>
              </div>
            </a>
          ))}
        </div>
      )}
    </Caja>
  );
}

// ─────────────────────────────────────────────
/** «Le interesa un plan»: queda anotado para el admin. Sólo nombres, sin precios. */
export function InteresPlan({ comercioId }: { comercioId: string }) {
  const [planes, setPlanes] = useState<PlanCampo[] | null>(null);
  const [errPlanes, setErrPlanes] = useState("");
  const [intento, setIntento] = useState(0);
  const [elegido, setElegido] = useState("");
  const [nota, setNota] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [err, setErr] = useState("");
  const [anotado, setAnotado] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    setPlanes(null); setErrPlanes("");
    planesCampo()
      .then((ps) => { if (vivo) setPlanes(ps); })
      .catch((e) => { if (vivo) setErrPlanes(textoError(e, "no se pudieron traer los planes")); });
    return () => { vivo = false; };
  }, [intento]);

  async function anotar() {
    if (!elegido || enviando) return;
    setEnviando(true); setErr("");
    try {
      await anotarInteresPlan(comercioId, elegido, nota);
      setAnotado(planes?.find((p) => p.slug === elegido)?.nombre ?? elegido);
      setNota("");
    } catch (e) {
      setErr(textoError(e, "no se anotó el interés"));   // lo elegido y la nota quedan
    } finally { setEnviando(false); }
  }

  return (
    <Caja icono="destacado" titulo="Le interesa un plan">
      {planes === null && !errPlanes && <p style={{ color: "var(--txt-3)", fontSize: 13, margin: 0 }}><Ic n="reloj" s={13} /> Trayendo los planes…</p>}
      {errPlanes && (
        <div role="alert" style={{ color: "var(--pink)", fontSize: 13 }}>
          <Ic n="aviso" s={13} /> {errPlanes}{" "}
          <button type="button" className="link-more" style={{ minHeight: 44 }} onClick={() => setIntento((n) => n + 1)}>Reintentar</button>
        </div>
      )}
      {planes && planes.length === 0 && <p style={{ color: "var(--txt-3)", fontSize: 13, margin: 0 }}>No hay planes pagos para ofrecer por ahora.</p>}
      {planes && planes.length > 0 && (
        <div style={{ display: "grid", gap: 10 }}>
          <p style={{ color: "var(--txt-3)", fontSize: 12.5, margin: 0, lineHeight: 1.4 }}>
            Si el dueño quiere un plan, elegilo y queda anotado para que lo llamemos.
          </p>
          <div role="radiogroup" aria-label="Plan que le interesa" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {planes.map((p) => {
              const on = elegido === p.slug;
              return (
                <button key={p.slug} type="button" role="radio" aria-checked={on}
                        onClick={() => { setElegido(p.slug); setAnotado(null); setErr(""); }}
                        style={{ minHeight: 44, padding: "8px 16px", borderRadius: 999, cursor: "pointer", fontSize: 14, fontWeight: on ? 700 : 500,
                                 border: `1px solid ${on ? "var(--neon)" : "var(--stroke)"}`,
                                 background: on ? "rgba(57,255,158,.12)" : "transparent", color: on ? "var(--neon)" : "var(--txt-2)",
                                 display: "inline-flex", alignItems: "center", gap: 6 }}>
                  {on && <Ic n="si" s={14} />}{p.nombre}
                </button>
              );
            })}
          </div>
          <div>
            <label className="campo-lbl" htmlFor="interes-nota">Nota (opcional)</label>
            <textarea id="interes-nota" className="adm-input" rows={2} maxLength={300} value={nota}
                      onChange={(e) => { setNota(e.target.value); setAnotado(null); }}
                      placeholder="Ej.: quiere que lo llamen a la tarde" style={{ resize: "vertical", width: "100%" }} />
            <div style={{ fontSize: 11, color: "var(--txt-3)", textAlign: "right" }}>{nota.length}/300</div>
          </div>
          {err && <div role="alert" style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={13} /> {err}</div>}
          {anotado && (
            <div role="status" style={{ color: "var(--neon)", fontSize: 13.5, fontWeight: 700 }}>
              <Ic n="listo" s={16} /> Anotado: le interesa {anotado}. El admin lo ve en Suscripciones.
            </div>
          )}
          <button type="button" className="btn btn-ghost" style={{ minHeight: 48 }} disabled={!elegido || enviando} onClick={anotar}>
            {enviando ? "Anotando…" : elegido ? "Anotar interés" : "Elegí un plan"}
          </button>
        </div>
      )}
    </Caja>
  );
}

// ─────────────────────────────────────────────
/** «Mandarle su ficha por WhatsApp»: sale del celular del agente. */
export function FichaPorWhatsapp({ comercio }: { comercio: ComercioOfrecible }) {
  const [pref, setPref] = useState("591");
  const [cel, setCel] = useState("");
  const [err, setErr] = useState("");
  const texto = mensajeFicha(comercio.nombre, comercio.slug);
  const numero = soloDigitos(comercio.whatsapp);
  const tiene = numero.length >= 7;

  function abrirConNumero() {
    const d = soloDigitos(cel);
    // Con menos de 7 dígitos es un número a medio dictar.
    if (d.length < 7) { setErr("El número está incompleto."); return; }
    setErr("");
    window.open(linkWhatsapp(pref + d, texto), "_blank", "noopener,noreferrer");
  }

  return (
    <Caja icono="whatsapp" titulo="Mandarle su ficha por WhatsApp">
      <p style={{ color: "var(--txt-3)", fontSize: 12.5, margin: "0 0 10px", lineHeight: 1.4 }}>
        Se abre tu WhatsApp con el mensaje ya escrito: el link de su ficha y qué gana completándola.
      </p>
      {tiene ? (
        <a className="btn btn-wa" style={{ minHeight: 48, display: "flex", justifyContent: "center", alignItems: "center", gap: 8 }}
           href={linkWhatsapp(numero, texto)} target="_blank" rel="noopener noreferrer">
          <Ic n="whatsapp" s={18} /> Mandarle su ficha a +{numero}
        </a>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          <label className="campo-lbl" htmlFor="ficha-wa">Todavía no tiene WhatsApp cargado: pedile el número</label>
          <div style={{ display: "flex", gap: 8 }}>
            <select className="adm-input" style={{ width: "auto", flexShrink: 0 }} value={pref} onChange={(e) => setPref(e.target.value)} aria-label="País del número">
              {PREFIJOS.map((x) => <option key={x.p} value={x.p}>{x.label}</option>)}
            </select>
            <input id="ficha-wa" className="adm-input" type="tel" inputMode="numeric" autoComplete="off" value={cel}
                   onChange={(e) => { setCel(e.target.value); setErr(""); }} placeholder="Número de celular" />
          </div>
          {err && <div role="alert" style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={13} /> {err}</div>}
          <button type="button" className="btn btn-wa" style={{ minHeight: 48, display: "flex", justifyContent: "center", alignItems: "center", gap: 8 }} onClick={abrirConNumero}>
            <Ic n="whatsapp" s={18} /> Abrir WhatsApp con el mensaje
          </button>
          <p style={{ color: "var(--txt-3)", fontSize: 11.5, margin: 0 }}>
            El número se usa solo para mandar este mensaje: no se guarda en la ficha. Para cargarlo, usá «Completar».
          </p>
        </div>
      )}
      <details style={{ marginTop: 10 }}>
        <summary style={{ cursor: "pointer", fontSize: 12.5, color: "var(--txt-3)", minHeight: 36 }}>Ver el mensaje</summary>
        <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: 12.5, color: "var(--txt-2)", margin: "6px 0 0", lineHeight: 1.45 }}>{texto}</pre>
      </details>
    </Caja>
  );
}

// ─────────────────────────────────────────────
/** Las tres cosas juntas: lo que va debajo de la ficha y de la pantalla de «listo». */
export function OfrecerComercio({ comercio }: { comercio: ComercioOfrecible }) {
  return (
    // minmax(0, 1fr): sin esto la tira de ejemplos (que se desliza) ensancha toda la columna.
    <div style={{ display: "grid", gap: 12, gridTemplateColumns: "minmax(0, 1fr)" }}>
      <EjemplosCompletos comercioId={comercio.id} rubroSlug={comercio.rubroSlug} />
      <InteresPlan comercioId={comercio.id} />
      <FichaPorWhatsapp comercio={comercio} />
    </div>
  );
}
