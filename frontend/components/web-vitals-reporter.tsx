"use client";

import { useReportWebVitals } from "next/web-vitals";
import { reportarMetrica } from "@/lib/observabilidad";

const METRICAS_RELEVANTES = new Set(["LCP", "TTFB", "INP", "CLS", "FCP"]);

/** "Repetida" = el service worker ya controla la página, por lo tanto los
 * assets estáticos deberían venir de caché (ver umbral distinto en el admin). */
function esVisitaRepetida(): boolean {
  return typeof navigator !== "undefined" && !!navigator.serviceWorker?.controller;
}

export function WebVitalsReporter() {
  useReportWebVitals((metric) => {
    if (!METRICAS_RELEVANTES.has(metric.name)) return;
    reportarMetrica(window.location.pathname, metric.name.toLowerCase(), metric.value, esVisitaRepetida());
  });
  return null;
}
