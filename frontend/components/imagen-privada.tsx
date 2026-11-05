"use client";

import { useEffect, useState, type CSSProperties } from "react";
import { Ic } from "@/components/ic";
import { getArchivoPrivado } from "@/lib/api";
import { rutaPrivada } from "@/lib/archivo-privado";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Una imagen privada del admin (comprobante de pago, foto del trámite de cambio de
 * número). El backend ya no la sirve como URL pública: el listado trae una ruta
 * (`/admin/pagos/<id>/comprobante`) que sólo responde con el Bearer del admin. Un
 * `<img src>` no lo manda, así que se pide con fetch y se muestra como blob (igual que
 * la foto de la bandeja de WhatsApp); la URL del blob se revoca al salir.
 *
 * Estados, todos con texto + ícono (no sólo color): cargando, sin foto (404 o sin dato)
 * y error con «Reintentar». Si el valor NO es una ruta privada (una URL pública de un
 * dato viejo), se muestra directo como antes.
 */
export function ImagenPrivada({ valor, alt, style, ancho = 120, alto = 84, ampliable = true }: {
  valor: string | null | undefined;
  alt: string;
  /** Estilo de la imagen y de los carteles (el tamaño suele venir del CSS del contenedor). */
  style?: CSSProperties;
  /** Tamaño de los carteles de estado cuando el CSS del contenedor no lo fija. */
  ancho?: number | string;
  alto?: number | string;
  /** Si la imagen abre en otra pestaña al tocarla. */
  ampliable?: boolean;
}) {
  const privada = rutaPrivada(valor, API) !== null;
  const [url, setUrl] = useState("");
  const [estado, setEstado] = useState<"cargando" | "ok" | "sin" | "error">("cargando");
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    if (!privada) return;
    let vivo = true;
    let creada = "";
    setEstado("cargando");
    getArchivoPrivado(valor)
      .then((b) => {
        if (!vivo) return;
        if (!b) { setEstado("sin"); return; }
        creada = URL.createObjectURL(b);
        setUrl(creada);
        setEstado("ok");
      })
      .catch(() => { if (vivo) setEstado("error"); });
    return () => {
      vivo = false;
      if (creada) URL.revokeObjectURL(creada);
      setUrl("");
    };
  }, [privada, valor, intento]);

  const marco: CSSProperties = {
    width: ancho, minWidth: ancho, height: alto, display: "flex", flexDirection: "column", alignItems: "center",
    justifyContent: "center", gap: 4, background: "var(--panel)", borderRadius: 8, color: "var(--txt-3)",
    fontSize: 12, textAlign: "center", ...style,
  };

  if (!valor) return <div style={marco}><Ic n="foto" s={16} /> sin foto</div>;
  if (!privada) {
    // Dato viejo: ya es una URL que el navegador puede abrir.
    // eslint-disable-next-line @next/next/no-img-element
    const img = <img src={valor} alt={alt} style={style} />;
    return ampliable ? <a href={valor} target="_blank" rel="noopener">{img}</a> : img;
  }
  if (estado === "cargando") return <div style={marco} role="status"><Ic n="reloj" s={16} /> cargando…</div>;
  if (estado === "sin") return <div style={marco}><Ic n="foto" s={16} /> sin foto</div>;
  if (estado === "error") {
    return (
      <div style={marco} role="alert">
        <span><Ic n="aviso" s={14} /> no se pudo cargar</span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setIntento((n) => n + 1)}>
          <Ic n="actualizar" s={13} /> Reintentar
        </button>
      </div>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element
  const img = <img src={url} alt={alt} style={style} />;
  return ampliable ? <a href={url} target="_blank" rel="noopener">{img}</a> : img;
}
