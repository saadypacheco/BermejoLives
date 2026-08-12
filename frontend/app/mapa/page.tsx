import { UrukuShell } from "@/components/uruku-shell";
import { MobileHome } from "@/components/mobile-home";
import { getComerciosMapa, getFeed } from "@/lib/data";
import { ciudadActual } from "@/lib/ciudad-server";

export const dynamic = "force-dynamic";

export default async function MapaPage({ searchParams }: { searchParams?: { of?: string } }) {
  const soloOfertas = searchParams?.of === "1";
  const { ciudad } = await ciudadActual();
  const [comercios, feed] = await Promise.all([getComerciosMapa(ciudad), getFeed(10)]);
  const center: [number, number] | null =
    ciudad?.lat != null && ciudad?.lng != null ? [ciudad.lat, ciudad.lng] : null;
  return (
    <UrukuShell fill showCatnav={false} rootClass="uk-map" activeNav={soloOfertas ? "Ofertas" : "Mapa"}>
      <MobileHome comercios={comercios} feed={feed} soloOfertas={soloOfertas} center={center} embedded />
    </UrukuShell>
  );
}
