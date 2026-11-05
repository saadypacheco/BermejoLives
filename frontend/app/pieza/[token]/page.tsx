// uruku.bo/pieza/<token>: la página del COMERCIANTE (docs/contenido-redes-tecnico.md §9.5).
//
// Le llega por el WhatsApp que le manda una persona de URUKU cuando su video ya
// salió. Acá lo mira, lo baja para su estado o su TikTok y copia el texto. No
// pide login: el token largo es la llave, y vence a los 60 días.
//
// Se consulta en CADA visita (`force-dynamic` + `no-store`) y no se indexa: ni la
// metadata ni la cabecera (`next.config.mjs`) ni `robots.txt` la dejan entrar a un
// buscador. Sin precios ni cifras de comercios.

import type { Metadata } from "next";
import "@/app/styles/pieza.css";
import { Ic } from "@/components/ic";
import { PiezaCopiar } from "@/components/content/pieza-copiar";
import { WA_URUKU_TEXTO, waUruku } from "@/lib/contacto";
import { fechaBo, urlApi, urlApiOpt, validarLinkDeRed, type ContentNetwork } from "@/lib/content-pure";
import { leerPieza } from "@/lib/pieza";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Tu video en URUKU",
  robots: { index: false, follow: false, nocache: true },
};

const REDES_CONOCIDAS = new Set<string>(["tiktok", "instagram", "facebook", "wa_channel"]);

function Logo() {
  // eslint-disable-next-line @next/next/no-img-element
  return <img className="pz-logo" src="/logouruku-wordmark.png" alt="URUKU" />;
}

function Ayuda({ texto }: { texto: string }) {
  return (
    <div className="pz-ayuda">
      <p>¿Dudas? Escribinos por WhatsApp al <b>{WA_URUKU_TEXTO}</b>.</p>
      <a className="pz-btn pz-btn-wa" href={waUruku(texto)} target="_blank" rel="noopener noreferrer">
        <Ic n="whatsapp" s={20} /> Escribir a URUKU
      </a>
    </div>
  );
}

export default async function PiezaPage(props: { params: Promise<{ token: string }> }) {
  const params = await props.params;
  const r = await leerPieza(params.token);

  if (r.tipo === "no_existe") {
    return (
      <main className="pz-root">
        <Logo />
        <section className="pz-vacio" role="alert">
          <Ic n="aviso" s={40} />
          <h1>Esta pieza no existe.</h1>
          <p>Revisá que el enlace esté completo, o pedile uno nuevo a URUKU.</p>
        </section>
        <Ayuda texto="Hola, el enlace de mi video de URUKU no abre. ¿Me pasan uno nuevo?" />
      </main>
    );
  }

  if (r.tipo === "vencido") {
    return (
      <main className="pz-root">
        <Logo />
        <section className="pz-vacio" role="alert">
          <Ic n="reloj" s={40} />
          <h1>Este enlace venció.</h1>
          <p>Pedile uno nuevo a URUKU.</p>
        </section>
        <Ayuda texto="Hola, el enlace de mi video de URUKU venció. ¿Me pasan uno nuevo?" />
      </main>
    );
  }

  if (r.tipo === "error") {
    return (
      <main className="pz-root">
        <Logo />
        <section className="pz-vacio" role="alert">
          <Ic n="aviso" s={40} />
          <h1>No pudimos abrir tu video.</h1>
          <p>Probá de nuevo en un momento.</p>
          <a className="pz-btn" href={`/pieza/${encodeURIComponent(params.token)}`}><Ic n="actualizar" s={20} /> Reintentar</a>
        </section>
        <Ayuda texto="Hola, no me abre el enlace de mi video de URUKU." />
      </main>
    );
  }

  const d = r.datos;
  const video = urlApi(d.video_url);
  const poster = urlApiOpt(d.cover_url) ?? undefined;
  // Sólo links de las redes de verdad: lo que llega de la API se valida igual antes de ponerlo en un href.
  const redes = d.posts.filter((p) =>
    REDES_CONOCIDAS.has(p.network) && !!p.post_url && validarLinkDeRed(p.network as ContentNetwork, p.post_url).ok);

  return (
    <main className="pz-root">
      <Logo />
      <h1 className="pz-titulo">Tu video en URUKU{d.comercio_nombre ? ` · ${d.comercio_nombre}` : ""}</h1>

      <video className="pz-video" controls playsInline preload="metadata" poster={poster} src={video}>
        Tu navegador no puede reproducir el video. Probá con el botón de descargar.
      </video>

      <div className="pz-acciones">
        <a className="pz-btn" href={urlApi(d.video_download_url)} download>
          <Ic n="descargar" s={20} /> Descargar para tu estado
        </a>
        <PiezaCopiar texto={d.status_text} />
      </div>

      {redes.length > 0 && (
        <p className="pz-redes">
          <b>También salió en:</b>
          {redes.map((p) => (
            <a key={p.network} className="pz-link" href={p.post_url as string} target="_blank" rel="noopener noreferrer nofollow">
              {p.network_label || p.network} <Ic n="abrir" s={14} />
            </a>
          ))}
        </p>
      )}

      {d.expires_at && <p className="pz-vence">Este enlace vence el {fechaBo(d.expires_at)}.</p>}

      <Ayuda texto="Hola, tengo una duda sobre mi video de URUKU." />
    </main>
  );
}
