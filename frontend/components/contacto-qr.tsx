"use client";

// La pantalla de /contacto: lo que la promotora le muestra a la gente.
//
// Dos pestañas, «Guardar contacto» primero (es lo que se pidió: que la gente
// tenga a URUKU agendado) y «Escribir por WhatsApp». El QR ocupa casi todo el
// ancho y va sobre blanco: desde la pantalla de otro celular, un QR chico o
// sobre fondo oscuro tarda en leerse.
//
// Mientras la página está abierta, la pantalla no se apaga (Wake Lock): la
// promotora la tiene en la mano esperando que alguien saque el celular.

import { useEffect, useState } from "react";
import "@/app/styles/contacto.css";
import { Ic } from "@/components/ic";

type Pestana = "contacto" | "whatsapp";

export function ContactoQr({ qrContacto, qrWhatsapp, enlaceWa, numero }: {
  qrContacto: string; qrWhatsapp: string; enlaceWa: string; numero: string;
}) {
  const [pestana, setPestana] = useState<Pestana>("contacto");

  // Que la pantalla no se apague mientras se muestra el QR. Donde el navegador
  // no lo permite (o sin HTTPS) no pasa nada: se apaga como siempre.
  useEffect(() => {
    let candado: { release: () => Promise<void> } | null = null;
    const pedir = async () => {
      try {
        const wl = (navigator as Navigator & { wakeLock?: { request: (t: "screen") => Promise<{ release: () => Promise<void> }> } }).wakeLock;
        if (wl && document.visibilityState === "visible") candado = await wl.request("screen");
      } catch { /* sin permiso: sigue igual */ }
    };
    void pedir();
    // El navegador lo suelta al cambiar de app: se vuelve a pedir al volver.
    const alVolver = () => { if (document.visibilityState === "visible") void pedir(); };
    document.addEventListener("visibilitychange", alVolver);
    return () => {
      document.removeEventListener("visibilitychange", alVolver);
      void candado?.release().catch(() => {});
    };
  }, []);

  const esContacto = pestana === "contacto";
  const [bajando, setBajando] = useState(false);

  /** Baja una imagen lista para compartir (estado de WhatsApp, imprimir): no el
   *  QR pelado, sino con el título, el número y uruku.bo, para que quien la
   *  reciba sepa qué es sin que nadie se lo explique. Se dibuja en el celular
   *  con un canvas: no hace falta pedirle nada al servidor. */
  async function descargar() {
    setBajando(true);
    try {
      const img = new Image();
      img.src = esContacto ? qrContacto : qrWhatsapp;
      await img.decode();
      const W = 1080, H = 1350;
      const c = document.createElement("canvas");
      c.width = W; c.height = H;
      const g = c.getContext("2d");
      if (!g) return;
      g.fillStyle = "#ffffff"; g.fillRect(0, 0, W, H);
      g.textAlign = "center"; g.fillStyle = "#214533";
      g.font = "800 92px Poppins, Arial, sans-serif";
      g.fillText("URUKU", W / 2, 150);
      g.font = "600 44px Poppins, Arial, sans-serif";
      g.fillStyle = "#1D8D52";
      g.fillText(esContacto ? "Guardá nuestro contacto" : "Escribinos por WhatsApp", W / 2, 230);
      const lado = 820;
      g.imageSmoothingEnabled = false;   // un QR escalado con suavizado se lee peor
      g.drawImage(img, (W - lado) / 2, 280, lado, lado);
      g.fillStyle = "#214533";
      g.font = "800 72px Poppins, Arial, sans-serif";
      g.fillText(`WhatsApp ${numero}`, W / 2, 1210);
      g.fillStyle = "#4E6053";
      g.font = "500 40px Poppins, Arial, sans-serif";
      g.fillText("Comercios de Bermejo en uruku.bo", W / 2, 1285);
      const blob = await new Promise<Blob | null>((r) => c.toBlob(r, "image/png"));
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = esContacto ? "URUKU-QR-contacto.png" : "URUKU-QR-WhatsApp.png";
      document.body.appendChild(a); a.click(); a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 4000);
    } catch { /* si el navegador no deja, queda la captura de pantalla */ }
    finally { setBajando(false); }
  }

  return (
    <main className="ct-root">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img className="ct-logo" src="/uruku-horizontal.svg" alt="URUKU" />

      <div className="ct-tabs" role="tablist" aria-label="Qué hace el código">
        <button type="button" role="tab" aria-selected={esContacto} className={esContacto ? "on" : ""}
                onClick={() => setPestana("contacto")}>
          <Ic n="usuario" s={18} /> Guardar contacto
        </button>
        <button type="button" role="tab" aria-selected={!esContacto} className={!esContacto ? "on" : ""}
                onClick={() => setPestana("whatsapp")}>
          <Ic n="whatsapp" s={18} /> Escribir por WhatsApp
        </button>
      </div>

      <div className="ct-qr" role="tabpanel">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={esContacto ? qrContacto : qrWhatsapp}
             alt={esContacto ? `QR para agendar a URUKU, WhatsApp ${numero}` : `QR para escribirle a URUKU por WhatsApp al ${numero}`} />
      </div>

      <button type="button" className="ct-btn ct-btn-sec ct-bajar" onClick={descargar} disabled={bajando}>
        <Ic n="descargar" s={18} /> {bajando ? "Preparando…" : "Descargar QR"}
      </button>

      <p className="ct-instruccion">
        {esContacto
          ? "Abrí la cámara de tu celular y apuntá al código: te ofrece guardar a URUKU en tus contactos."
          : "Abrí la cámara de tu celular y apuntá al código: se abre WhatsApp para escribirle a URUKU."}
      </p>

      <p className="ct-numero"><Ic n="whatsapp" s={22} /> {numero}</p>
      <p className="ct-sub">Comercios de Bermejo en <b>uruku.bo</b></p>

      {/* Para cuando el enlace se abre en el celular de quien quiere agendar
          (se lo mandaron por WhatsApp): ahí no hay QR que escanear. */}
      <div className="ct-acciones">
        <a className="ct-btn ct-btn-sec" href="/contacto/uruku.vcf"><Ic n="descargar" s={18} /> Guardar contacto</a>
        <a className="ct-btn ct-btn-wa" href={enlaceWa} target="_blank" rel="noopener"><Ic n="whatsapp" s={18} /> Escribir</a>
      </div>
    </main>
  );
}
