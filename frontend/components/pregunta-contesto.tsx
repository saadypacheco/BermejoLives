"use client";

import { useEffect, useState } from "react";
import { posponerContacto, proximoParaPreguntar, quitarContacto, type ContactoPendiente } from "@/lib/contestaron";
import { responderContesto } from "@/lib/campo";

/**
 * El cartelito «¿Te contestó Rústico?» — Sí / No / Todavía no.
 *
 * Aparece cuando la persona vuelve al sitio después de haber tocado el
 * WhatsApp de un local (tres minutos o más después), una vez por contacto.
 * Es la única señal que URUKU puede tener de si un comercio atiende: la
 * conversación pasa en el teléfono del comerciante, donde no se ve nada.
 *
 * Con las respuestas: «✓ Responde» en la tarjeta de los que contestan, los
 * que no contestan nunca bajan al final de su rubro, y el admin ve a quién
 * llamar. Sin este cartel, un número apagado sigue primero para siempre.
 */
export function PreguntaContesto() {
  const [pendiente, setPendiente] = useState<ContactoPendiente | null>(null);
  const [listo, setListo] = useState<"" | "gracias">("");

  useEffect(() => {
    const mirar = () => { if (document.visibilityState === "visible") setPendiente(proximoParaPreguntar()); };
    mirar();
    document.addEventListener("visibilitychange", mirar);
    const t = setInterval(mirar, 60 * 1000);
    return () => { document.removeEventListener("visibilitychange", mirar); clearInterval(t); };
  }, []);

  if (!pendiente && !listo) return null;

  async function contestar(respondio: boolean) {
    if (!pendiente) return;
    quitarContacto(pendiente.id);
    responderContesto(pendiente.id, respondio);
    setPendiente(null);
    setListo("gracias");
    setTimeout(() => setListo(""), 2500);
  }

  function despues() {
    if (!pendiente) return;
    posponerContacto(pendiente.id, 30);
    setPendiente(null);
  }

  return (
    <div className="uk-contesto" role="status" aria-live="polite">
      {listo ? (
        <span className="uk-contesto-gracias">¡Gracias! Eso ayuda a que aparezcan primero los que contestan.</span>
      ) : pendiente && (
        <>
          <span className="uk-contesto-texto">¿Te contestó <b>{pendiente.nombre}</b>?</span>
          <div className="uk-contesto-btns">
            <button type="button" onClick={() => contestar(true)}>Sí</button>
            <button type="button" onClick={() => contestar(false)}>No</button>
            <button type="button" className="suave" onClick={despues}>Todavía no</button>
          </div>
        </>
      )}
    </div>
  );
}
