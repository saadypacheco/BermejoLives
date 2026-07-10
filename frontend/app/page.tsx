import { MobileHome } from "@/components/mobile-home";
import { BottomNav } from "@/components/bottom-nav";
import { getComerciosMapa, getFeed } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function Home({ searchParams }: { searchParams?: { of?: string } }) {
  const soloOfertas = searchParams?.of === "1";

  // Diagnóstico temporal (self-host, 2026-07-10): supabase-js está devolviendo
  // un error sin forma reconocible (objeto vacío). fetch crudo, sin pasar por
  // la librería, para ver el error real de Node (con .cause.code si es de red).
  if (typeof window === "undefined") {
    const url = `${process.env.SUPABASE_INTERNAL_URL || process.env.NEXT_PUBLIC_SUPABASE_URL}/comercios?limit=1`;
    try {
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY}` },
        cache: "no-store",
      });
      const body = await res.text();
      console.warn("DIAG fetch crudo:", url, "status=", res.status, "body=", body.slice(0, 300));
    } catch (e: any) {
      console.warn(
        "DIAG fetch crudo EXCEPTION:", url,
        "name=", e?.name, "message=", e?.message,
        "cause.code=", e?.cause?.code, "cause.message=", e?.cause?.message,
        "stack=", e?.stack?.slice(0, 500),
      );
    }
  }

  const [comercios, feed] = await Promise.all([getComerciosMapa(), getFeed(10)]);
  return (
    <>
      <MobileHome comercios={comercios} feed={feed} soloOfertas={soloOfertas} />
      <BottomNav active={soloOfertas ? "Ofertas" : "Mapa"} />
    </>
  );
}
