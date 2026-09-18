import type { Metadata } from "next";
import Link from "next/link";
import QRCode from "qrcode";
import { UrukuShell } from "@/components/uruku-shell";
import { enlacesComunidad } from "@/components/unirme-comunidad";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "La comunidad de los que compran en Bermejo — URUKU",
  description: "Cotización de la mañana, ofertas del día, cómo está el paso y un grupo por ciudad para preguntar a los que ya vinieron. Entrás vos: nadie te agrega.",
};

/**
 * /comunidad — qué es la Comunidad de WhatsApp, qué recibís, las reglas, y el
 * botón para entrar. Con el QR grande: es lo que el administrador de un
 * grupo de compras pega en su grupo, o lo que va en el volante.
 *
 * Si el enlace todavía no está cargado en /contenido, la página lo dice y
 * manda a la Ayuda: nunca un botón muerto.
 */
export default async function ComunidadPage() {
  const { comunidad, canal } = await enlacesComunidad();
  const qr = comunidad
    ? await QRCode.toDataURL(comunidad, { width: 320, margin: 1, errorCorrectionLevel: "M", color: { dark: "#0f2c33", light: "#ffffff" } })
    : null;

  return (
    <UrukuShell showCatnav={false}>
      <div className="uk-container uk-comunidad">
        <h1>La comunidad de los que compran en Bermejo</h1>
        <p className="uk-comunidad-sub">
          Una Comunidad de WhatsApp para el que viene a comprar: lo de hoy, lo de siempre, y la gente que ya vino.
          <b> Entrás vos, nadie te agrega</b>, y te vas cuando quieras.
        </p>

        <div className="uk-comunidad-grid">
          <div className="uk-comunidad-col">
            <h2>Qué recibís</h2>
            <ul className="uk-comunidad-lista">
              <li>💱 <b>La cotización de la mañana</b> (dólar y peso), antes de salir.</li>
              <li>🏷️ <b>Las ofertas del día</b> que los comercios mandan y se aprueban.</li>
              <li>🌉 <b>Cómo está el paso</b>: puente, chalanas, río.</li>
              <li>🏙️ <b>Un grupo por ciudad</b> (Salta, Jujuy, Orán, Tartagal…) para preguntar a los que ya vinieron: dónde comer, cuánto pagaron, qué tour les fue bien.</li>
              <li>💬 Lo que no esté, se lo preguntás a la <b>Ayuda de URUKU</b> o a la gente del grupo.</li>
            </ul>

            <h2>Las reglas, cortas</h2>
            <ul className="uk-comunidad-lista">
              <li>Sólo compras y viajes a Bermejo. Nada de política, cadenas ni rifas.</li>
              <li>Los comercios publican en su ficha de URUKU, no en los grupos. Lo que quieran mostrar entra por ahí.</li>
              <li>El que hace spam o vende por privado a los miembros, afuera.</li>
              <li>Tu número lo ven los del grupo, como en cualquier grupo de WhatsApp. Si preferís sólo leer, seguí el canal.</li>
            </ul>
          </div>

          <div className="uk-comunidad-col uk-comunidad-entrar">
            {comunidad ? (
              <>
                <a className="uk-btn uk-btn-wa uk-comunidad-btn" href={comunidad} target="_blank" rel="noopener">💬 Unite a la comunidad</a>
                {qr && (
                  <div className="uk-comunidad-qr">
                    <img src={qr} alt="QR para entrar a la comunidad" width={200} height={200} />
                    <small>Escaneá o compartí este QR. Es el mismo enlace.</small>
                  </div>
                )}
                {canal && (
                  <p className="uk-comunidad-canal">
                    ¿Sólo querés leer? <a href={canal} target="_blank" rel="noopener">Seguí el canal de URUKU</a>: los avisos, sin chat.
                  </p>
                )}
              </>
            ) : (
              <div className="uk-comunidad-pronto">
                <b>La comunidad se abre en estos días.</b>
                <span>Mientras tanto, la cotización, las ofertas y el estado del paso están en la <Link href="/guia">guía</Link>, y lo que
                  quieras preguntar, en el botón de <b>Ayuda</b>.</span>
              </div>
            )}
          </div>
        </div>

        <section className="uk-comunidad-admins">
          <h2>¿Administrás un grupo de compras o un tour?</h2>
          <p>
            Pegá el enlace o el QR en tu grupo: tu gente tiene la cotización, el mapa y las ofertas antes de salir, y vos
            no contestás las mismas preguntas todos los días. Si organizás viajes, tu tour puede salir en la
            <Link href="/guia#transporte"> guía de cómo llegar</Link>: escribinos al WhatsApp de URUKU.
          </p>
        </section>
      </div>
    </UrukuShell>
  );
}
