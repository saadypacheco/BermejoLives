"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { aprobarLoteImportados } from "@/lib/api";
import {
  AVISO_BUSQUEDA_NO_APLICA, LOTE_CERRADO, aprobarPorTandas, mensajeDeFalloLote, reducirLote,
  textoProgreso, textoResultado, textoSimulacion, type EstadoLote,
} from "@/lib/aprobar-lote-pure";
import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE } from "@/components/content/content-ui";

/** El `status` que `authFetch` cuelga del error (undefined = falló la red, no hubo respuesta). */
const statusDe = (e: unknown): number | undefined => (e as { status?: unknown } | null)?.status as number | undefined;
const textoDe = (e: unknown): string => (e instanceof Error ? e.message : "error desconocido");

/**
 * «Aprobar en bloque» de Importados (docs/home-ciudades.md §14). El flujo es siempre el mismo:
 *   1. «Aprobar en bloque» pide una SIMULACIÓN al servidor (cuenta, no escribe nada);
 *   2. se muestran los números («Se aprueban 412; se saltean 3 repetidos…») y se pide confirmar EN LA MISMA PANTALLA
 *      (nada de `window.confirm`), avisando que la búsqueda por nombre del panel no se aplica;
 *   3. con «Sí, aprobar N» se aprueba de verdad, por el mismo camino que «Al mapa», en tandas de hasta 200 que la pantalla
 *      repite («Aprobando… 200 de 412») sin pasar nunca de N.
 * Nada se publica sin esa confirmación. Si una tanda falla (otro lote en curso, red caída) se corta: se muestra lo que ya se
 * aprobó y la persona decide si simula de nuevo; NO se lanza otro lote por su cuenta. El padre lo monta con `key` = ciudad +
 * fuente + estado: si la persona cambia cualquiera de las tres, el flujo arranca de cero.
 */
export function AprobarLote({ fuente, nombreFuente, ciudadId, ciudadNombre, onAprobado }: {
  /** El valor del query param `fuente` (`turismo`, `anh`, `aduana`). */
  fuente: string;
  nombreFuente: string;
  ciudadId: string | null;
  ciudadNombre: string | null;
  /** Después de aprobar (aunque sea una parte): el panel vuelve a pedir la lista. */
  onAprobado: () => void;
}) {
  const [estado, despachar] = useReducer(reducirLote, LOTE_CERRADO as EstadoLote);
  // Si la pantalla se cierra con un pedido en vuelo, el ciclo de tandas se corta (no sigue aprobando para nadie).
  const vivo = useRef(true);
  // Un doble toque en «Sí, aprobar» no lanza dos ciclos.
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
      if (vivo.current) despachar({ tipo: "fallo", mensaje: mensajeDeFalloLote(statusDe(e), textoDe(e), false) });
    }
  }, [fuente, ciudadId]);

  const aprobar = useCallback(async (total: number) => {
    if (!ciudadId || aprobandoYa.current) return;
    aprobandoYa.current = true;
    despachar({ tipo: "confirmar" });
    const { resultado, error } = await aprobarPorTandas(
      (max) => aprobarLoteImportados({ fuente, ciudad_id: ciudadId, solo_con_punto: true, simular: false, max_aprobar: max }),
      total,
      { seguir: () => vivo.current, alProgreso: (acumulado) => despachar({ tipo: "progreso", acumulado }) },
    );
    aprobandoYa.current = false;
    // Aunque haya sido una parte: la lista del panel ya no es la misma.
    if (resultado.aprobados > 0) onAprobado();
    if (!vivo.current) return;
    if (error === null) {
      despachar({ tipo: "aprobado", resultado });
    } else {
      // Se corta ACÁ: nada de reintentar un lote nuevo a ciegas. Se muestra lo que ya se aprobó (en `parcial`).
      despachar({ tipo: "progreso", acumulado: resultado });
      despachar({ tipo: "fallo", mensaje: mensajeDeFalloLote(statusDe(error), textoDe(error), true) });
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
            {estado.simulado.aprobados > 0 && <><br />{AVISO_BUSQUEDA_NO_APLICA}</>}
          </Aviso>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {estado.simulado.aprobados > 0 && (
              <button type="button" className="btn btn-primary" style={BTN_GRANDE} onClick={() => void aprobar(estado.simulado.aprobados)}>
                <Ic n="listo" s={16} /> Sí, aprobar {estado.simulado.aprobados}
              </button>
            )}
            <button type="button" className="btn btn-ghost" style={BTN_GRANDE} onClick={() => despachar({ tipo: "cancelar" })}>
              {estado.simulado.aprobados > 0 ? "No, cancelar" : "Cerrar"}
            </button>
          </div>
        </>
      )}

      {estado.tipo === "aprobando" && (
        <p style={{ margin: 0, fontSize: 13.5, color: "var(--txt-3)" }} role="status">
          {textoProgreso(estado.hechos.aprobados, estado.simulado.aprobados)} Puede tardar un rato. No cierres esta pantalla.
        </p>
      )}

      {estado.tipo === "hecho" && (
        <>
          <Aviso tono="ok">{textoResultado(estado.resultado)}</Aviso>
          <div><button type="button" className="btn btn-ghost" style={BTN_GRANDE} onClick={() => despachar({ tipo: "cancelar" })}>Cerrar</button></div>
        </>
      )}

      {estado.tipo === "error" && (
        <>
          <Aviso tono="error">{estado.mensaje}</Aviso>
          {estado.parcial && estado.parcial.aprobados > 0 && (
            <Aviso tono="info">Antes del corte se aprobaron {estado.parcial.aprobados}. La lista ya se actualizó.</Aviso>
          )}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="btn btn-primary" style={BTN_GRANDE} onClick={simular}>Simular de nuevo</button>
            <button type="button" className="btn btn-ghost" style={BTN_GRANDE} onClick={() => despachar({ tipo: "cancelar" })}>Cerrar</button>
          </div>
        </>
      )}
    </div>
  );
}
