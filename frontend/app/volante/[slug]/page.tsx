import QRCode from "qrcode";
import { WA_URUKU } from "@/lib/contacto";
import { nombreCiudadDe } from "@/lib/data";
import { getComercioBySlug } from "@/lib/data";

export const dynamic = "force-dynamic";

/**
 * El volante que se deja en el mostrador, con el QR de ESE comercio.
 *
 * POR QUÉ UNO POR COMERCIO Y NO UN FOLLETO GENERAL
 * ================================================
 * Un folleto que dice "sumate a URUKU" es publicidad y se tira. Éste dice "su
 * local ya está adentro, escanee y lo ve" — y el QR lleva a su propia ficha,
 * con su foto y su nombre. Deja de ser una promesa y pasa a ser una prueba.
 *
 * Es también la salida para el caso más común de la calle: el comerciante está
 * atendiendo y no te puede escuchar. Insistir ahí quema el local; dejarle esto
 * y volver el martes, no.
 *
 * SE IMPRIME EN MEDIA HOJA
 * ========================
 * A5, que es media A4: entran dos por hoja y se cortan al medio. En una
 * impresora de oficina, sin papel especial. Un volante que necesita imprenta no
 * se imprime nunca.
 *
 * El QR se genera EN EL SERVIDOR y viaja como imagen. Hacerlo en el navegador
 * habría sumado la librería al bundle de todo el sitio para una página que se
 * abre una vez por comercio.
 *
 * DOS USOS, EL MISMO PAPEL
 * ========================
 * 1. Impreso, en el mostrador: la prueba de que está adentro y el QR para
 *    que los clientes lo abran.
 * 2. Como PDF, mandado al grupo de WhatsApp del local apenas se lo da de alta
 *    (Ctrl+P → Guardar como PDF, desde el admin). Queda fijado en el grupo,
 *    y el comerciante tiene ahí su QR, su código y cómo publicar, sin tener
 *    que acordarse de nada.
 *
 * Por eso el pie ya no lleva un número de teléfono: las ofertas se mandan al
 * grupo que se le creó al local, `URUKU · <nombre>` (manual operativo, 3.1).
 * Un número impreso en cien volantes es un número que no se puede cambiar; el
 * grupo va con cada local y sigue funcionando aunque cambie el teléfono que
 * lo atiende.
 */
