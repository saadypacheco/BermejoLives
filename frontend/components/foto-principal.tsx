"use client";

import { useRef, useState } from "react";
import { Ic } from "@/components/ic";

/**
 * La foto principal del negocio (la portada): la que se ve primero en la
 * ficha, en el mapa y en los resultados.
 *
 * Existía desde siempre, pero para cambiarla había que darse cuenta de que
 * la miniatura de 58 px de arriba era un botón — y el cartelito «cambiar»
 * sólo aparecía al pasar el mouse, cosa que en un celular no pasa nunca. El
 * dueño entraba a Fotos, podía borrar las demás, y la primera no había forma
 * de tocarla. Acá va donde la fue a buscar, con la foto grande y un botón
 * que dice qué hace.
 *
 * Los estilos van acá adentro a propósito: este panel no carga `uruku.css`
 * —es la otra piel, la del panel— y una clase que no existe se ve como un
 * bloque sin formato.
 */
export function FotoPrincipal({ url, onSubir, soloLectura = false, textoBoton, aspecto = "4 / 3", recorte, confirmarCambio, compacto = false }: {
  url: string | null | undefined;
  /** Sube el archivo y devuelve la URL nueva. */
  onSubir: (f: File) => Promise<string | null | undefined>;
  /** Sin permiso para cambiarla (p. ej. el publicador sin `comercios.editar`): se ve, no se toca. */
  soloLectura?: boolean;
  /** Para decir «Subir otra» en vez de «Cambiar la foto principal». */
  textoBoton?: string;
  /** Si viene y ya hay foto, se pregunta antes de abrir el selector: subir otra
   *  descarta la actual (no queda en la galería). */
  confirmarCambio?: string;
  /** Versión angosta para el modal del panel: foto más chica y sin el texto de ayuda. */
  compacto?: boolean;
  /** Forma del recuadro (CSS `aspect-ratio`). El panel usa la de la tarjeta de resultados. */
  aspecto?: string;
  /** «Recorte: más arriba / más abajo». `valor` es el % vertical (0-100) que va al
   *  centro del recorte; `null` = nadie lo tocó (se dibuja al medio). */
  recorte?: { valor: number | null; onChange: (v: number) => void };
}) {
  const input = useRef<HTMLInputElement>(null);
  // La URL subida acá, atada a la que el padre tenía en ese momento: si el padre
  // la cambia por otro camino (p. ej. «Usar como portada» desde la galería), esta
  // deja de valer y manda la de afuera.
  const [actual, setActual] = useState<{ base: string | null | undefined; ver: string | null | undefined } | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const [err, setErr] = useState("");
  const [avisar, setAvisar] = useState(false);

  const mostrar = actual && actual.base === url ? actual.ver : url;

  async function elegir(f: File | undefined) {
    if (!f) return;
    setErr(""); setSubiendo(true);
    try {
      const nueva = await onSubir(f);
      // Con la misma URL el navegador mostraría la foto vieja de la caché.
      setActual({ base: nueva, ver: nueva ? `${nueva}${nueva.includes("?") ? "&" : "?"}v=${Date.now()}` : nueva });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "No se pudo subir");
    } finally {
      setSubiendo(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <div style={{ display: "flex", gap: 16, alignItems: compacto ? "flex-start" : "center", flexWrap: "wrap",
                  padding: 14, border: "1px solid var(--stroke)", borderRadius: 14 }}>
      <div style={{ position: "relative", width: compacto ? 150 : 190, aspectRatio: aspecto, borderRadius: 12, overflow: "hidden",
                    background: "rgba(127,127,127,.14)", display: "grid", placeItems: "center", flexShrink: 0 }}>
        {mostrar
          ? <img src={mostrar} alt="Foto principal del negocio"
                 style={{ width: "100%", height: "100%", objectFit: "cover", display: "block",
                          objectPosition: `center ${recorte?.valor ?? 50}%` }} />
          : <span style={{ fontSize: 13, opacity: .6 }}>Sin foto todavía</span>}
        <span style={{ position: "absolute", left: 8, top: 8, fontSize: 10.5, fontWeight: 800, letterSpacing: ".04em",
                       textTransform: "uppercase", background: "var(--neon)", color: "#06251a", padding: "4px 8px", borderRadius: 999 }}>
          Foto principal
        </span>
      </div>
      <div style={{ display: "grid", gap: 6, justifyItems: "start", flex: compacto ? "1 1 150px" : "1 1 220px", minWidth: 0 }}>
        <b style={{ fontSize: 15 }}>Es la primera que ve el comprador</b>
        {!compacto && (
          <span style={{ fontSize: 13, color: "var(--txt-3)", lineHeight: 1.45 }}>
            En tu ficha, en el mapa y en los resultados de búsqueda. Sacale al frente del local, de día y sin gente delante.
          </span>
        )}
        {!soloLectura && (
          <>
            <input ref={input} type="file" accept="image/*" style={{ display: "none" }}
                   onChange={(e) => elegir(e.target.files?.[0])} />
            {/* El aviso va EN la pantalla y no en un window.confirm: Chrome sólo
                deja abrir el selector de archivos unos segundos después del toque,
                y quien leía el confirm con calma tocaba «OK» y no pasaba nada. Acá
                el botón del aviso es un toque nuevo y abre el selector siempre. */}
            {avisar ? (
              <div role="alert" style={{ display: "grid", gap: 8, padding: 10, borderRadius: 10,
                                          border: "1px solid var(--amber)", background: "rgba(255,176,32,.08)" }}>
                <span style={{ fontSize: 12.5, lineHeight: 1.45, color: "var(--txt-2)" }}>{confirmarCambio}</span>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button type="button" className="btn btn-primary btn-sm" style={{ minHeight: 44 }}
                          onClick={() => { setAvisar(false); input.current?.click(); }}>
                    Elegir la foto nueva
                  </button>
                  <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }}
                          onClick={() => setAvisar(false)}>
                    Cancelar
                  </button>
                </div>
              </div>
            ) : (
              <button type="button" className="btn btn-primary btn-sm" style={{ minHeight: 44 }} disabled={subiendo} onClick={() => {
                        if (mostrar && confirmarCambio) { setAvisar(true); return; }
                        input.current?.click();
                      }}>
                {subiendo ? "Subiendo…" : textoBoton ?? (mostrar ? "Cambiar la foto principal" : "Subir la foto principal")}
              </button>
            )}
          </>
        )}
        {recorte && mostrar && (
          <div style={{ display: "grid", gap: 4 }}>
            <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>
              Recorte: {recorte.valor == null ? "centrado" : `${recorte.valor}%`}
            </span>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} disabled={soloLectura}
                      onClick={() => recorte.onChange(Math.max(0, (recorte.valor ?? 50) - 10))}>
                <Ic n="arriba" s={14} /> Más arriba
              </button>
              <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} disabled={soloLectura}
                      onClick={() => recorte.onChange(Math.min(100, (recorte.valor ?? 50) + 10))}>
                <Ic n="abajo" s={14} /> Más abajo
              </button>
            </div>
          </div>
        )}
        {err && <span style={{ color: "var(--pink)", fontSize: 12.5 }}>{err}</span>}
      </div>
    </div>
  );
}
