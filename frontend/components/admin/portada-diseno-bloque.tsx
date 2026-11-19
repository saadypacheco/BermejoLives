"use client";

import { useEffect, useRef, useState } from "react";
import { Ic } from "@/components/ic";
import {
  armarPortadaDiseno, descartarPropuestaDiseno, quitarPortadaDiseno, usarPortadaDiseno,
  type PortadaDiseno,
} from "@/lib/api";

/**
 * «Portada de diseño» (docs/portada-diseno.md): la foto del local con una franja de publicidad
 * (nombre, rubro y ciudad). Se arma acá, se MIRA, y recién con «Usar en la ficha» se publica.
 *
 * El texto de la imagen sale de la base. Mientras se arma, los botones quedan quietos.
 *
 * Si el listado del panel no trae las dos columnas, arranca mostrando sólo los botones y se pone al día
 * con lo que contesta cada acción (todas devuelven las dos URLs).
 *
 * `portadaUrl`: si cambia la foto de portada el servidor borra el diseño (era de la foto anterior),
 * así que el bloque vuelve a empezar vacío.
 */
type Accion = "armar" | "usar" | "descartar" | "quitar";

const TEXTO_ESPERA: Record<Accion, string> = {
  armar: "Armando la portada…",
  usar: "Poniéndola en la ficha…",
  descartar: "Descartando…",
  quitar: "Volviendo a la foto original…",
};

export function PortadaDisenoBloque({ comercioId, portadaUrl, inicial, puedeEditar = true, onCambio }: {
  comercioId: string;
  portadaUrl: string | null;
  inicial?: Partial<PortadaDiseno>;
  puedeEditar?: boolean;
  /** Algo cambió en el servidor: el listado de atrás tiene que recargarse. */
  onCambio?: () => void;
}) {
  const [estado, setEstado] = useState<PortadaDiseno>({
    portada_diseno_url: inicial?.portada_diseno_url ?? null,
    portada_diseno_propuesta_url: inicial?.portada_diseno_propuesta_url ?? null,
  });
  const [ocupado, setOcupado] = useState<Accion | null>(null);
  const [err, setErr] = useState("");
  const [aviso, setAviso] = useState("");
  const primera = useRef(true);

  // Foto de portada nueva: el servidor vació las dos columnas.
  useEffect(() => {
    if (primera.current) { primera.current = false; return; }
    setEstado({ portada_diseno_url: null, portada_diseno_propuesta_url: null });
    setErr(""); setAviso("");
  }, [portadaUrl]);

  async function correr(accion: Accion, llamar: () => Promise<PortadaDiseno>, listo: string) {
    if (ocupado) return;
    setErr(""); setAviso(""); setOcupado(accion);
    try {
      setEstado(await llamar());
      setAviso(listo);
      onCambio?.();
    } catch (e) {
      // El 400 de «sin foto» y demás errores traen el motivo en español: se muestra tal cual.
      setErr(e instanceof Error && e.message ? e.message : "No se pudo completar la acción. Probá de nuevo.");
    } finally { setOcupado(null); }
  }

  const { portada_diseno_url: actual, portada_diseno_propuesta_url: propuesta } = estado;
  const sinFoto = !portadaUrl;
  const quieto = ocupado !== null || !puedeEditar;

  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: 12, padding: 14, display: "grid", gap: 12 }}>
      <p style={{ margin: 0, fontSize: 12.5, color: "var(--txt-3)", lineHeight: 1.5 }}>
        Arma una portada de publicidad con la foto del local, el nombre, el rubro y la ciudad. Primero la ves
        y vos decidís si va a la ficha; los listados y el mapa siguen con la foto real.
      </p>

      {sinFoto && (
        <div role="status" style={{ fontSize: 12.5, color: "var(--amber)" }}>
          <Ic n="aviso" s={14} /> Este negocio no tiene foto de portada. Subí una arriba y después armá el diseño.
        </div>
      )}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-primary btn-sm" style={{ minHeight: 44 }}
          disabled={quieto || sinFoto}
          onClick={() => correr("armar", () => armarPortadaDiseno(comercioId), "Propuesta lista: mirala abajo antes de usarla.")}>
          <Ic n="documento" s={15} /> Armar portada de diseño (gratis)
        </button>
      </div>

      {ocupado && (
        <div role="status" aria-live="polite" style={{ fontSize: 12.5 }}>
          <Ic n="reloj" s={14} /> {TEXTO_ESPERA[ocupado]}
        </div>
      )}
      {err && <div role="alert" style={{ color: "var(--pink)", fontSize: 12.5 }}><Ic n="aviso" s={14} /> {err}</div>}
      {aviso && !err && !ocupado && (
        <div role="status" style={{ color: "var(--neon)", fontSize: 12.5 }}><Ic n="listo" s={14} /> {aviso}</div>
      )}

      {propuesta && (
        <figure style={{ margin: 0, display: "grid", gap: 8 }}>
          <figcaption style={{ fontSize: 13, fontWeight: 600 }}>Propuesta (todavía no se ve en la ficha)</figcaption>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={propuesta} alt="Vista previa de la portada de diseño propuesta"
               style={{ width: "100%", maxWidth: 480, aspectRatio: "1600 / 1000", objectFit: "cover", borderRadius: 10, border: "1px solid var(--border)" }} />
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="btn btn-primary btn-sm" style={{ minHeight: 44 }} disabled={quieto}
              onClick={() => correr("usar", () => usarPortadaDiseno(comercioId), "Listo: la portada de diseño ya se ve en la ficha.")}>
              <Ic n="si" s={15} /> Usar en la ficha
            </button>
            <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} disabled={quieto}
              onClick={() => correr("descartar", () => descartarPropuestaDiseno(comercioId), "Propuesta descartada.")}>
              <Ic n="cerrar" s={15} /> Descartar
            </button>
          </div>
        </figure>
      )}

      {actual && (
        <figure style={{ margin: 0, display: "grid", gap: 8 }}>
          <figcaption style={{ fontSize: 13, fontWeight: 600 }}>Portada de diseño en la ficha</figcaption>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={actual} alt="Portada de diseño que se ve ahora en la ficha"
               style={{ width: "100%", maxWidth: 240, aspectRatio: "1600 / 1000", objectFit: "cover", borderRadius: 8, border: "1px solid var(--border)" }} />
          <div>
            <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} disabled={quieto}
              onClick={() => correr("quitar", () => quitarPortadaDiseno(comercioId), "La ficha volvió a mostrar la foto original.")}>
              <Ic n="volver" s={15} /> Volver a la foto original
            </button>
          </div>
        </figure>
      )}
    </div>
  );
}
