// uruku.bo/contacto: el QR que las promotoras muestran en su celular.
//
// Dos QR: «Guardar contacto» (una vCard: la cámara del teléfono ofrece agendar
// a URUKU con su WhatsApp) y «Escribir por WhatsApp» (abre el chat con el
// mensaje escrito). Se arman en el servidor, en el build: la página es
// estática y abre aunque la señal sea mala.

import type { Metadata } from "next";
import QRCode from "qrcode";
import { ContactoQr } from "@/components/contacto-qr";
import { WA_URUKU_TEXTO, vcardUruku, waUruku } from "@/lib/contacto";

export const dynamic = "force-static";

export const metadata: Metadata = {
  title: "Contacto de URUKU",
  description: `Agendá a URUKU o escribinos por WhatsApp al ${WA_URUKU_TEXTO}.`,
  robots: { index: false, follow: false },
};

const OPCIONES = { width: 640, margin: 2, errorCorrectionLevel: "M" as const, color: { dark: "#0f2c33", light: "#ffffff" } };

export default async function Contacto() {
  const enlaceWa = waUruku("Hola URUKU, quiero información para sumar mi comercio");
  const [qrContacto, qrWhatsapp] = await Promise.all([
    QRCode.toDataURL(vcardUruku(), OPCIONES),
    QRCode.toDataURL(enlaceWa, OPCIONES),
  ]);
  return <ContactoQr qrContacto={qrContacto} qrWhatsapp={qrWhatsapp} enlaceWa={enlaceWa} numero={WA_URUKU_TEXTO} />;
}
