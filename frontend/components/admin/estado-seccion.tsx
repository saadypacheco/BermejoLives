"use client";

// Los cuatro estados que tiene que tener toda sección del panel (cargando,
// vacío, error, sin conexión) — acá los tres que son de la CARGA. «Vacío» lo
// dice cada panel con su lista; «sin conexión» lo avisa el marco (admin-shell).
//
// `useCarga` + `<Carga>` son lo que permite que cada sección pida SUS datos
// cuando se abre (docs/admin-rediseno.md §4) sin que cada una reinvente el
// «cargando…» y el «no se pudo».

import { useCallback, useRef, useState } from "react";
import "@/app/styles/admin-shell.css";
import { Ic } from "@/components/ic";

export type EstadoCarga = {
  cargando: boolean;
  /** El mensaje del último intento si falló; null si anduvo o no se intentó. */
  error: string | null;
  /** Ya llegó bien al menos una vez: de acá en más hay algo que mostrar, aunque
   *  un refresco posterior falle o esté en camino. */
  listo: boolean;
};

/** Un error de red o del servidor, en palabras. `fetch` sin red tira «Failed to
 *  fetch» (o «Load failed» en Safari): eso no le dice nada a quien opera. */
//  Siempre «qué falló: por qué», en una sola frase y sin punto final (lo pone
//  quien la muestra): así nadie le antepone otro «No se pudo cargar…» y se lee
//  doble, ni queda un motivo suelto sin decir qué era lo que se cargaba.
export function mensajeDeError(e: unknown, queFallo = "No se pudo cargar"): string {
  const m = (e instanceof Error ? e.message : "").trim().replace(/\.$/, "");
  if (!m || m === "Failed to fetch" || m === "Load failed" || m === "NetworkError when attempting to fetch resource") {
    return `${queFallo}: no hay conexión con el servidor`;
  }
  return m.toLowerCase().startsWith(queFallo.toLowerCase()) ? m : `${queFallo}: ${m}`;
}

/** El estado de UNA carga y la función que la corre. `correr` es estable (se
 *  puede poner en las dependencias de un efecto sin que se dispare de más). Si
 *  se pide dos veces seguidas, sólo el último resultado cuenta para el estado. */
export function useCarga(queFallo?: string): [EstadoCarga, (fn: () => Promise<void>) => Promise<void>] {
  const [estado, setEstado] = useState<EstadoCarga>({ cargando: false, error: null, listo: false });
  const vez = useRef(0);
  const correr = useCallback(async (fn: () => Promise<void>) => {
    const n = ++vez.current;
    setEstado((e) => ({ ...e, cargando: true, error: null }));
    try {
      await fn();
      if (n === vez.current) setEstado({ cargando: false, error: null, listo: true });
    } catch (e) {
      if (n === vez.current) setEstado((p) => ({ ...p, cargando: false, error: mensajeDeError(e, queFallo) }));
    }
  }, [queFallo]);
  return [estado, correr];
}

export function CargandoSeccion({ texto = "Cargando…" }: { texto?: string }) {
  return (
    <div className="panel-card glass ash-estado" role="status" aria-live="polite">
      <span className="ash-spin" aria-hidden />
      <span>{texto}</span>
    </div>
  );
}

export function ErrorSeccion({ mensaje, onReintentar }: { mensaje: string; onReintentar: () => void }) {
  return (
    <div className="panel-card glass ash-estado ash-estado-error" role="alert">
      <span className="ash-estado-txt"><Ic n="aviso" s={20} /> {mensaje}</span>
      <button type="button" className="btn btn-ghost btn-sm ash-btn-grande" onClick={onReintentar}>Reintentar</button>
    </div>
  );
}

/** Envuelve el contenido de una sección que carga datos al abrirse.
 *   - Primera vez, en camino  → «Cargando…».
 *   - Primera vez, falló      → el error con «Reintentar» (y nada más: pintar la
 *     lista vacía debajo del error se leería como «no hay nada»).
 *   - Ya hubo datos           → el contenido siempre; si un refresco falla, un
 *     aviso arriba; si está en camino, una línea «Actualizando…». */
export function Carga({ estado, onReintentar, que, children }: {
  estado: EstadoCarga;
  onReintentar: () => void;
  /** Qué se está cargando, para el texto: «las suscripciones». */
  que: string;
  children: React.ReactNode;
}) {
  if (!estado.listo) {
    if (estado.error) return <ErrorSeccion mensaje={`${estado.error}.`} onReintentar={onReintentar} />;
    return <CargandoSeccion texto={`Cargando ${que}…`} />;
  }
  return (
    <>
      {estado.error && (
        <div className="ash-aviso ash-aviso-error" role="alert">
          <span className="ash-estado-txt"><Ic n="aviso" s={18} /> {estado.error}. Lo que ves puede estar desactualizado.</span>
          <button type="button" className="btn btn-ghost btn-sm ash-btn-grande" onClick={onReintentar}>Reintentar</button>
        </div>
      )}
      {estado.cargando && !estado.error && (
        <div className="ash-actualizando" role="status" aria-live="polite">
          <span className="ash-spin ash-spin-chico" aria-hidden /> Actualizando {que}…
        </div>
      )}
      {children}
    </>
  );
}

/** La fila de arriba de una lista grande que se baja UNA vez: cuántos hay y el
 *  botón para volver a bajarla. Sin él, una lista cacheada no tiene forma de
 *  ponerse al día sin recargar toda la página. */
export function BarraDatos({ texto, cargando, onActualizar, aviso }: {
  texto: string;
  cargando: boolean;
  onActualizar: () => void;
  /** Una advertencia de la lista (p.ej. que llegó a su tope). */
  aviso?: string | null;
}) {
  return (
    <div className="ash-datos">
      <span className="ash-datos-txt">{texto}</span>
      <button type="button" className="btn btn-ghost btn-sm ash-btn-grande" onClick={onActualizar} disabled={cargando}>
        <Ic n="actualizar" s={15} /> {cargando ? "Actualizando…" : "Actualizar"}
      </button>
      {aviso && (
        <p role="alert" className="ash-datos-aviso"><Ic n="aviso" s={14} /> {aviso}</p>
      )}
    </div>
  );
}
