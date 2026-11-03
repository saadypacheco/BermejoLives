"use client";

import { useCallback, useEffect, useState } from "react";
import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE, Cargando, Insignia } from "@/components/content/content-ui";
import { ContentDayPackage } from "@/components/content/content-day-package";
import { ContentReview } from "@/components/content/content-review";
import { ContentWeek } from "@/components/content/content-week";
import { getEstadoContenido, mensajeContent, type ContentStatusResponse } from "@/lib/content";

type Pestana = "revision" | "dia" | "semana";

const GB = 1024 * 1024 * 1024;

/** El estado del armado de videos en palabras (`render_worker`, §8.2). */
function EstadoArmado({ s }: { s: ContentStatusResponse }) {
  const libreGb = (s.disk.free_bytes / GB).toFixed(1);
  switch (s.render_worker) {
    case "idle": return <Insignia tono="ok" icono="listo">Armado de videos: en espera · {libreGb} GB libres</Insignia>;
    case "running": return <Insignia tono="info" icono="reloj">Armado de videos: armando uno ahora</Insignia>;
    case "paused_disk": return <Insignia tono="aviso" icono="aviso">Armado pausado: poco espacio en disco ({libreGb} GB libres)</Insignia>;
    case "disabled": return <Insignia tono="aviso" icono="aviso">Armado de videos apagado en el servidor</Insignia>;
    case "no_ffmpeg": return <Insignia tono="error" icono="aviso">Falta ffmpeg en el servidor: no se pueden armar videos</Insignia>;
    case "unsafe_dir": return <Insignia tono="error" icono="aviso">La carpeta de contenido no es segura: banco y videos apagados</Insignia>;
    default: return null;
  }
}

/**
 * Admin › Contenido para redes (§9.3): tres pestañas sobre el mismo ciclo de una
 * pieza. Revisión (se ve, se corrige y se aprueba), Paquete del día (se publica
 * red por red, a mano) y Semana (qué hay cada día). La publicación es SIEMPRE de
 * una persona: URUKU no publica solo en ninguna red.
 */
export function ContentRedesPanel() {
  const [estado, setEstado] = useState<ContentStatusResponse | null>(null);
  const [errEstado, setErrEstado] = useState("");
  const [pestana, setPestana] = useState<Pestana | null>(null);

  const cargarEstado = useCallback(async () => {
    setErrEstado("");
    try {
      const s = await getEstadoContenido();
      setEstado(s);
      // Sólo la PRIMERA vez decide la pestaña: después manda lo que eligió la persona.
      setPestana((p) => p ?? (s.queue.ready_for_review > 0 ? "revision" : "dia"));
    } catch (ex) {
      setErrEstado(mensajeContent(ex, "No se pudo leer el estado del armado de videos"));
      setPestana((p) => p ?? "dia");
    }
  }, []);

  useEffect(() => { void cargarEstado(); }, [cargarEstado]);

  const paraRevisar = estado?.queue.ready_for_review ?? 0;
  const sinArmador = estado?.render_worker === "no_renderer";
  const tabs: { id: Pestana; label: string; icono: "listo" | "calendario" | "video"; n?: number }[] = [
    { id: "revision", label: "Revisión", icono: "listo", n: paraRevisar },
    { id: "dia", label: "Paquete del día", icono: "video" },
    { id: "semana", label: "Semana", icono: "calendario" },
  ];

  return (
    <div style={{ display: "grid", gap: 14, maxWidth: 980 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        {estado && <EstadoArmado s={estado} />}
        {estado && !estado.gemini_configured && (
          <Insignia tono="info" icono="dato">Sin Gemini: los textos salen de la plantilla fija</Insignia>
        )}
      </div>
      {errEstado && <Aviso tono="aviso">{errEstado}</Aviso>}
      {sinArmador && (
        <Aviso tono="error">
          El armador de videos no está disponible. Las piezas quedan en la cola y se arman cuando vuelva; avisale a quien administra el servidor.
        </Aviso>
      )}

      <div role="tablist" aria-label="Contenido para redes" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {tabs.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={pestana === t.id}
                  onClick={() => setPestana(t.id)}
                  className={`btn btn-sm ${pestana === t.id ? "btn-primary" : "btn-ghost"}`} style={BTN_GRANDE}>
            <Ic n={t.icono} s={15} /> {t.label}{t.n ? ` (${t.n})` : ""}
          </button>
        ))}
      </div>

      {pestana === null && <Cargando texto="Cargando…" />}
      {pestana === "revision" && <ContentReview sinArmador={sinArmador} onCambioCola={() => void cargarEstado()} />}
      {pestana === "dia" && <ContentDayPackage onIrARevision={() => setPestana("revision")} />}
      {pestana === "semana" && <ContentWeek onCambioCola={() => void cargarEstado()} />}
    </div>
  );
}
