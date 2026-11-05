import { Ic } from "@/components/ic";
import { VideoUrukuCard } from "@/components/video-uruku-card";
import type { VideoPromo } from "@/lib/data-pure";
import { videoUrl, type PublicVideo } from "@/lib/videos-pure";

/**
 * «Videos de URUKU» en la home: UNA sola sección (antes eran dos, «Videos de
 * URUKU» y «Recorrimos Bermejo»; docs/analisis-avellaneda-al-toque.md §6). Es una
 * tira horizontal con dos clases de video, ninguna se pierde:
 *
 *   1. Los publicados en las redes de URUKU (docs/contenido-redes-tecnico.md
 *      §15.2): portadas 9:16 con el nombre del comercio debajo. Al tocar una, el
 *      video se reproduce ahí mismo (`VideoUrukuCard`) y el JSON-LD `VideoObject`
 *      sale de la página, con los mismos datos.
 *   2. Los recorridos de la ciudad («Recorrimos Bermejo», `getVideosPromo`): un
 *      reproductor común, que no baja nada hasta que se lo toca de verdad.
 *
 * Componente de servidor. Lee las listas quien lo usa (`getVideosUruku` nunca
 * tira). Sin ningún video NO dibuja nada: la home no se rompe ni deja un hueco.
 */
export function VideosUruku({ videos, recorridos = [], nombre }: {
  videos: readonly PublicVideo[];
  /** Los recorridos de la ciudad (sólo hay cargados para Bermejo). */
  recorridos?: readonly VideoPromo[];
  nombre: string;
}) {
  if (videos.length === 0 && recorridos.length === 0) return null;
  return (
    <section className="uk-container uk-home-sec" aria-labelledby="home-videos-uruku">
      <div className="uk-section-head">
        <h2 id="home-videos-uruku">
          <Ic n="videos" s={22} tono="marca" /> Videos de URUKU{" "}
          {recorridos.length > 0 && <small>{videos.length > 0 ? `Lo que publicamos en las redes y recorridos por ${nombre}.` : `Recorrimos ${nombre}.`}</small>}
        </h2>
      </div>
      <div className="uk-vc-rail uk-vc-rail-mixta">
        {videos.map((v) => (
          <VideoUrukuCard key={v.id} video={v} cover={videoUrl(v.cover_url)} src={videoUrl(v.video_url)} />
        ))}
        {recorridos.map((v) => (
          <div key={v.id} className="uk-vid">
            <video src={v.url} controls preload="metadata" playsInline aria-label={v.titulo ?? `Recorrido por ${nombre}`} />
            {v.titulo && <span>{v.titulo}</span>}
          </div>
        ))}
      </div>
    </section>
  );
}
