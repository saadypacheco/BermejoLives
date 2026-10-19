"use client";

import { useRef, useState } from "react";
import { Ic } from "@/components/ic";
import {
  CATALOGO_MAX_TEXTO, esCatalogoSubido, textoErrorCatalogo, urlHttp, validarCatalogoPdf,
} from "@/lib/catalogo";

/**
 * Subir, ver y quitar el catálogo en PDF de un comercio. Lo usan «Mi comercio ›
 * Editar información» (el dueño) y «Completar comercio» (el agente): cambia
 * quién llama al servidor, no cómo se ve ni cómo se valida.
 *
 * El PDF se sube AL ELEGIRLO (como las fotos), no con el botón «Guardar» de la
 * pantalla: es un archivo, no un texto, y mandarlo recién al final es dejar que
 * un corte de señal se lleve los 8 MB. Antes de mandar se controla el tipo y el
 * tamaño, así que un archivo que no entra ni sale del teléfono.
 *
 * Si falla, el catálogo que había queda como estaba (el servidor no lo toca).
 *
 * Sólo habla de un PDF SUBIDO. Si `url` es un enlace que pegó una persona, acá
 * no aparece como archivo: lo maneja el campo de texto de quien lo usa.
 */
export function CatalogoPdf({ url, subir, quitar, onCambio }: {
  /** El `catalogo_url` guardado: un enlace o la URL de un PDF subido. */
  url: string | null | undefined;
  subir: (file: File, onProgreso: (pct: number) => void) => Promise<string | null>;
  quitar: () => Promise<unknown>;
  /** Avisa la URL que quedó en el servidor (null = sin catálogo). */
  onCambio: (url: string | null) => void;
}) {
  const [pct, setPct] = useState<number | null>(null);
  const [quitando, setQuitando] = useState(false);
  const [err, setErr] = useState("");
  const input = useRef<HTMLInputElement>(null);

  const hayArchivo = esCatalogoSubido(url);
  const ocupado = pct !== null || quitando;
  const enlace = hayArchivo ? urlHttp(url) : null;

  function elegir() {
    setErr("");
    // El selector se abre YA: Chrome sólo lo deja abrir unos segundos después del
    // toque, y un confirm antes se los comía. Se pregunta al elegir el archivo.
    input.current?.click();
  }

  async function alElegir(file: File) {
    const motivo = validarCatalogoPdf(file);
    if (motivo) { setErr(motivo); return; }
    if (typeof navigator !== "undefined" && !navigator.onLine) {
      setErr("Sin conexión: el catálogo no se subió. Probá de nuevo cuando haya señal.");
      return;
    }
    setErr(""); setPct(0);
    try {
      const nueva = await subir(file, setPct);
      onCambio(nueva);
    } catch (e) {
      setErr(textoErrorCatalogo(e));
    } finally { setPct(null); }
  }

  async function alQuitar() {
    if (!window.confirm("¿Quitar el catálogo? Se borra el archivo y deja de verse en la ficha.")) return;
    setErr(""); setQuitando(true);
    try {
      await quitar();
      onCambio(null);
    } catch (e) {
      setErr(textoErrorCatalogo(e));
    } finally { setQuitando(false); }
  }

  // En un contenedor angosto (el modal del admin en el celular) el texto largo
  // del botón se pasaba del borde: que baje de renglón en vez de cortarse.
  const boton = { minHeight: 44, maxWidth: "100%", whiteSpace: "normal" } as const;

  return (
    <div style={{ display: "grid", gap: 8 }}>
      {hayArchivo && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", padding: "8px 10px",
                      borderRadius: 10, border: "1px solid var(--stroke)", background: "var(--panel-2, transparent)" }}>
          <Ic n="catalogo" s={20} />
          <span style={{ fontSize: 14, fontWeight: 700 }}>Catálogo en PDF subido</span>
          {enlace && (
            <a href={enlace} target="_blank" rel="noopener" className="link-more"
               style={{ display: "inline-flex", alignItems: "center", gap: 4, minHeight: 44, marginLeft: "auto" }}>
              Ver <Ic n="abrir" s={14} />
            </a>
          )}
        </div>
      )}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-ghost" style={boton} disabled={ocupado} onClick={elegir}>
          <Ic n={hayArchivo ? "actualizar" : "documento"} s={16} />{" "}
          {hayArchivo ? "Cambiar el PDF" : `Subir catálogo (PDF, hasta ${CATALOGO_MAX_TEXTO})`}
        </button>
        {hayArchivo && (
          <button type="button" className="btn btn-ghost" style={boton} disabled={ocupado} onClick={alQuitar}>
            <Ic n="cerrar" s={14} /> {quitando ? "Quitando…" : "Quitar"}
          </button>
        )}
        <input ref={input} type="file" accept="application/pdf,.pdf" hidden
               onChange={(e) => {
                 const f = e.target.files?.[0]; e.target.value = "";
                 // Reemplazarlo borra el archivo anterior y no tiene vuelta atrás.
                 if (f && hayArchivo && !window.confirm("Ya hay un catálogo subido. ¿Reemplazarlo por el nuevo? El anterior se borra.")) return;
                 if (f) void alElegir(f);
               }} />
      </div>

      {pct !== null && (
        <div>
          <div role="progressbar" aria-label="Subiendo el catálogo" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}
               style={{ height: 8, borderRadius: 999, background: "var(--stroke)", overflow: "hidden" }}>
            <div style={{ width: `${pct}%`, height: "100%", background: "var(--neon)", transition: "width .15s" }} />
          </div>
          <div role="status" style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 4 }}>
            {pct >= 100 ? "Procesando el archivo…" : `Subiendo… ${pct} %`}
          </div>
        </div>
      )}

      {err && (
        <div role="alert" style={{ fontSize: 12.5, color: "var(--pink)", lineHeight: 1.4 }}>
          <Ic n="aviso" s={13} /> {err}
        </div>
      )}
    </div>
  );
}
