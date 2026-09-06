"use client";

import { useCallback, useEffect, useState } from "react";
import { getBandejaWa, type BandejaWa } from "@/lib/api";

const ETIQUETA: Record<string, { texto: string; color: string }> = {
  publicada: { texto: "Publicada", color: "var(--neon)" },
  ignorada: { texto: "Ignorada", color: "var(--txt-3)" },
  sin_comercio: { texto: "No se supo de quién es", color: "var(--amber)" },
  sin_permiso: { texto: "El plan no alcanza", color: "var(--amber)" },
  error: { texto: "Error", color: "var(--pink)" },
  sin_registrar: { texto: "Sin registrar", color: "var(--txt-3)" },
};

/**
 * Qué entró por WhatsApp y qué pasó con cada mensaje.
 *
 * POR QUÉ ESTA PANTALLA
 * =====================
 * La ingesta está construida y era ciega. Cuando algo no se publica —el grupo
 * no está atado, el mensaje vino sin el código, el plan no alcanza— el crudo se
 * guarda y el motivo se va en una línea de log. Con el canal apagado alcanzaba.
 *
 * Encendido, la primera pregunta de cada día es "le dije al de la ferretería
 * que mande la foto, ¿llegó?". Contestarla por SSH significa que no la contesta
 * nadie: se le pide al comerciante que mande de nuevo, y la segunda vez tampoco
 * se publica por la misma razón que la primera. Ahí es donde se pierde un
 * comerciante que ya había aceptado.
 *
 * El filtro arranca en "hay que mirarlos": es lo único que pide acción.
 */
export function BandejaWhatsApp() {
  const [estado, setEstado] = useState("problemas");
  const [d, setD] = useState<BandejaWa | null>(null);
  const [err, setErr] = useState("");
  const [cargando, setCargando] = useState(true);

  const cargar = useCallback(async () => {
    setCargando(true);
    try { setD(await getBandejaWa(estado, 150)); setErr(""); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo cargar"); }
    finally { setCargando(false); }
  }, [estado]);

  useEffect(() => { cargar(); }, [cargar]);

  const total = (d?.resumen ?? []).reduce((a, b) => a + b.n, 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {err && <div className="panel-card glass" style={{ padding: 14, color: "var(--pink)", fontSize: 13 }}>{err}</div>}

      {/* El estado del canal. Sin esto, "no llega nada" y "llega y se descarta"
          se ven igual desde acá — y son problemas opuestos: uno se arregla en
          el teléfono y el otro en el panel. */}
      <div className="panel-card glass">
        <div className="ph">
          <h3>Canal de WhatsApp</h3>
          <span style={{ color: "var(--txt-3)", fontSize: 12.5 }}>últimos 7 días</span>
        </div>
        <div style={{ padding: "12px 16px", display: "flex", gap: 18, flexWrap: "wrap", fontSize: 13 }}>
          <span><b style={{ fontSize: 18 }}>{total}</b> mensajes</span>
          {(d?.resumen ?? []).map((r) => (
            <span key={r.resultado} style={{ color: ETIQUETA[r.resultado]?.color ?? "var(--txt-2)" }}>
              {ETIQUETA[r.resultado]?.texto ?? r.resultado}: <b>{r.n}</b>
            </span>
          ))}
        </div>
        <div style={{ padding: "0 16px 14px", fontSize: 12, color: "var(--txt-3)" }}>
          {/* Cuántos, no cuáles: el panel lo usa un administrador, pero un
              teléfono en pantalla se saca en una foto. */}
          Números propios configurados: <b>{d?.config.propios ?? 0}</b> ·
          {" "}explorador: <b>{d?.config.explorador ?? 0}</b> ·
          {" "}contacto del explorador: <b>{d?.config.contacto_explorador ? "sí" : "no"}</b>
          {d && d.config.propios === 0 && (
            <div style={{ color: "var(--amber)", marginTop: 6 }}>
              ⚠️ Sin números propios cargados, cualquier mensaje que escriba alguien de URUKU
              dentro de un grupo se publica como oferta del comerciante. Va en
              <code> WA_NUMEROS_PROPIOS</code> del <code>backend/.env</code>, y sin
              placeholders: <code>591XXXXXXXX</code> se normaliza a <code>591</code> y apaga
              la guarda sin avisar.
            </div>
          )}
        </div>

        <div style={{ display: "flex", gap: 8, padding: "0 16px 14px", flexWrap: "wrap" }}>
          {[
            { k: "problemas", t: "Hay que mirarlos" },
            { k: "publicada", t: "Publicadas" },
            { k: "ignorada", t: "Ignoradas" },
            { k: "", t: "Todo" },
          ].map((f) => (
            <button key={f.k} className={`btn btn-sm ${estado === f.k ? "btn-primary" : "btn-ghost"}`}
                    onClick={() => setEstado(f.k)}>
              {f.t}
            </button>
          ))}
          <button className="btn btn-ghost btn-sm" onClick={cargar} disabled={cargando}>
            {cargando ? "…" : "↻ Actualizar"}
          </button>
        </div>
      </div>

      {!cargando && (d?.items.length ?? 0) === 0 && (
        <div className="panel-card glass" style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>
          {estado === "problemas"
            ? "Nada pendiente de mirar. 🎉"
            : "No hay mensajes con ese filtro."}
        </div>
      )}

      {(d?.items ?? []).map((m) => {
        const et = ETIQUETA[m.resultado ?? "sin_registrar"] ?? ETIQUETA.sin_registrar;
        return (
          <div key={m.id} className="panel-card glass" style={{ padding: 12 }}>
            <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
              {m.media_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={m.media_url} alt="" width={72} height={72}
                     style={{ borderRadius: 8, objectFit: "cover", flexShrink: 0 }} />
              )}
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
                  <b style={{ color: et.color }}>{et.texto}</b>
                  <span style={{ color: "var(--txt-3)", fontSize: 12 }}>
                    {new Date(m.created_at).toLocaleString("es-BO", {
                      day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
                    })}
                  </span>
                  {m.comercios?.nombre && (
                    <span style={{ fontSize: 12.5 }}>
                      · {m.comercios.nombre}
                      {m.comercios.codigo && (
                        <span style={{ color: "var(--neon)", fontFamily: "monospace" }}>
                          {" "}URUKU-{m.comercios.codigo}
                        </span>
                      )}
                    </span>
                  )}
                </div>

                {m.motivo && (
                  <div style={{ fontSize: 12.5, color: "var(--txt-2)", marginTop: 3 }}>{m.motivo}</div>
                )}

                {/* De dónde vino. El grupo importa más que el número: un grupo
                    sin atar es el caso que más se repite y se arregla desde la
                    ficha del comercio, en "Grupo de WhatsApp". */}
                <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginTop: 4, fontFamily: "monospace" }}>
                  {m.wa_jid?.endsWith("@g.us") ? `grupo ${m.wa_jid}` : `de ${m.phone ?? m.wa_jid}`}
                  {m.tipo ? ` · ${m.tipo}` : ""}
                </div>

                {m.body && (
                  <div style={{ fontSize: 12.5, color: "var(--txt-2)", marginTop: 5,
                                maxHeight: 60, overflow: "hidden" }}>
                    {m.body}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
