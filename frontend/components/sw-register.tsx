"use client";

import { useEffect } from "react";

/** Registra el service worker (PWA) una vez cargada la página. */
export function SwRegister() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    const reg = () => navigator.serviceWorker.register("/sw.js").catch(() => {});
    if (document.readyState === "complete") reg();
    else { window.addEventListener("load", reg); return () => window.removeEventListener("load", reg); }
  }, []);
  return null;
}
