"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Ic } from "@/components/ic";
import {
  constructorVoz, debeReintentarConRespaldo, errorDeVoz, idiomaVoz, MENSAJES_VOZ,
  SILENCIO_MAX_MS, textoDeEvento,
  type ConstructorReconocedor, type ReconocedorVoz,
} from "@/lib/voz";

type VentanaVoz = Window & {
  SpeechRecognition?: ConstructorReconocedor;
  webkitSpeechRecognition?: ConstructorReconocedor;
};

/**
 * Botón de micrófono para la caja de búsqueda: dicta y busca, con la Web
 * Speech API del navegador (gratis, sin servicios ni dependencias).
 *
 * Va adentro del `<form className="uk-search">`. Es un componente de cliente
 * aparte porque el buscador del encabezado es de servidor.
 *
 * - Si el navegador no tiene reconocimiento de voz, NO dibuja nada (ni el
 *   botón). Se decide después de montar: en el servidor no se sabe.
 * - Al reconocer: con `onResultado` se lo pasa a quien lo usa (la pantalla de
 *   /buscar, que busca en vivo); sin él, pone el texto en el campo `q` del
 *   formulario y lo envía (el buscador del encabezado va a /buscar?q=…).
 * - Tocar de nuevo corta. Sin hablar, corta solo a los ~8 s.
 * - El estado («Escuchando…», errores) está en una región `aria-live`.
 */
export function MicrofonoBusqueda({ onResultado }: {
  onResultado?: (texto: string) => void;
}) {
  const [soporta, setSoporta] = useState(false);
  const [escuchando, setEscuchando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const boton = useRef<HTMLButtonElement>(null);
  const rec = useRef<ReconocedorVoz | null>(null);
  const ctor = useRef<ConstructorReconocedor | null>(null);
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);
  const alCallar = useRef<ReturnType<typeof setTimeout> | null>(null);
  const corteManual = useRef(false);

  useEffect(() => {
    ctor.current = constructorVoz(window as VentanaVoz);
    setSoporta(ctor.current !== null);
    return () => {
      if (temporizador.current) clearTimeout(temporizador.current);
      if (alCallar.current) clearTimeout(alCallar.current);
      try { rec.current?.abort(); } catch { /* ya estaba parado */ }
    };
  }, []);

  const armarSilencio = useCallback(() => {
    if (temporizador.current) clearTimeout(temporizador.current);
    temporizador.current = setTimeout(() => {
      try { rec.current?.stop(); } catch { /* ya estaba parado */ }
    }, SILENCIO_MAX_MS);
  }, []);

  const mostrarError = useCallback((mensaje: string) => {
    setError(mensaje);
    if (alCallar.current) clearTimeout(alCallar.current);
    alCallar.current = setTimeout(() => setError(null), 10000);
  }, []);

  const entregar = useCallback((texto: string) => {
    if (onResultado) { onResultado(texto); return; }
    const form = boton.current?.closest("form");
    const campo = form?.querySelector<HTMLInputElement>('input[name="q"]');
    if (!form || !campo) return;
    campo.value = texto;
    if (typeof form.requestSubmit === "function") form.requestSubmit();
    else form.submit();
  }, [onResultado]);

  const escuchar = useCallback((respaldo: boolean) => {
    const Reconocedor = ctor.current;
    if (!Reconocedor) return;
    const r = new Reconocedor();
    rec.current = r;
    r.lang = idiomaVoz(respaldo);
    r.continuous = false;
    r.interimResults = true;
    r.maxAlternatives = 1;

    let texto = "";
    let hayError = false;
    let reintenta = false;

    r.onstart = () => { setEscuchando(true); armarSilencio(); };
    r.onspeechstart = () => armarSilencio();
    r.onresult = (e) => {
      armarSilencio();
      const t = textoDeEvento(e);
      if (t) texto = t;
    };
    r.onerror = (e) => {
      if (debeReintentarConRespaldo(e.error, respaldo)) { reintenta = true; return; }
      const err = errorDeVoz(e.error);
      if (err) { hayError = true; mostrarError(err.mensaje); }
    };
    r.onend = () => {
      if (temporizador.current) clearTimeout(temporizador.current);
      if (reintenta) { escuchar(true); return; }
      setEscuchando(false);
      rec.current = null;
      if (texto) { entregar(texto); return; }
      // Si cortó ella a mano sin decir nada, no hay nada que reclamarle.
      if (!hayError && !corteManual.current) mostrarError(MENSAJES_VOZ.no_entendi);
    };

    try {
      r.start();
    } catch {
      // `start()` tira si ya había una sesión andando: se lo trata como un
      // intento fallido y no como un cuelgue.
      setEscuchando(false);
      mostrarError(MENSAJES_VOZ.no_entendi);
    }
  }, [armarSilencio, entregar, mostrarError]);

  const tocar = useCallback(() => {
    if (escuchando) {
      corteManual.current = true;
      try { rec.current?.stop(); } catch { /* ya estaba parado */ }
      return;
    }
    corteManual.current = false;
    setError(null);
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      mostrarError(MENSAJES_VOZ.sin_conexion);
      return;
    }
    escuchar(false);
  }, [escuchando, escuchar, mostrarError]);

  if (!soporta) return null;

  const estado = escuchando ? "Escuchando… tocá el micrófono para terminar" : error;
  return (
    <>
      <button ref={boton} type="button"
              className={`uk-mic${escuchando ? " uk-mic-on" : ""}`}
              onClick={tocar}
              aria-label={escuchando ? "Dejar de escuchar" : "Buscar con la voz"}
              aria-pressed={escuchando}
              title="Buscar con la voz">
        <Ic n="microfono" s={26} />
      </button>
      {/* Siempre en el DOM: un lector de pantalla anuncia el cambio de texto de
          una región que ya existía, no la que aparece de golpe. */}
      <span role="status" aria-live="polite"
            className={`uk-mic-estado${estado ? (escuchando ? " on escuchando" : " on error") : ""}`}>
        {estado && (
          <>
            <Ic n={escuchando ? "microfono" : "aviso"} s={18} />
            <span>{estado}</span>
          </>
        )}
      </span>
    </>
  );
}
