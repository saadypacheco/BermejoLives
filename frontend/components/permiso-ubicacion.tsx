"use client";

import { useEffect, useState } from "react";
import { aparato, pasosPermisoUbicacion } from "@/lib/geo";

/**
 * El cartel que sale cuando hace falta la ubicación y no está.
 *
 * Tiene dos caras, porque el navegador tiene dos estados:
 *
 *  · Todavía no preguntó (o no sabemos): un botón «Dar permiso». Al tocarlo
 *    se vuelve a pedir la posición y el navegador muestra SU cartel de
 *    permitir/bloquear. Eso es lo más que una página puede hacer.
 *  · Ya dijo que no: ninguna página puede volver a abrir ese permiso sola —
 *    Chrome, Safari y Android lo prohíben a propósito. Entonces se muestran
 *    los tres pasos para el aparato en el que está la persona y un botón
 *    «Probar de nuevo». Y se escucha el permiso: apenas cambia a permitido,
 *    se vuelve a pedir solo, sin que tenga que tocar nada.
 *
 * `mensaje` es el texto que dejó el último intento (vacío = no hubo error).
 * `onPedir` vuelve a pedir la ubicación; el padre decide qué hacer con ella.
 */
export function PermisoUbicacion({ mensaje, onPedir, motivo = "Para ordenar por cercanía y mostrarte dónde estás en el mapa" }: {
  mensaje: string;
  onPedir: () => void | Promise<unknown>;
  motivo?: string;
}) {
  const [estado, setEstado] = useState<"granted" | "prompt" | "denied" | "unknown">("unknown");
  const [pidiendo, setPidiendo] = useState(false);

  useEffect(() => {
    let status: PermissionStatus | null = null;
    let vivo = true;
    (async () => {
      try {
        if (!("permissions" in navigator)) return;
        status = await navigator.permissions.query({ name: "geolocation" as PermissionName });
        if (!vivo) return;
        setEstado(status.state);
        status.onchange = () => {
          if (!status || !vivo) return;
          setEstado(status.state);
          // Cambió a permitido desde el candado o los Ajustes: se pide sola.
          if (status.state === "granted") onPedir();
        };
      } catch { /* Safari viejo: sin Permissions API */ }
    })();
    return () => { vivo = false; if (status) status.onchange = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function pedir() {
    setPidiendo(true);
    try { await onPedir(); } finally { setPidiendo(false); }
  }

  const bloqueado = estado === "denied" || /denegado/i.test(mensaje);
  const donde = aparato();
  const { pasos, recargar } = pasosPermisoUbicacion(donde);

  if (!bloqueado) {
    return (
      <div className="uk-permiso" role="status">
        <p>
          <b>📍 {motivo}, URUKU necesita tu ubicación.</b>
          {mensaje && !/denegado/i.test(mensaje) ? <span> {mensaje}</span> : <span> El navegador te va a preguntar; elegí «Permitir».</span>}
        </p>
        <button type="button" className="uk-btn uk-btn-primary" onClick={pedir} disabled={pidiendo}>
          {pidiendo ? "Pidiendo…" : "Dar permiso de ubicación"}
        </button>
      </div>
    );
  }

  return (
    <div className="uk-permiso bloqueado" role="alert">
      <p><b>📍 El navegador tiene la ubicación bloqueada para uruku.bo.</b> Se destraba en tres pasos{donde === "iphone" ? " del iPhone" : donde === "android" ? " del celular" : ""}:</p>
      <ol>
        {pasos.map((p) => <li key={p}>{p}</li>)}
      </ol>
      <div className="uk-permiso-acciones">
        {recargar && (
          <button type="button" className="uk-btn uk-btn-primary" onClick={() => window.location.reload()}>Ya lo activé, recargar</button>
        )}
        <button type="button" className={recargar ? "uk-btn-ghost" : "uk-btn uk-btn-primary"} onClick={pedir} disabled={pidiendo}>
          {pidiendo ? "Probando…" : "Probar de nuevo"}
        </button>
      </div>
    </div>
  );
}
