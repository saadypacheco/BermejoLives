"use client";

import { useState } from "react";
import { Ic } from "@/components/ic";

/**
 * La clave (`NOMBRE-XXXXXX`, ej. `BOUTIQUE-K7M2P9`), mostrada UNA vez. El servidor guarda sólo el hash: si
 * se cierra esto sin anotarla, la única salida es generar otra. Lo usan los tres
 * lugares donde el backend la entrega: entrar por WhatsApp (`clave_nueva`),
 * «Generar clave nueva» en Mi comercio (`clave`) y el alta de campo
 * (`clave`).
 *
 * Sin `onListo` no hay botón de seguir: la usa la app del agente, donde la
 * tarjeta queda a la vista hasta que se pasa al próximo comercio.
 */
export function ClaveUnaVez({ clave, titulo = "Tu clave para entrar", aviso, onListo, textoListo = "Ya la guardé", compacta = false, sinCopiar = false }: {
  clave: string;
  titulo?: string;
  /** Lo que se le dice a quien la lee. Por defecto, la regla general. */
  aviso?: string;
  onListo?: () => void;
  textoListo?: string;
  compacta?: boolean;
  /** Sin «Copiar»: en el celular del agente la clave quedaría en el historial
   *  del portapapeles (y tienta a pegarla en un chat). Se anota a mano. */
  sinCopiar?: boolean;
}) {
  const [copiada, setCopiada] = useState(false);
  const [noCopio, setNoCopio] = useState(false);

  async function copiar() {
    setNoCopio(false);
    try { await navigator.clipboard.writeText(clave); setCopiada(true); }
    catch { setNoCopio(true); /* sin portapapeles: la clave está a la vista */ }
  }

  return (
    <div className="glass" role="group" aria-label={titulo}
      style={{ padding: compacta ? "10px 12px" : 22, borderRadius: 16, display: "flex", flexDirection: "column", gap: compacta ? 6 : 12, textAlign: "center",
        border: "2px solid var(--neon)" }}>
      <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700, textTransform: "uppercase", letterSpacing: ".05em" }}>
        <Ic n="seguridad" s={14} /> {titulo}
      </div>
      {/* 15 caracteres con guion: el tamaño se achica con el ancho para que entre
          en una línea en el celular, y si no entra corta en el guion, no en medio. */}
      <div aria-label={`Clave ${clave.split("").map((c) => (c === "-" ? "guion" : c)).join(" ")}`}
        style={{ fontSize: compacta ? "clamp(20px, 7vw, 30px)" : "clamp(24px, 8vw, 40px)", fontWeight: 800, letterSpacing: ".06em",
          color: "var(--neon)", fontFamily: "monospace", userSelect: "all", overflowWrap: "anywhere" }}>
        {clave}
      </div>
      <p style={{ color: "var(--txt-2)", fontSize: compacta ? 12 : 14, margin: 0, lineHeight: 1.4 }}>
        {aviso ?? "Guardala: no se vuelve a mostrar. Con tu celular y esta clave entrás sin esperar el WhatsApp."}
      </p>
      {!sinCopiar && <button type="button" className="btn" onClick={copiar} aria-label="Copiar la clave"
        style={{ border: "1px solid var(--stroke)", padding: compacta ? "7px 12px" : undefined, fontSize: compacta ? 13 : undefined }}>
        {copiada ? <><Ic n="listo" s={15} /> Copiada</> : "Copiar"}
      </button>}
      {noCopio && <span role="status" style={{ color: "var(--amber)", fontSize: 12.5 }}>No se pudo copiar: anotala tal como está en pantalla.</span>}
      {onListo && (
        <button type="button" className="btn btn-primary" onClick={onListo}>{textoListo}</button>
      )}
    </div>
  );
}
