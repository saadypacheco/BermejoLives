import QRCode from "qrcode";
import { Ic } from "@/components/ic";
import { WA_URUKU_TEXTO, waUruku } from "@/lib/contacto";

/**
 * El WhatsApp de URUKU, a la vista en el home. Antes el número no aparecía
 * escrito en ninguna pantalla: sólo detrás de algunos botones. Quien escuchaba
 * «escribinos al…» en una entrevista y entraba al sitio no lo encontraba.
 *
 * Con un QR que abre el chat: en la computadora, en una pantalla o en una
 * captura que se comparte, se escanea con el celular y queda escrito el
 * mensaje. En el mismo celular sirve el botón.
 *
 * Usa el mismo molde que el aviso de la comunidad, para que el home no sume
 * un estilo más.
 */
export async function ContactoUruku() {
  const enlace = waUruku("Hola, quiero contactar a URUKU");
  // Se arma en el servidor, como el del volante: es una imagen más, sin
  // JavaScript en el navegador. Si por algo falla, el aviso sale sin QR.
  const qr = await QRCode.toDataURL(enlace, {
    width: 240, margin: 1, errorCorrectionLevel: "M", color: { dark: "#0f2c33", light: "#ffffff" },
  }).catch(() => null);

  return (
    <section className="uk-container">
      <div className="uk-comunidad-banner">
        <div className="uk-comunidad-texto">
          <b><Ic n="whatsapp" s={17} /> Escribile a URUKU: WhatsApp {WA_URUKU_TEXTO}</b>
          <span>¿Tenés un comercio y querés aparecer, o una consulta? Te respondemos por WhatsApp.</span>
        </div>
        <div className="uk-comunidad-acciones" style={{ alignItems: "center" }}>
          <a className="uk-btn uk-btn-wa" href={enlace} target="_blank" rel="noopener">
            <Ic n="whatsapp" s={17} /> {WA_URUKU_TEXTO}
          </a>
          {qr && (
            <a href={enlace} target="_blank" rel="noopener" title="Escaneá para escribirle a URUKU por WhatsApp"
               style={{ display: "inline-flex", flexDirection: "column", alignItems: "center", gap: 4, textDecoration: "none" }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={qr} alt={`QR para escribirle a URUKU por WhatsApp al ${WA_URUKU_TEXTO}`}
                   width={120} height={120} style={{ borderRadius: 8, background: "#fff", display: "block" }} />
              <small style={{ fontSize: 11, opacity: 0.8 }}>Escaneá y escribinos</small>
            </a>
          )}
        </div>
      </div>
    </section>
  );
}
