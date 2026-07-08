"use client";

import { useEffect, useState } from "react";

const DISMISSED_KEY = "encontralo_install_dismissed";

function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(display-mode: standalone)").matches || (window.navigator as any).standalone === true;
}

function isIOS(): boolean {
  if (typeof window === "undefined") return false;
  return /iphone|ipad|ipod/i.test(window.navigator.userAgent);
}

/** Banner de "Instalar app": botón nativo en Android/Chrome (beforeinstallprompt),
 * instrucciones manuales en iOS (Safari no dispara ese evento — nunca lo va a hacer). */
export function InstallPrompt() {
  const [deferredEvent, setDeferredEvent] = useState<any>(null);
  const [visible, setVisible] = useState(false);
  const [ios, setIos] = useState(false);

  useEffect(() => {
    if (isStandalone() || localStorage.getItem(DISMISSED_KEY)) return;

    if (isIOS()) {
      setIos(true);
      setVisible(true);
      return;
    }

    function onBeforeInstall(e: Event) {
      e.preventDefault();
      setDeferredEvent(e);
      setVisible(true);
    }
    function onInstalled() {
      localStorage.setItem(DISMISSED_KEY, "1");
      setVisible(false);
    }
    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstall);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  function dismiss() {
    localStorage.setItem(DISMISSED_KEY, "1");
    setVisible(false);
  }

  async function instalar() {
    if (!deferredEvent) return;
    deferredEvent.prompt();
    const { outcome } = await deferredEvent.userChoice;
    if (outcome === "accepted") setVisible(false);
    else dismiss();
  }

  if (!visible) return null;

  return (
    <div className="install-banner">
      <div className="install-banner-text">
        <b>Instalá Encontralo</b>
        <span>{ios ? "Tocá compartir (⬆️) y elegí \"Agregar a inicio\"" : "Accedé más rápido desde tu pantalla de inicio"}</span>
      </div>
      {!ios && <button className="btn btn-primary btn-sm" onClick={instalar}>Instalar</button>}
      <button className="install-banner-close" onClick={dismiss} aria-label="Cerrar">✕</button>
    </div>
  );
}
