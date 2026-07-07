import { MobileHome } from "@/components/mobile-home";
import { BottomNav } from "@/components/bottom-nav";
import { getComerciosMapa, getFeed } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function Home({ searchParams }: { searchParams?: { of?: string } }) {
  const soloOfertas = searchParams?.of === "1";
  const [comercios, feed] = await Promise.all([getComerciosMapa(), getFeed(10)]);
  return (
    <>
      <MobileHome comercios={comercios} feed={feed} soloOfertas={soloOfertas} />
      <BottomNav active={soloOfertas ? "Ofertas" : "Mapa"} />
    </>
  );
}
