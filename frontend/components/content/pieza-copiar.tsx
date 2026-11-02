"use client";

import { useState } from "react";
import { Ic } from "@/components/ic";
import { copiarTexto } from "@/components/content/content-ui";

/**
 * «Copiar texto para tu estado» de /pieza/<token>. El texto ya trae el link de la
 * ficha del comercio con su `?ref=st-<slug>`: así se mide cuánta gente llega desde
 * el estado de WhatsApp del comerciante. Si el navegador no deja copiar solo, se
 * muestra el texto para copiarlo a mano.
 */
export function PiezaCopiar({ texto }: { texto: string }) {
  const [estado, setEstado] = useState<"" | "ok" | "no">("");
  if (!texto) return null;
  async function copiar() {
    setEstado((await copiarTexto(texto)) ? "ok" : "no");
  }
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <button type="button" className="pz-btn pz-btn-sec" onClick={() => void copiar()}>
        <Ic n={estado === "ok" ? "si" : "copiar"} s={20} /> {estado === "ok" ? "Texto copiado" : "Copiar texto para tu estado"}
      </button>
      {estado === "ok" && <p className="pz-copiado" role="status">Listo: pegalo en tu estado de WhatsApp.</p>}
      {estado === "no" && (
        <>
          <p className="pz-fallo" role="alert">No se pudo copiar solo. Mantené apretado el texto y copialo:</p>
          <textarea className="pz-texto" readOnly value={texto} onFocus={(e) => e.currentTarget.select()} />
        </>
      )}
    </div>
  );
}
