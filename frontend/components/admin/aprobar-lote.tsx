"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { aprobarLoteImportados } from "@/lib/api";
import { LOTE_CERRADO, reducirLote, textoResultado, textoSimulacion, type EstadoLote } from "@/lib/aprobar-lote-pure";
import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE } from "@/components/content/content-ui";

/**
 * «Aprobar en bloque» de Importados (docs/home-ciudades.md §14). El flujo es siempre el mismo:
 *   1. «Aprobar en bloque» pide una SIMULACIÓN al servidor (cuenta, no escribe nada);
 *   2. se muestran los números («Se aprueban 12; se saltean 3 repetidos…») y se pide confirmar EN LA MISMA PANTALLA
 *      (nada de `window.confirm`);
 *   3. recién con «Sí, aprobar» se aprueba de verdad, por el mismo camino que «Al mapa», una fila por vez en el servidor.
 * Nada se publica sin esa confirmación. El padre lo monta con `key` = ciudad + fuente + estado: si la persona cambia
 * cualquiera de las tres, el flujo arranca de cero y una respuesta vieja no llega a la pantalla nueva.
 */
export function AprobarLote({ fuente, nombreFuente, ciudadId, ciudadNombre, onAprobado }: {
  /** El valor del query param `fuente` (`turismo`, `osm`…). */
  fuente: string;
  nombreFuente: string;
  ciudadId: string | null;
  ciudadNombre: string | null;
  /** Después de aprobar de verdad: el panel vuelve a pedir la lista. */
  onAprobado: () => void;
}) {
  const [estado, despachar] = useReducer(reducirLote, LOTE_CERRADO as EstadoLote);
  // Si la pantalla se cierra con un pedido en vuelo, su respuesta no hace nada.
  const vivo = useRef(true);
  // Un doble toque en «Sí, aprobar» no manda dos pedidos.
  const aprobandoYa = useRef(false);
  useEffect(() => { vivo.current = true; return () => { vivo.current = false; }; }, []);

  const simular = useCallback(async () => {
    if (!ciudadId) return;
    despachar({ tipo: "abrir" });
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      despachar({ tipo: "fallo", mensaje: "Sin conexión. Cuando vuelva internet, probá de nuevo: no se cambió nada." });
      return;
    }
    try {
      const r = await aprobarLoteImportados({ fuente, ciudad_id: ciudadId, solo_con_punto: true, simular: true });
      if (vivo.current) despachar({ tipo: "simulado", resultado: r });
    } catch (e) {
      if (vivo.current) despachar({ tipo: "fallo", mensaje: `No se pudo simular: ${e instanceof Error ? e.message : "error desconocido"}. No se cambió nada.` });
    }
  }, [fuente, ciudadId]);

  const aprobar = useCallback(async () => {
    if (!ciudadId || aprobandoYa.current) return;
    aprobandoYa.current = true;
    despachar({ tipo: "confirmar" });
    try {
      const r = await aprobarLoteImportados({ fuente, ciudad_id: ciudadId, solo_con_punto: true, simular: false });
      aprobandoYa.current = false;
      despachar({ tipo: "aprobado", resultado: r });
      onAprobado();
    } catch (e) {
      aprobandoYa.current = false;
      if (vivo.current) despachar({ tipo: "fallo", mensaje: `No se pudo aprobar: ${e instanceof Error ? e.message : "error desconocido"}. Revisá la lista antes de repetir: puede que algunos ya hayan pasado.` });
    }
  }, [fuente, ciudadId, onAprobado]);

  // Sin ciudad no hay a quién aprobar: el servidor lo pide (`ciudad_id`) y un lote de todo el país no es revisable.
  if (!ciudadId) {
    return <Aviso tono="info">Para aprobar en bloque, elegí una ciudad en el selector de arriba: se aprueba de a una ciudad.</Aviso>;
  }

  if (estado.tipo === "cerrado") {
    return (
      <button type="button" className="btn btn-sm btn-ghost" style={BTN_GRANDE} onClick={simular}>
        <Ic n="listo" s={16} /> Aprobar en bloque
      </button>
    );
  }

  return (
    <div style={{ display: "grid", gap: 10, padding: 12, border: "1px solid var(--border)", borderRadius: 12 }} aria-live="polite">
      <b style={{ fontSize: 14 }}>Aprobar en bloque · {nombreFuente}{ciudadNombre ? ` · ${ciudadNombre}` : ""}</b>

      {estado.tipo === "simulando" && <p style={{ margin: 0, fontSize: 13.5, color: "var(--txt-3)" }}>Simulando… todavía no se aprueba nada.</p>}

      {estado.tipo === "confirmar" && (
        <>
          <Aviso tono={estado.simulado.aprobados > 0 ? "aviso" : "info"}>
            <b>{textoSimulacion(estado.simulado)}</b>{" "}
            {estado.simulado.aprobados > 0
              ? "Es una simulación: todavía no se aprobó nada. Al confirmar, esos comercios pasan al mapa."
              : "Revisá las filas salteadas de a una, o probá con otra fuente."}
          </Aviso>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {estado.simulado.aprobados > 0 && (
              <button type="button" className="btn btn-primary" style={BTN_GRANDE} onClick={aprobar}>
                <Ic n="listo" s={16} /> Sí, aprobar {estado.simulado.aprobados}
              </button>
            )}
            <button type="button" className="btn btn-ghost" style={BTN_GRANDE} onClick={() => despachar({ tipo: "cancelar" })}>
              {estado.simulado.aprobados > 0 ? "No, cancelar" : "Cerrar"}
            </button>
          </div>
        </>
      )}

      {estado.tipo === "aprobando" && <p style={{ margin: 0, fontSize: 13.5, color: "var(--txt-3)" }}>Aprobando {estado.simulado.aprobados}… puede tardar un rato. No cierres esta pantalla.</p>}

      {estado.tipo === "hecho" && (
        <>
          <Aviso tono="ok">{textoResultado(estado.resultado)}</Aviso>
          <div><button type="button" className="btn btn-ghost" style={BTN_GRANDE} onClick={() => despachar({ tipo: "cancelar" })}>Cerrar</button></div>
        </>
      )}

      {estado.tipo === "error" && (
        <>
          <Aviso tono="error">{estado.mensaje}</Aviso>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="btn btn-primary" style={BTN_GRANDE} onClick={simular}>Reintentar (simula de nuevo)</button>
            <button type="button" className="btn btn-ghost" style={BTN_GRANDE} onClick={() => despachar({ tipo: "cancelar" })}>Cerrar</button>
          </div>
        </>
      )}
    </div>
  );
}
