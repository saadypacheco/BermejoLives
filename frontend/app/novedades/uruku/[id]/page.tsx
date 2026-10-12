import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { UrukuShell } from "@/components/uruku-shell";
import { Ic } from "@/components/ic";
import { CompartirBoton } from "@/components/compartir-boton";
import { NovedadUrukuFotos } from "@/components/novedad-uruku-fotos";
import { fechaNovedad, getNovedadUruku } from "@/lib/data";
import { urlHttp } from "@/lib/catalogo";

// Una novedad cambia poco: se regenera cada cinco minutos. (El marco del sitio
// lee la ciudad de una cookie, así que Next la sirve dinámica igual; la
// directiva queda para el día que el marco no dependa de la cookie.)
export const revalidate = 300;

type Props = { params: { id: string } };

/** Lo que se ve al compartir el link por WhatsApp: título, un pedazo del texto y la portada. */
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const n = await getNovedadUruku(params.id);
  if (!n) return { title: "Novedad no encontrada — URUKU" };
  const titulo = `${n.titulo} — URUKU`;
  const descripcion = (n.texto?.replace(/\s+/g, " ").trim() || `Novedad de URUKU del ${fechaNovedad(n.fecha)}.`).slice(0, 200);
  const imagen = n.portada_url || n.video_poster_url || n.fotos[0]?.url || "https://uruku.bo/og-image.png";
  const url = `https://uruku.bo/novedades/uruku/${n.id}`;
  return {
    title: titulo,
    description: descripcion,
    alternates: { canonical: url },
    openGraph: { title: titulo, description: descripcion, url, siteName: "URUKU", type: "article", locale: "es_BO", images: [{ url: imagen }] },
    twitter: { card: "summary_large_image", title: titulo, description: descripcion, images: [imagen] },
  };
}

export default async function NovedadUrukuPage({ params }: Props) {
  const n = await getNovedadUruku(params.id);
  // 404 de verdad: una novedad dada de baja o un id mal copiado no es una página que existe.
  if (!n) notFound();
  const enlace = urlHttp(n.enlace_url);

  return (
    <UrukuShell showCatnav={false} activeNav="Novedades">
      <article className="uk-container uk-nov-det">
        <Link href="/novedades" className="volver"><Ic n="volver" s={18} /> Todas las novedades</Link>
        <div><span className="etiqueta">URUKU</span></div>
        <h1>{n.titulo}</h1>
        <div className="fecha"><Ic n="calendario" s={18} /> {fechaNovedad(n.fecha)}</div>

        {n.texto && <p className="texto">{n.texto}</p>}

        {n.video_url && (
          // eslint-disable-next-line jsx-a11y/media-has-caption
          <video src={n.video_url} poster={n.video_poster_url ?? n.portada_url ?? undefined}
                 controls playsInline preload="metadata" />
        )}

        <NovedadUrukuFotos fotos={n.fotos} titulo={n.titulo} />

        <div className="enlace" style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {enlace && (
            <a href={enlace} target="_blank" rel="noopener noreferrer" className="uk-btn uk-btn-primary">
              <Ic n="abrir" s={18} /> Ver más
            </a>
          )}
          <CompartirBoton titulo={n.titulo} texto={n.titulo} />
        </div>
      </article>
    </UrukuShell>
  );
}
