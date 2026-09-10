"use client";

import { useCallback, useEffect, useState } from "react";
import { enviarDifusion, getDifusion, reintentarDifusion, type Difusion } from "@/lib/api";

const COLOR: Record<string, string> = {
  enviado: "var(--neon)",
  pendiente: "var(--txt-3)",
  error: "var(--pink)",
  omitido: "var(--txt-3)",
};

const TEXTO: Record<string, string> = {
  enviado: "Publicada",
  pendiente: "Esperando",
  error: "Falló",
  omitido: "No corresponde",
};

/**
 * La cola de difusión: qué oferta salió a qué red y qué pasó con cada una.
 *
 * POR QUÉ ESTA PANTALLA Y NO SÓLO EL AUTOMÁTICO
 * =============================================
 * Publicar en una red ajena falla por razones que no son nuestras: el token
 * venció, Meta está caído, la imagen tardó. Si eso pasa sin pantalla, la oferta
 * simplemente no aparece y nadie se entera hasta que el comerciante pregunta
 * por qué no la vio — que es tarde, porque ya se le prometió.
 *
 * Acá se ve el estado de cada envío, el motivo del que falló y el botón para
 * reintentar. También qué destinos están configurados: sin eso, "no se publica
 * nada en Facebook" y "se publica y falla" se ven igual, y uno se arregla
 * pegando un token mientras el otro se arregla mirando el error.
 */
export function DifusionPanel() {
  const [estado, setEstado] = useState("");
  const [d, setD] = useState<Difusion | null>(null);
  const [err, setErr] = useState("");
  const [cargando, setCargando] = useState(true);
  const [ocupado, setOcupado] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try { setD(await getDifusion(estado, 150)); setErr(""); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo cargar"); }
    finally { setCargando(false); }
  }, [estado]);

  useEffect(() => { cargar(); }, [cargar]);

  const accion = async (fn: () => Promise<unknown>) => {
    setOcupado(true); setErr("");
    try { await fn(); await cargar(); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo"); }
    finally { setOcupado(false); }
  };

  const pendientes = (d?.resumen ?? [])
    .filter((r) => r.estado === "pendiente").reduce((a, b) => a + b.n, 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {err && <div className="panel-card glass" style={{ padding: 14, color: "var(--pink)", fontSize: 13 }}>{err}</div>}

      <div className="panel-card glass">
        <div className="ph">
          <h3>Difusión a las redes</h3>
          <span style={{ color: "var(--txt-3)", fontSize: 12.5 }}>
            {pendientes > 0 ? `${pendientes} esperando` : "nada esperando"}
          </span>
        </div>

        {/* Qué destino está prendido y cuál no. Un destino sin configurar no es
            un error: es que todavía no le pegaron el token. Pero tiene que
            verse, porque explica por qué la cola no baja. */}
        <div style={{ padding: "12px 16px", display: "flex", gap: 10, flexWrap: "wrap" }}>
          {(d?.destinos ?? []).map((x) => (
            <span key={x.clave} style={{
              fontSize: 12.5, padding: "5px 10px", borderRadius: 8,
              border: "1px solid var(--line)",
              color: x.configurado ? "var(--txt-2)" : "var(--amber)",
            }}>
              {x.configurado ? "✓" : "○"} {x.nombre}
              {x.automatico && x.configurado && (
                <b style={{ color: "var(--neon)" }}> · sale solo</b>
              )}
              {!x.configurado && " · falta configurar"}
            </span>
          ))}
        </div>

        <div style={{ padding: "0 16px 14px", fontSize: 12, color: "var(--txt-3)" }}>
          El canal tiene tope diario: lo que no entra hoy espera y sale mañana. Cada
          publicación es una notificación en el teléfono de cada seguidor, y los
          seguidores son lo único que no se puede rehacer.
          <br />
          TikTok y YouTube no están: sus APIs piden video y una app auditada. Esas dos
          se siguen subiendo a mano.
        </div>

        <div style={{ display: "flex", gap: 8, padding: "0 16px 14px", flexWrap: "wrap" }}>
          {[
            { k: "", t: "Todo" },
            { k: "pendiente", t: "Esperando" },
            { k: "error", t: "Fallaron" },
            { k: "enviado", t: "Publicadas" },
          ].map((f) => (
            <button key={f.k} className={`btn btn-sm ${estado === f.k ? "btn-primary" : "btn-ghost"}`}
                    onClick={() => setEstado(f.k)}>
              {f.t}
            </button>
          ))}
          <button className="btn btn-sm btn-primary" disabled={ocupado || !pendientes}
                  onClick={() => accion(() => enviarDifusion(10))}>
            Publicar 10 que esperan
          </button>
          <button className="btn btn-ghost btn-sm" onClick={cargar} disabled={cargando}>
            {cargando ? "…" : "↻ Actualizar"}
          </button>
        </div>
      </div>

      {!cargando && (d?.items.length ?? 0) === 0 && (
        <div className="panel-card glass" style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>
          Todavía no salió ninguna oferta a las redes.
        </div>
      )}

      {(d?.items ?? []).map((f) => {
        const pub = f.publicaciones;
        const com = pub?.comercios;
        return (
          <div key={f.id} className="panel-card glass"
               style={{ padding: 14, display: "flex", gap: 12, alignItems: "flex-start" }}>
            {pub?.imagen_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={pub.imagen_url} alt="" style={{
                width: 66, height: 66, objectFit: "cover", borderRadius: 8, flexShrink: 0 }} />
            )}
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ display: "flex", gap: 10, alignItems: "baseline", flexWrap: "wrap" }}>
                <b style={{ fontSize: 13.5 }}>{com?.nombre ?? "(sin comercio)"}</b>
                <span style={{ fontSize: 12, color: "var(--txt-3)" }}>
                  {f.destino === "wa_canal" ? "Canal de WhatsApp"
                    : f.destino === "facebook" ? "Facebook" : "Instagram"}
                </span>
                <span style={{ fontSize: 12, color: COLOR[f.estado] }}>
                  {TEXTO[f.estado] ?? f.estado}
                  {f.intentos > 1 && ` · ${f.intentos} intentos`}
                </span>
              </div>
              <div style={{ fontSize: 12.5, color: "var(--txt-2)", marginTop: 3,
                            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {pub?.titulo || pub?.descripcion || "(sin texto)"}
              </div>
              {f.motivo && (
                <div style={{ fontSize: 12, color: f.estado === "error" ? "var(--pink)" : "var(--txt-3)", marginTop: 4 }}>
                  {f.motivo}
                </div>
              )}
              {f.url_publicada && (
                <a href={f.url_publicada} target="_blank" rel="noreferrer"
                   style={{ fontSize: 12, color: "var(--neon)" }}>ver el posteo →</a>
              )}
            </div>
            {f.estado !== "enviado" && (
              <button className="btn btn-sm btn-ghost" disabled={ocupado}
                      onClick={() => accion(() => reintentarDifusion(f.id))}>
                Publicar
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
