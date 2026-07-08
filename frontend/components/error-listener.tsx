"use client";

import { useEffect } from "react";
import { reportarError } from "@/lib/observabilidad";

/** Captura errores fuera del árbol de React (handlers de eventos, promesas
 * sin catch) — error.tsx solo cubre errores durante el render. */
export function ErrorListener() {
  useEffect(() => {
    function onError(e: ErrorEvent) {
      reportarError(e.message || "Error no manejado", { stack: e.error?.stack });
    }
    function onRejection(e: PromiseRejectionEvent) {
      const reason = e.reason;
      reportarError(reason?.message || String(reason) || "Promise rechazada sin manejar", { stack: reason?.stack });
    }
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
    };
  }, []);

  return null;
}
