import "@/app/uruku.css";
import { MobileHome } from "@/components/mobile-home";
import { BottomNav } from "@/components/bottom-nav";
import { getComerciosMapa, getFeed } from "@/lib/data";
import { ciudadActual } from "@/lib/ciudad-server";

export const dynamic = "force-dynamic";

export default async function MapaPage({ searchParams }: { searchParams?: { of?: string } }) {
  const soloOfertas = searchParams?.of === "1";
  const { ciudad, ciudades } = await ciudadActual();
  const [comercios, feed] = await Promise.all([getComerciosMapa(ciudad), getFeed(10)]);
  const center: [number, number] | null =
    ciudad?.lat != null && ciudad?.lng != null ? [ciudad.lat, ciudad.lng] : null;
  return (
    <div id="ukroot" className="uk" data-theme="dark">
      <MobileHome comercios={comercios} feed={feed} soloOfertas={soloOfertas} center={center} ciudad={ciudad} ciudades={ciudades} />
      <BottomNav active={soloOfertas ? "Ofertas" : "Mapa"} />
    </div>
  );
}
