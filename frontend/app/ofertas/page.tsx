import type { Metadata } from "next";
import Link from "next/link";
import { UrukuShell } from "@/components/uruku-shell";
import { PublicacionesGrid, SolapasPublicaciones } from "@/components/publicaciones-grid";
import { UnirmeComunidad } from "@/components/unirme-comunidad";
import { FECHA_LANZAMIENTO, faltaParaLanzamiento } from "@/lib/lanzamiento";
import { getPublicaciones } from "@/lib/data";
import { ciudadActual } from "@/lib/ciudad-server";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const { ciudad } = await ciudadActual();
  const n = ciudad?.nombre ?? "Bermejo";
  return {
    title: "Ofertas de " + n + " — URUKU",
    description: "Las ofertas del día de los comercios: precios, liquidaciones y lo que llegó, con la foto y el WhatsApp de cada local.",
  };
}

/**
 * /ofertas — lo que publicaron TODOS los comercios de la ciudad, con su foto.
 *
 * La otra mitad está en la ficha de cada negocio (#ofertas): el mismo
 * contenido visto desde un local. Acá se mira la ciudad; allá, un comercio.
 */
export default async function OfertasPage() {
  const { ciudad } = await ciudadActual();
  const nombre = ciudad?.nombre ?? "Bermejo";
  const items = await getPublicaciones("oferta", 60, ciudad?.slug);

  return (
    <UrukuShell showCatnav={false} activeNav="Ofertas">
      <div className="uk-container uk-pub">
        <div className="uk-section-head">
          <h1>🏷️ Ofertas de {nombre}</h1>
          <SolapasPublicaciones activa="ofertas" />
        </div>
        <p className="uk-pub-sub">Lo que publicaron hoy los comercios. Tocá la foto para ver el negocio, o escribile directo por WhatsApp.</p>

        <PublicacionesGrid
          items={items}
          vacio={faltaParaLanzamiento() ? (
            <div className="uk-lanzamiento">
              <span className="uk-lanzamiento-tag">Nuevo en URUKU</span>
              <h2>Las ofertas empiezan {FECHA_LANZAMIENTO}</h2>
              <p>
                Desde ese día vas a ver acá, todos los días, lo que publican los comercios de {nombre}:
                precios, lo que llegó, la liquidación de la semana. Directo del local a tu celular.
              </p>
              <div className="uk-lanzamiento-acciones">
                <Link href="/buscar?vista=mapa" className="uk-btn uk-btn-primary">Mientras tanto, ver los comercios</Link>
                <Link href="/planes" className="uk-btn-ghost">¿Tenés un negocio? Publicá lo tuyo</Link>
              </div>
            </div>
          ) : (
            <div className="uk-empty">
              Todavía no hay ofertas publicadas hoy. Los comercios las mandan por WhatsApp y aparecen acá apenas se aprueban.
              <Link className="uk-btn-ghost" style={{ marginTop: 10 }} href="/buscar?vista=mapa">Ver todos los comercios</Link>
            </div>
          )}
        />

        <UnirmeComunidad variante="chico" />
      </div>
    </UrukuShell>
  );
}
