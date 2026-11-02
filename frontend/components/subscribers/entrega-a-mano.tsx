"use client";

import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE } from "@/components/content/content-ui";
import { urlApi } from "@/lib/content-pure";

export const ENTREGA_A_MANO = "Entregar el video a mano";

/**
 * La parte «bajar el video» de la tarea `piece_delivery` (docs/contenido-redes-tecnico.md §15):
 * al comerciante NO se le escribe por WhatsApp; se descarga el video (URL firmada del panel,
 * relativa, 15 minutos) y se le entrega en persona. Lo usan la tarea del suscriptor y el
 * Paquete del día. El botón «Marcar entregado» lo pone quien lo usa (cada uno cierra a su modo).
 */
export function EntregaDescarga({ downloadUrl }: { downloadUrl: string | null | undefined }) {
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <p style={{ margin: 0, fontSize: 13, color: "var(--txt-2)", lineHeight: 1.45 }}>
        Bajá el video y entregáselo al comerciante en persona. No se le manda nada por WhatsApp.
      </p>
      {downloadUrl ? (
        <>
          <div>
            <a className="btn btn-ghost btn-sm" style={BTN_GRANDE} href={urlApi(downloadUrl)} rel="noopener noreferrer">
              <Ic n="descargar" s={15} /> Descargar video
            </a>
          </div>
          <span style={{ fontSize: 12, color: "var(--txt-3)" }}>El enlace dura 15 minutos. Si no baja, recargá la lista.</span>
        </>
      ) : (
        <Aviso tono="aviso">Esta pieza no tiene video para descargar (puede haberse vencido la retención de 90 días).</Aviso>
      )}
    </div>
  );
}
