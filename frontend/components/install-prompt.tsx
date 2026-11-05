"use client";

import { useEffect, useState } from "react";
import { Ic } from "@/components/ic";
import { InstalarHoja, abrirEnChrome, pedirInstalacion, useInstalacion } from "@/components/instalar-app";

const DISMISSED_KEY = "encontralo_install_dismissed";

function leerDescartado(): boolean {
  try { return localStorage.getItem(DISMISSED_KEY) !== null; } catch { return false; }
}

/** Banner de "Instalar app".
 *
 *  - Chrome (Android o compu): el diálogo nativo (`beforeinstallprompt`).
 *  - Android con OTRO navegador (Samsung Internet, Edge, Firefox, Brave,
 *    Opera…): NO se ofrece instalar directo. Ese navegador arma su propio
 *    paquete con un Android viejo y Google Play Protect avisa «se diseñó para
 *    una versión anterior». Se ofrece abrir en Chrome, donde Google arma la app.
 *  - iPhone: instrucciones manuales (Safari no dispara ese evento, ni va a).
 *
 *  También monta la hoja de «Instalar la app» que usan el pie y el menú. */
export function InstallPrompt() {
  const { listo, instalada, plan } = useInstalacion();
  const [descartado, setDescartado] = useState(true);

  useEffect(() => { setDescartado(leerDescartado()); }, []);

  function dismiss() {
    try { localStorage.setItem(DISMISSED_KEY, "1"); } catch { /* sin almacenamiento: se cierra igual */ }
    setDescartado(true);
  }

  async function instalar() {
    const r = await pedirInstalacion();
    if (r !== "hoja") dismiss();
  }

  const ofrecer = listo && !instalada && !descartado && (plan === "ios" || plan === "abrir-chrome" || plan === "nativo");
  const ios = plan === "ios";
  const aChrome = plan === "abrir-chrome";

  return (
    <>
      {ofrecer && (
        <div className="install-banner">
          <div className="install-banner-text">
            <b>{aChrome ? "Instalá URUKU desde Chrome" : "Instalá URUKU"}</b>
            <span>
              {ios
                ? <>Tocá compartir <Ic n="compartir_ios" s={15} /> y elegí &quot;Agregar a inicio&quot;</>
                : aChrome
                  ? "Así Android no muestra el aviso de versión"
                  : "Accedé más rápido desde tu pantalla de inicio"}
            </span>
          </div>
          {aChrome && <button className="btn btn-primary btn-sm" onClick={abrirEnChrome}>Abrir en Chrome</button>}
          {plan === "nativo" && <button className="btn btn-primary btn-sm" onClick={instalar}>Instalar</button>}
          <button className="install-banner-close" onClick={dismiss} aria-label="Cerrar"><Ic n="cerrar" s={16} /></button>
        </div>
      )}
      <InstalarHoja />
    </>
  );
}
