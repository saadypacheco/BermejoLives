"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { GIT_SHA } from "@/lib/version";

// EL TELÉFONO SE QUEDA CON EL CÓDIGO VIEJO DESPUÉS DE UN DEPLOY.
//
// La PWA abierta (o una pestaña que quedó de ayer) navega adentro del sitio
// sin volver a pedir la página: cambia de ruta con JavaScript y sigue usando
// el bundle con el que arrancó. El deploy salió bien, /version lo confirma,
// en la compu se ve el arreglo... y en el celular sigue el comportamiento
// anterior. Pasó con el botón "Reservar" (sw.js v6), con las altas de campo
// (v5) y con el buscador de resultados, que seguía buscando a cada tecla
// cuando ya se había cambiado a buscar al apretar Buscar.
//
// Acá se compara el commit horneado en este bundle (GIT_SHA) con el que
// responde el servidor en /version. Si difieren, la página se recarga —
// pero SÓLO en un momento en que recargar no le pierde nada a nadie:
//
//  - Al navegar a otra ruta: la persona acaba de llegar, no escribió nada.
//    Si ya se sabía que hay versión nueva, se recarga en el acto. Si recién
//    se está averiguando, se recarga si la respuesta llega enseguida
//    (VENTANA_MS); si tarda más, se guarda el dato y se recarga en la
//    PRÓXIMA navegación.
//  - Al volver a la app (visibilitychange): sólo se averigua. Recargar ahí
//    puede tirar un formulario a medio llenar — el de campo, sin ir más
//    lejos —, así que se espera a la próxima navegación.
//
// Y nunca dos veces por el mismo commit: si después de recargar el bundle
// sigue sin coincidir (un proxy que sirviera HTML viejo, por ejemplo), no se
// entra en un bucle de recargas. Se anota en sessionStorage y listo.
const VENTANA_MS = 1500;
const CADA_MS = 60_000;
const CLAVE = "uk-recargue-por";

export async function commitDelServidor(): Promise<string | null> {
  try {
    const r = await fetch("/version", { cache: "no-store" });
    if (!r.ok) return null;
    const j = (await r.json()) as { commit?: string };
    return j.commit || null;
  } catch {
    return null;
  }
}

/** ¿Hay que recargar? Puro, para poder razonarlo sin navegador. */
export function hayVersionNueva(local: string, servidor: string | null): boolean {
  // "dev" es el valor cuando no hay GIT_SHA (next dev, o un build sin el
  // ARG): ahí no hay nada que comparar.
  if (!servidor || local === "dev" || servidor === "dev") return false;
  return servidor !== local;
}

export function VersionCheck() {
  const pathname = usePathname();
  const pendiente = useRef(false);
  const ultimaRevision = useRef(0);
  const llegadaA = useRef(0);
  const primera = useRef(true);

  function recargar(commit: string) {
    try {
      if (sessionStorage.getItem(CLAVE) === commit) return;
      sessionStorage.setItem(CLAVE, commit);
    } catch {
      // Sin sessionStorage (modo privado raro) se recarga igual: el riesgo
      // de bucle es teórico y el de quedarse con código viejo, real.
    }
    location.reload();
  }

  async function revisar(motivo: "navegacion" | "volver") {
    const ahora = Date.now();
    if (ahora - ultimaRevision.current < CADA_MS) return;
    ultimaRevision.current = ahora;
    const commit = await commitDelServidor();
    if (!hayVersionNueva(GIT_SHA, commit)) return;
    pendiente.current = true;
    if (motivo === "navegacion" && Date.now() - llegadaA.current < VENTANA_MS) recargar(commit!);
  }

  useEffect(() => {
    llegadaA.current = Date.now();
    // La primera vez es la carga de la página, y ésa viene fresca por
    // definición (el HTML no se cachea y trae los chunks nuevos). Preguntar
    // ahí es un pedido más por visita, para no enterarse de nada.
    if (primera.current) { primera.current = false; return; }
    if (pendiente.current) {
      // Ya se sabía. Se vuelve a leer el commit sólo para anotarlo.
      commitDelServidor().then((c) => c && recargar(c));
      return;
    }
    revisar("navegacion");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  useEffect(() => {
    const alVolver = () => { if (document.visibilityState === "visible") revisar("volver"); };
    document.addEventListener("visibilitychange", alVolver);
    return () => document.removeEventListener("visibilitychange", alVolver);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
