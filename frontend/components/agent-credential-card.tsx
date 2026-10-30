"use client";

// La credencial impresa del agente: tarjeta CR80 vertical (54 × 85,6 mm, la de
// las tarjetas de crédito: entra en cualquier portacredencial), frente y reverso.
//
// El QR lleva a `<origen>/agentes/<token>` (en QA sale encontralo.store, en
// producción uruku.bo). Se arma con `qrcode` importado DENTRO del efecto, para
// que la librería no viaje en el bundle del resto del sitio. Negro sobre blanco,
// margen 1, corrección M: igual que el volante (un QR con poco contraste no lo
// lee ningún teléfono, y eso se descubre con la tarjeta ya impresa).
//
// Reusable: «Mi credencial» en la app del agente (pendiente) va a usar este mismo
// componente. `slotAtras` es el lugar armado para el QR de la comunidad de
// comercios (etapa E2, todavía no existe).

import { useEffect, useState } from "react";
import "@/app/styles/credencial-agente.css";
import { WA_URUKU_TEXTO } from "@/lib/contacto";
import { nombreCompleto } from "@/lib/agent-credentials";

type Props = {
  nombre: string | null;
  apellido: string | null;
  ciudad: string | null;
  photoUrl: string | null;
  token: string;
  /** Contenido extra del reverso (p. ej. el QR de la comunidad, cuando exista). */
  slotAtras?: React.ReactNode;
};

export function AgentCredentialCard({ nombre, apellido, ciudad, photoUrl, token, slotAtras }: Props) {
  const [qr, setQr] = useState<string | null>(null);
  const [fallo, setFallo] = useState(false);
  const url = typeof window === "undefined" ? "" : `${window.location.origin}/agentes/${token}`;

  useEffect(() => {
    let vivo = true;
    const destino = `${window.location.origin}/agentes/${token}`;
    setQr(null); setFallo(false);
    import("qrcode")
      .then((m) => m.toDataURL(destino, { width: 520, margin: 1, errorCorrectionLevel: "M", color: { dark: "#000000", light: "#ffffff" } }))
      .then((d) => { if (vivo) setQr(d); })
      .catch(() => { if (vivo) setFallo(true); });
    return () => { vivo = false; };
  }, [token]);

  const completo = nombreCompleto(nombre, apellido);

  return (
    <div className="acc-par">
      <article className="acc-cara acc-frente" aria-label="Frente de la credencial">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="acc-logo" src="/logouruku-wordmark.png" alt="URUKU" />
        {photoUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img className="acc-foto" src={photoUrl} alt={`Foto de ${completo}`} />
        ) : (
          <div className="acc-foto acc-foto-vacia">Sin foto</div>
        )}
        <h2 className="acc-nombre">{completo}</h2>
        <p className="acc-rol">Agente de URUKU{ciudad ? ` · ${ciudad}` : ""}</p>
        <div className="acc-qr">
          {qr ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={qr} alt={`QR que abre ${url}`} />
          ) : (
            <span className="acc-qr-espera" role="status">{fallo ? "No se pudo armar el QR" : "Armando el QR…"}</span>
          )}
        </div>
        <p className="acc-escanea">Escaneá para comprobar que soy agente</p>
        <p className="acc-pie">Los agentes de URUKU nunca cobran.</p>
      </article>

      <article className="acc-cara acc-reverso" aria-label="Reverso de la credencial">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="acc-logo" src="/logouruku-wordmark.png" alt="URUKU" />
        <p className="acc-aviso">Si alguien te pide plata en nombre de URUKU, <b>no pagues</b> y avisanos.</p>
        <p className="acc-wa">WhatsApp URUKU<br /><b>{WA_URUKU_TEXTO}</b></p>
        {slotAtras}
        <p className="acc-web">uruku.bo/agentes</p>
        <p className="acc-pie">Los agentes de URUKU nunca cobran.</p>
      </article>
    </div>
  );
}
