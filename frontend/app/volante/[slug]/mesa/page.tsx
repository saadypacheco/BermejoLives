import QRCode from "qrcode";
import { nombreCiudadDe } from "@/lib/data";
import { getComercioBySlug } from "@/lib/data";

export const dynamic = "force-dynamic";

/**
 * La tarjeta de mesa: el QR del local para dejar en cada mesa.
 *
 * Nació para los restaurantes —"escaneá y mirá la carta"— pero sirve para
 * cualquier mostrador. Para el local es un menú que no hay que reimprimir
 * cuando cambia un precio: la carta vive en su ficha, y la ficha la actualiza
 * él mismo mandando una foto al grupo. Para URUKU es publicidad en el lugar
 * exacto donde alguien está con el celular en la mano y tiempo para mirar.
 *
 * CUATRO POR HOJA A4, con marcas de corte. Una tarjeta por hoja es tirar tres
 * cuartos del papel; y son cuatro mesas.
 *
 * "Carta" o "ofertas" según el rubro: a un restaurante le hablás de su carta;
 * a una ferretería, de sus ofertas. Es la misma ficha, cambia la palabra que
 * hace que el que la lee entienda qué va a ver.
 */
const RUBROS_CON_CARTA = new Set([
  "restaurantes", "comida-rapida", "cafeteria", "bebidas", "panaderia", "nocturna", "hospedaje",
]);

export default async function TarjetaMesaPage({ params }: { params: { slug: string } }) {
  const comercio = await getComercioBySlug(params.slug);
  if (!comercio) {
    return <div style={{ padding: 40 }}>No encontramos ese comercio.</div>;
  }

  const url = `https://uruku.bo/comercios/${comercio.slug}`;
  const ciudadNombre = await nombreCiudadDe(comercio.ciudad_id);
  // `?ref=mesa-<slug>`: lo que dice, después, si las tarjetas de mesa
  // trajeron a alguien (Admin › Panel › Llegadas por QR).
  const qr = await QRCode.toDataURL(`${url}?ref=mesa-${comercio.slug}`, {
    width: 640, margin: 1, errorCorrectionLevel: "M",
    color: { dark: "#0f2c33", light: "#ffffff" },
  });
  const conCarta = RUBROS_CON_CARTA.has(comercio.rubro_slug ?? "");
  const invitacion = conCarta ? "Escaneá y mirá la carta" : "Escaneá y mirá las ofertas";
  const detalle = conCarta
    ? "Platos, precios y novedades, siempre al día."
    : "Precios, novedades y cómo llegar, siempre al día.";

  const tarjeta = (
    <div className="mesa">
      <img className="mesa-logo" src="/logouruku-wordmark.png" alt="URUKU" />
      <div className="mesa-nombre">{comercio.nombre}</div>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img className="mesa-qr" src={qr} alt={`Ficha de ${comercio.nombre} en URUKU`} />
      <div className="mesa-invita">{invitacion}</div>
      <div className="mesa-detalle">{detalle}</div>
      <div className="mesa-pie">
        <b>uruku.bo</b>
        <span>Todo lo que se vende en {ciudadNombre}, en el mapa</span>
      </div>
    </div>
  );

  return (
    <div className="mesa-hoja">
      <div className="mesa-pliego">
        {tarjeta}{tarjeta}{tarjeta}{tarjeta}
      </div>

      <style>{`
        .mesa-hoja { background: #e9e6dd; min-height: 100vh; padding: 20px; display: grid; place-items: start center; }
        /* A4 con cuatro A6. Las líneas punteadas entre tarjetas son la guía
           de corte: una tijera y listo. */
        .mesa-pliego { width: 210mm; height: 297mm; background: #fff; box-sizing: border-box;
          display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr;
          box-shadow: 0 10px 40px rgba(0,0,0,.18); }
        .mesa { box-sizing: border-box; padding: 10mm 9mm; display: flex; flex-direction: column;
          align-items: center; text-align: center; gap: 3mm; color: #14322b;
          font-family: system-ui, -apple-system, sans-serif; border: 1px dashed #b9c8c1; }
        .mesa-logo { height: 7.5mm; width: auto; }
        .mesa-nombre { font-size: 19px; font-weight: 800; line-height: 1.15; margin-top: 2mm; }
        .mesa-qr { width: 58mm; height: 58mm; margin-top: 2mm; }
        .mesa-invita { font-size: 16px; font-weight: 700; margin-top: 2mm; }
        .mesa-detalle { font-size: 12px; color: #3d5b50; line-height: 1.4; }
        .mesa-pie { margin-top: auto; display: flex; flex-direction: column; gap: 1px; border-top: 1px solid #cfdcd6;
          padding-top: 3mm; width: 100%; }
        .mesa-pie b { font-size: 13px; letter-spacing: .02em; }
        .mesa-pie span { font-size: 10.5px; color: #6b8177; }

        @media print {
          @page { size: A4; margin: 0; }
          .mesa-hoja { background: #fff; padding: 0; min-height: auto; display: block; }
          .mesa-pliego { box-shadow: none; }
        }
      `}</style>
    </div>
  );
}
