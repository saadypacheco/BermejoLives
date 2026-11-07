"use client";

/**
 * «Instalar la app»: el botón permanente (pie y menú de Ingresar) y la hoja
 * que explica qué hacer según el aparato y el navegador.
 *
 * Las reglas viven en `lib/instalar-app.ts` (puro, con tests). Acá sólo está
 * lo que toca el navegador: guardar el aviso `beforeinstallprompt`, saber si
 * la app ya está instalada y dibujar la hoja.
 *
 * El aviso nativo se guarda a nivel de MÓDULO y no en el estado de un
 * componente: Chrome lo dispara una sola vez y puede llegar antes de que
 * cualquier botón exista. Los tres lugares que instalan (pie, menú y banner)
 * comparten el mismo.
 */
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Ic } from "@/components/ic";
import { evento as medir } from "@/lib/medicion";
import {
  detectarPlataforma, planInstalacion, intentAbrirEnChrome, instruccionManual, nombreNavegador,
  type Plataforma, type PlanInstalacion,
} from "@/lib/instalar-app";

interface EventoInstalar extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

let diferido: EventoInstalar | null = null;
let hojaAbierta = false;
let instaladaAhora = false;
const oyentes = new Set<() => void>();
const avisar = () => oyentes.forEach((f) => f());
const suscribir = (f: () => void) => { oyentes.add(f); return () => { oyentes.delete(f); }; };

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    diferido = e as EventoInstalar;
    avisar();
  });
  window.addEventListener("appinstalled", () => {
    diferido = null;
    instaladaAhora = true;
    hojaAbierta = false;
    medir("pwa_install", "installed");
    avisar();
  });
}

function estaInstalada(): boolean {
  if (instaladaAhora) return true;
  try {
    if (window.matchMedia("(display-mode: standalone)").matches) return true;
  } catch { /* matchMedia no existe: seguimos */ }
  return (window.navigator as Navigator & { standalone?: boolean }).standalone === true;
}

function leerPlataforma(): Plataforma {
  const nav = window.navigator as Navigator & { brave?: unknown };
  return detectarPlataforma(nav.userAgent, { brave: nav.brave !== undefined, maxTouchPoints: nav.maxTouchPoints });
}

/** Abre esta misma página en Chrome de Android (intent://). */
export function abrirEnChrome(): void {
  const intent = intentAbrirEnChrome(window.location.href);
  if (intent) window.location.href = intent;
}

export interface EstadoInstalacion {
  /** Falso hasta montar: en el servidor no se sabe nada del aparato. */
  listo: boolean;
  instalada: boolean;
  plataforma: Plataforma;
  plan: PlanInstalacion;
  hayPromptNativo: boolean;
}

const SERVIDOR: Plataforma = { sistema: "escritorio", navegador: "otro" };

export function useInstalacion(): EstadoInstalacion {
  const hayPromptNativo = useSyncExternalStore(suscribir, () => diferido !== null, () => false);
  const [base, setBase] = useState<{ plataforma: Plataforma; instalada: boolean } | null>(null);

  useEffect(() => {
    const sync = () => setBase({ plataforma: leerPlataforma(), instalada: estaInstalada() });
    sync();
    return suscribir(sync);
  }, []);

  const plataforma = base?.plataforma ?? SERVIDOR;
  return {
    listo: base !== null,
    instalada: base?.instalada ?? false,
    plataforma,
    plan: planInstalacion(plataforma, hayPromptNativo),
    hayPromptNativo,
  };
}

/** Lo que pasa al tocar «Instalar la app»: diálogo nativo o la hoja. */
export async function pedirInstalacion(): Promise<"aceptada" | "rechazada" | "hoja"> {
  const plataforma = leerPlataforma();
  const plan = planInstalacion(plataforma, diferido !== null);
  if (plan === "nativo" && diferido) {
    const aviso = diferido;
    // El aviso sirve una sola vez: después hay que esperar a que Chrome lo dispare de nuevo.
    diferido = null;
    avisar();
    try {
      await aviso.prompt();
      const { outcome } = await aviso.userChoice;
      medir("pwa_install", outcome === "accepted" ? "accepted" : "dismissed");
      return outcome === "accepted" ? "aceptada" : "rechazada";
    } catch {
      return "rechazada"; // si el diálogo falla, no hay nada más que hacer
    }
  }
  hojaAbierta = true;
  avisar();
  return "hoja";
}

