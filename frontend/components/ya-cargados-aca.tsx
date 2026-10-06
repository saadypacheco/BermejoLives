"use client";

/**
 * «Ya cargados acá cerca»: el aviso del formulario de alta.
 *
 * Con dos agentes por ciudad y locales pegados, lo más fácil es cargar dos veces
 * el mismo. Apenas se toma el GPS se muestran los que ya están a menos de
 * RADIO_YA_CARGADO_M, con la foto de portada (lo que mejor identifica un local
 * desde la vereda). «Es este» abre ese comercio para completarlo; si es otro,
 * no hay que tocar nada y se sigue cargando.
 *
 * Es un AVISO: nunca bloquea el alta ni exige una respuesta.
 */
import { useMemo } from "react";
import { Ic } from "@/components/ic";
import { metros } from "@/lib/geo";
import type { ComercioCercano } from "@/lib/campo-cache";

/** Dos locales a menos de esto de donde está parado el agente son candidatos a
 *  ser el mismo. Más corto que «Acá» (120 m) a propósito: acá se compara contra
 *  la puerta, no contra la cuadra. */
export const RADIO_YA_CARGADO_M = 40;
const MAX_MOSTRADOS = 8;

export type EstadoLista = "cargando" | "fresca" | "guardada" | "sin-datos";

export function YaCargadosAca({ lat, lng, acc, lista, estado, onEsEste, onVerTodos }: {
  lat: number; lng: number; acc: number;
  lista: ComercioCercano[] | null; estado: EstadoLista;
  onEsEste: (id: string) => void; onVerTodos: () => void;
}) {
  const cerca = useMemo(() => {
    if (!lista) return [];
    return lista
      .map((c) => ({ c, d: metros(lat, lng, c.lat, c.lng) }))
      .filter((x) => x.d <= RADIO_YA_CARGADO_M)
      .sort((a, b) => a.d - b.d);
  }, [lista, lat, lng]);

  const baseStyle = { fontSize: 12, color: "var(--txt-3)", margin: 0 } as const;

  if (!lista) {
    if (estado === "cargando") return <p style={baseStyle}><Ic n="reloj" s={12} /> Revisando si ya está cargado…</p>;
    return (
      <p style={baseStyle}>
        <Ic n="aviso" s={12} /> No se pudo revisar si ya está cargado (sin conexión). Podés seguir cargando.
      </p>
    );
  }

  const aviso = estado === "guardada"
    ? "Lista guardada en el celular: puede no tener lo último."
    : estado === "cargando" ? "Actualizando la lista…" : "";
  // Con GPS flojo la distancia miente para los dos lados.
  const gpsFlojo = acc > RADIO_YA_CARGADO_M ? `El GPS tiene ±${acc} m: puede mostrar de más o de menos.` : "";

  if (cerca.length === 0) {
    return (
      <p style={baseStyle}>
        <Ic n="si" s={12} /> No hay comercios cargados a menos de {RADIO_YA_CARGADO_M} m.
        {aviso && ` ${aviso}`}{gpsFlojo && ` ${gpsFlojo}`}
      </p>
    );
  }

  const mostrados = cerca.slice(0, MAX_MOSTRADOS);
  return (
    <section
      aria-label="Comercios ya cargados cerca"
      style={{ border: "1px solid var(--amber)", background: "rgba(255,176,32,.08)", borderRadius: 14, padding: 12 }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 700, fontSize: 14, color: "var(--amber)" }}>
        <Ic n="aviso" s={15} /> Ya cargados acá cerca ({cerca.length})
      </div>
      <p style={{ ...baseStyle, margin: "2px 0 10px" }}>
        ¿Es alguno de estos? Si es, completalo en vez de cargarlo de nuevo. Si no es ninguno, seguí cargando.
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {mostrados.map(({ c, d }) => (
          <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 10, background: "var(--panel)", border: "1px solid var(--stroke)", borderRadius: 12, padding: 8 }}>
            <div style={{ width: 56, height: 56, borderRadius: 10, overflow: "hidden", background: "var(--bg, #0b1411)", flexShrink: 0, display: "grid", placeItems: "center", color: "var(--txt-3)" }}>
              {c.thumb
                // eslint-disable-next-line @next/next/no-img-element
                ? <img src={c.thumb} alt={`Portada de ${c.nombre || "comercio sin nombre"}`} loading="lazy" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                : <Ic n="comercios" s={24} />}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 14, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {c.nombre || "Sin nombre"}
              </div>
              <div style={{ fontSize: 12, color: "var(--txt-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {c.rubro ?? "Sin rubro"}
              </div>
              <div style={{ fontSize: 12, color: "var(--neon)", fontWeight: 700 }}>a {Math.round(d)} m</div>
            </div>
            <button type="button" className="btn btn-ghost" style={{ flexShrink: 0, minHeight: 44, padding: "8px 14px", whiteSpace: "nowrap" }} onClick={() => onEsEste(c.id)}>
              Es este
            </button>
          </div>
        ))}
      </div>

      {cerca.length > MAX_MOSTRADOS && (
        <button type="button" className="link-more" style={{ marginTop: 8, minHeight: 40 }} onClick={onVerTodos}>
          Ver los {cerca.length} en «Comercios de mi ciudad»
        </button>
      )}
      {(aviso || gpsFlojo) && <p style={{ ...baseStyle, marginTop: 8 }}>{[aviso, gpsFlojo].filter(Boolean).join(" ")}</p>}
    </section>
  );
}
