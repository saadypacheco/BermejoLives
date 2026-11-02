import { Ic } from "@/components/ic";
import { VideoUrukuCard } from "@/components/video-uruku-card";
import { videoUrl, type PublicVideo } from "@/lib/videos-pure";

/**
 * «Videos de URUKU» en la home (docs/contenido-redes-tecnico.md §15.2): una tira
 * horizontal de portadas 9:16 con el nombre del comercio debajo. Al tocar una, el
 * video se reproduce ahí mismo (`VideoUrukuCard`).
 *
 * Componente de servidor. Lee la lista quien lo usa (`getVideosUruku`, que nunca
 * tira) porque la home necesita los mismos datos para el JSON-LD. Sin videos NO
 * dibuja nada: la home no se rompe ni deja un hueco por esto.
 */
export function VideosUruku({ videos }: { videos: readonly PublicVideo[] }) {
  if (videos.length === 0) return null;
  return (
    <section className="uk-container uk-home-sec" aria-labelledby="home-videos-uruku">
      <div className="uk-section-head">
        <h2 id="home-videos-uruku"><Ic n="videos" s={22} tono="marca" /> Videos de URUKU</h2>
      </div>
      <div className="uk-vc-rail">
        {videos.map((v) => (
          <VideoUrukuCard key={v.id} video={v} cover={videoUrl(v.cover_url)} src={videoUrl(v.video_url)} />
        ))}
      </div>
    </section>
  );
}
