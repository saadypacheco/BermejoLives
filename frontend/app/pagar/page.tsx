// uruku.bo/pagar: el QR de pago de la suscripción a URUKU.
//
// Se arma en el servidor y se refresca cada 5 minutos (ISR): si el admin sube
// otro QR, la gente lo ve enseguida. Sin precios de planes: el monto lo dice
// URUKU por WhatsApp a cada comercio.

import type { Metadata } from "next";
import "@/app/styles/pagar.css";
import { Ic } from "@/components/ic";
import { WA_URUKU, WA_URUKU_TEXTO } from "@/lib/contacto";
import { linkWhatsapp } from "@/lib/ficha-whatsapp";
import { getQrPagoInfo, numeroLegible, urlQrPagoImagen } from "@/lib/pago";

export const revalidate = 300;

export const metadata: Metadata = {
  title: "Pagá tu suscripción a URUKU",
  description: "Pagá tu suscripción a URUKU con el QR oficial y mandanos el comprobante por WhatsApp.",
  robots: { index: false, follow: false },
};

export default async function PagarPage() {
  const info = await getQrPagoInfo();
  const numeroComprobante = info?.whatsapp_comprobante || WA_URUKU;
  const linkComprobante = linkWhatsapp(numeroComprobante, "Hola URUKU, te mando el comprobante de pago de [mi comercio]");
  const linkPedirQr = linkWhatsapp(WA_URUKU, "Hola URUKU, necesito el QR de pago de mi suscripción");

  return (
    <main className="pg-root">
      <h1 className="pg-titulo">Pagá tu suscripción a URUKU</h1>

      {/* Seguridad: lo primero que se lee, grande y con ícono + texto */}
      <section className="pg-aviso" role="note" aria-label="Aviso de seguridad">
        <Ic n="aviso" s={28} />
        <div>
          <p className="pg-aviso-t">Los agentes de URUKU nunca cobran en efectivo. Pagá sólo a este QR.</p>
          <p className="pg-aviso-s">Fijate que arriba, en la barra del navegador, diga <b>uruku.bo</b>.</p>
        </div>
      </section>

      {info?.disponible ? (
        <>
          <div className="pg-qr">
            {/* Imagen del backend; la huella corta la caché cuando se cambia el QR. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={urlQrPagoImagen(info.huella)} alt="Código QR de pago de la suscripción a URUKU" width={440} height={440} />
          </div>
          <p className="pg-guardar"><Ic n="foto" s={16} /> Mantené apretada la imagen para guardarla.</p>

          {(info.titular || info.banco) && (
            <dl className="pg-datos">
              {info.titular && <div><dt>Titular</dt><dd>{info.titular}</dd></div>}
              {info.banco && <div><dt>Banco</dt><dd>{info.banco}</dd></div>}
            </dl>
          )}
          {info.nota && <p className="pg-nota"><Ic n="dato" s={16} /> <span>{info.nota}</span></p>}

          <ol className="pg-pasos">
            <li><b>Escaneá</b> el QR con la app de tu banco.</li>
            <li><b>Poné el monto</b> de tu plan, el que te dijo URUKU.</li>
            <li>
              <b>Mandá el comprobante</b> por WhatsApp al {numeroLegible(numeroComprobante)}
              {" "}o subilo en <b>Mi comercio › Pagar</b>.
            </li>
          </ol>

          <a className="pg-btn" href={linkComprobante} target="_blank" rel="noopener noreferrer">
            <Ic n="whatsapp" s={20} /> Mandar el comprobante por WhatsApp
          </a>
        </>
      ) : (
        <section className="pg-vacio" aria-live="polite">
          <Ic n="dato" s={32} />
          <p>El QR de pago todavía no está cargado. Pedilo por WhatsApp al <b>{WA_URUKU_TEXTO}</b>.</p>
          <a className="pg-btn" href={linkPedirQr} target="_blank" rel="noopener noreferrer">
            <Ic n="whatsapp" s={20} /> Pedir el QR por WhatsApp
          </a>
        </section>
      )}
    </main>
  );
}