export default async function VolantePage({ params }: { params: { slug: string } }) {
  const comercio = await getComercioBySlug(params.slug);
  if (!comercio) {
    return <div style={{ padding: 40 }}>No encontramos ese comercio.</div>;
  }

  // `codigo` viaja en la fila pero el tipo público no lo declara: es un dato de
  // gestión, no de la ficha. Se lee con un cast acotado en vez de ensanchar el
  // tipo, que lo haría aparecer en el autocompletado de todo el sitio.
  const codigo = (comercio as { codigo?: string | null }).codigo ?? null;
  const url = `https://uruku.bo/comercios/${comercio.slug}`;
  const ciudadNombre = await nombreCiudadDe(comercio.ciudad_id);
  // Negro sobre blanco y margen 1: un QR impreso con poco contraste o sin borde
  // blanco alrededor no lo lee ningún teléfono, y eso se descubre con cien
  // volantes ya impresos.
  // `?ref=volante-<slug>` en el QR (no en el texto impreso): cada ficha
  // abierta desde este papel queda contada como llegada del volante (0114).
  const qr = await QRCode.toDataURL(`${url}?ref=volante-${comercio.slug}`, {
    width: 520, margin: 1, errorCorrectionLevel: "M",
    color: { dark: "#0f2c33", light: "#ffffff" },
  });

  return (
    <div className="vol-hoja">
      <div className="vol">
        <img className="vol-logo" src="/logouruku-wordmark.png" alt="URUKU" />

        <h1>Su negocio ya está en URUKU</h1>
        <p className="vol-sub">
          En {ciudadNombre} lo buscan por lo que vende, no por el nombre del local.
          Acá lo encuentran, le escriben al WhatsApp y saben cómo llegar.
        </p>

        <div className="vol-qr">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={qr} alt={`Ficha de ${comercio.nombre} en URUKU`} />
          <div>
            <b>{comercio.nombre}</b>
            <span>Escanee y vea su ficha</span>
            <small>{url.replace("https://", "")}</small>
          </div>
        </div>

        <ul className="vol-lista">
          <li>Aparece en el <b>mapa</b> de la ciudad, con cómo llegar</li>
          <li>Lo encuentran buscando <b>lo que vende</b></li>
          <li>El cliente le escribe <b>directo a su WhatsApp</b></li>
          <li><b>Sin comisión</b> por venta — usted cobra como siempre</li>
        </ul>

        <div className="vol-pie">
          <b>Para publicar una oferta o una novedad</b>
          <span>
            Mande la foto al grupo de WhatsApp <b>URUKU · {comercio.nombre}</b>,
            con el precio si lo tiene. Sale en su ficha y entre las ofertas
            de {ciudadNombre}. Sin formularios, sin apps.
          </span>
        </div>

        {codigo && (
          <p className="vol-cod">Código de su local: <b>URUKU-{codigo}</b> · <a href={`/volante/${comercio.slug}/mesa`}>tarjeta de mesa</a></p>
        )}
        {/* El contacto de URUKU para el comerciante: el Anfitrión y el correo
            de comercios. Es lo que se le da en la mano; sin esto, la duda
            del jueves no tiene a quién ir. */}
        <p className="vol-cod">Dudas: WhatsApp <b>+591 {WA_URUKU.slice(3, 5)} {WA_URUKU.slice(5)}</b> · comercios@uruku.bo</p>
      </div>

      <style>{`
        /* La pantalla imita la hoja para que lo que se ve sea lo que sale. */
        .vol-hoja { background: #e9e6dd; min-height: 100vh; padding: 20px; display: grid; place-items: start center; }
        .vol { width: 148mm; min-height: 210mm; background: #fff; color: #14322b;
          padding: 14mm 13mm; box-sizing: border-box; font-family: system-ui, -apple-system, sans-serif;
          display: flex; flex-direction: column; gap: 6mm; box-shadow: 0 10px 40px rgba(0,0,0,.18); }
        .vol-logo { height: 22mm; width: auto; align-self: center; }
        .vol h1 { font-size: 26px; line-height: 1.15; margin: 0; text-align: center; }
        .vol-sub { margin: 0; text-align: center; font-size: 13.5px; line-height: 1.5; color: #3d5b50; }
        .vol-qr { display: flex; gap: 5mm; align-items: center; border: 2px solid #14322b;
          border-radius: 10px; padding: 5mm; }
        .vol-qr img { width: 38mm; height: 38mm; flex-shrink: 0; }
        .vol-qr div { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
        .vol-qr b { font-size: 17px; line-height: 1.2; }
        .vol-qr span { font-size: 13px; color: #3d5b50; }
        .vol-qr small { font-size: 11px; color: #6b8177; word-break: break-all; }
        .vol-lista { margin: 0; padding-left: 5mm; display: flex; flex-direction: column; gap: 2.5mm;
          font-size: 13.5px; line-height: 1.4; }
        .vol-pie { margin-top: auto; display: flex; flex-direction: column; gap: 1.5mm;
          border-top: 1px solid #cfdcd6; padding-top: 4mm; }
        .vol-pie > b { font-size: 13.5px; }
        .vol-pie span { font-size: 12.5px; line-height: 1.45; color: #3d5b50; }
        .vol-pie span b { color: #14322b; }
        .vol-cod { margin: 0; font-size: 11px; color: #6b8177; text-align: center; }
        .vol-cod a { color: #6b8177; }
        @media print { .vol-cod a { display: none; } }

        /* Al imprimir se va todo lo que no es la hoja. Sin esto salen el fondo
           gris y la sombra, que en papel son tinta tirada. */
        @media print {
          @page { size: A5; margin: 0; }
          .vol-hoja { background: #fff; padding: 0; min-height: auto; display: block; }
          .vol { box-shadow: none; width: 100%; min-height: 100vh; }
        }
      `}</style>
    </div>
  );
}
