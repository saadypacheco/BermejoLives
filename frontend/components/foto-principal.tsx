"use client";

import { useRef, useState } from "react";

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
export function FotoPrincipal({ url, onSubir }: {
  url: string | null | undefined;
  /** Sube el archivo y devuelve la URL nueva. */
  onSubir: (f: File) => Promise<string | null | undefined>;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [actual, setActual] = useState<string | null | undefined>(url);
  const [subiendo, setSubiendo] = useState(false);
  const [err, setErr] = useState("");

  // `url` llega después (el perfil se pide al montar): mientras no se haya
  // subido nada, manda lo que venga de afuera.
  const mostrar = actual ?? url;

  async function elegir(f: File | undefined) {
    if (!f) return;
    setErr(""); setSubiendo(true);
    try {
      const nueva = await onSubir(f);
      // Con la misma URL el navegador mostraría la foto vieja de la caché.
      setActual(nueva ? `${nueva}${nueva.includes("?") ? "&" : "?"}v=${Date.now()}` : nueva);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "No se pudo subir");
    } finally {
      setSubiendo(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap",
                  padding: 14, border: "1px solid var(--stroke)", borderRadius: 14 }}>
      <div style={{ position: "relative", width: 190, aspectRatio: "4 / 3", borderRadius: 12, overflow: "hidden",
                    background: "rgba(127,127,127,.14)", display: "grid", placeItems: "center", flexShrink: 0 }}>
        {mostrar
          ? <img src={mostrar} alt="Foto principal del negocio" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
          : <span style={{ fontSize: 13, opacity: .6 }}>Sin foto todavía</span>}
        <span style={{ position: "absolute", left: 8, top: 8, fontSize: 10.5, fontWeight: 800, letterSpacing: ".04em",
                       textTransform: "uppercase", background: "var(--neon)", color: "#06251a", padding: "4px 8px", borderRadius: 999 }}>
          Foto principal
        </span>
      </div>
      <div style={{ display: "grid", gap: 6, justifyItems: "start", flex: "1 1 220px", minWidth: 0 }}>
        <b style={{ fontSize: 15 }}>Es la primera que ve el comprador</b>
        <span style={{ fontSize: 13, color: "var(--txt-3)", lineHeight: 1.45 }}>
          En tu ficha, en el mapa y en los resultados de búsqueda. Sacale al frente del local, de día y sin gente delante.
        </span>
        <input ref={input} type="file" accept="image/*" style={{ display: "none" }}
               onChange={(e) => elegir(e.target.files?.[0])} />
        <button type="button" className="btn btn-primary btn-sm" disabled={subiendo} onClick={() => input.current?.click()}>
          {subiendo ? "Subiendo…" : mostrar ? "Cambiar la foto principal" : "Subir la foto principal"}
        </button>
        {err && <span style={{ color: "var(--pink)", fontSize: 12.5 }}>{err}</span>}
      </div>
    </div>
  );
}