/** Botón permanente de instalar. Se esconde si la app ya está instalada. */
export function InstalarAppBoton({ variante, alElegir }: { variante: "pie" | "menu"; alElegir?: () => void }) {
  const { listo, instalada } = useInstalacion();
  if (!listo || instalada) return null;
  const tocar = () => { alElegir?.(); void pedirInstalacion(); };

  if (variante === "pie") {
    return (
      <button type="button" className="uk-foot-link uk-foot-link-btn" onClick={tocar}>
        <Ic n="descargar" /><span>Instalar la app</span><i>›</i>
      </button>
    );
  }
  return (
    <button type="button" className="uk-acct-item uk-acct-item-btn" onClick={tocar}>
      <b className="uk-acct-item-tit"><Ic n="descargar" s={16} /> Instalar la app</b>
      <small>Tenela en la pantalla de inicio de tu celular</small>
    </button>
  );
}

/** La hoja con las instrucciones. Vive una sola vez, en el layout. */
export function InstalarHoja() {
  const abierta = useSyncExternalStore(suscribir, () => hojaAbierta, () => false);
  const { plataforma, plan } = useInstalacion();
  const cerrarRef = useRef<HTMLButtonElement>(null);

  const cerrar = () => { hojaAbierta = false; avisar(); };

  // Las instrucciones manuales de iPhone: es lo único que se le puede mostrar a quien usa Safari.
  useEffect(() => {
    if (abierta && plan === "ios") medir("pwa_install", "ios_hint");
  }, [abierta, plan]);

  useEffect(() => {
    if (!abierta) return;
    cerrarRef.current?.focus();
    const tecla = (e: KeyboardEvent) => { if (e.key === "Escape") cerrar(); };
    document.addEventListener("keydown", tecla);
    return () => document.removeEventListener("keydown", tecla);
  }, [abierta]);

  if (!abierta) return null;
  const nombre = nombreNavegador(plataforma.navegador);

  return (
    <div className="ins-fondo" onClick={cerrar}>
      <div className="ins-hoja" role="dialog" aria-modal="true" aria-labelledby="ins-titulo" onClick={(e) => e.stopPropagation()}>
        <button type="button" ref={cerrarRef} className="ins-cerrar" onClick={cerrar} aria-label="Cerrar"><Ic n="cerrar" s={18} /></button>

        {plan === "abrir-chrome" && (
          <>
            <h2 id="ins-titulo">Instalá URUKU desde Chrome</h2>
            <p>
              Si la instalás desde {nombre}, Android puede mostrarte un aviso de Google Play Protect
              («se diseñó para una versión anterior de Android»). No es un problema de URUKU: pasa
              porque ese navegador arma la app por su cuenta. Con Chrome la arma Google y el aviso no aparece.
            </p>
            <button type="button" className="btn btn-primary ins-principal" onClick={abrirEnChrome}>
              <Ic n="descargar" s={18} /> Abrir en Chrome
            </button>
            <p className="ins-chico">Cuando se abra Chrome, tocá «Instalar la app» de nuevo.</p>
            <details className="ins-detalle">
              <summary>¿No tenés Chrome?</summary>
              <p>{instruccionManual(plataforma)}</p>
              {plataforma.navegador !== "webview" && (
                <p className="ins-chico">Desde {nombre} puede aparecer el aviso de Google Play Protect; podés aceptarlo.</p>
              )}
            </details>
          </>
        )}

        {plan === "ios" && (
          <>
            <h2 id="ins-titulo">Instalá URUKU en tu iPhone</h2>
            <ol className="ins-pasos">
              <li>Abrí URUKU en <b>Safari</b>.</li>
              <li>Tocá <b>Compartir</b> <Ic n="compartir_ios" s={18} /> (el cuadrado con la flecha).</li>
              <li>Elegí <b>«Agregar a inicio»</b> y confirmá.</li>
            </ol>
            {plataforma.navegador === "ios-otro" && (
              <p className="ins-chico">Estás en otro navegador: si no ves «Agregar a inicio», abrí esta misma página en Safari.</p>
            )}
          </>
        )}

        {plan === "manual" && (
          <>
            <h2 id="ins-titulo">Instalá URUKU</h2>
            <p>{instruccionManual(plataforma)}</p>
            {plataforma.sistema === "android" && (
              <p className="ins-chico">Si ya la instalaste, buscala en la pantalla de inicio de tu celular.</p>
            )}
          </>
        )}

        {plan === "nativo" && (
          <>
            <h2 id="ins-titulo">Instalá URUKU</h2>
            <button type="button" className="btn btn-primary ins-principal" onClick={() => { cerrar(); void pedirInstalacion(); }}>
              <Ic n="descargar" s={18} /> Instalar
            </button>
          </>
        )}

        <button type="button" className="btn btn-ghost ins-secundario" onClick={cerrar}>Ahora no</button>
      </div>
    </div>
  );
}
