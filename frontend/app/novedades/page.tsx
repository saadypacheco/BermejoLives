import type { Metadata } from "next";
import Link from "next/link";
import { UrukuShell } from "@/components/uruku-shell";
import { PublicacionesGrid, SolapasPublicaciones } from "@/components/publicaciones-grid";
import { UnirmeComunidad } from "@/components/unirme-comunidad";
import { FECHA_LANZAMIENTO, faltaParaLanzamiento } from "@/lib/lanzamiento";
import { getPublicaciones } from "@/lib/data";
import { RubrosDePublicaciones } from "@/components/rubros-publicaciones";
import { ciudadActual } from "@/lib/ciudad-server";

export const dynamic = "force-dynamic";

type Props = { searchParams?: Record<string, string | string[] | undefined> };

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const { ciudad } = await ciudadActual();
  const n = ciudad?.nombre ?? "Bermejo";
  // El rubro va en el título porque este link se comparte: lo que se ve en la
  // vista previa de WhatsApp es esto, y «Ofertas de Bermejo» no dice de qué.
  const rubro = typeof searchParams?.rubro === "string" ? searchParams.rubro : null;
  if (rubro) {
    const items = await getPublicaciones("novedad", 1, ciudad?.slug, rubro);
    const nom = (items[0]?.rubro_nombre ?? rubro).replace(/^\S+\s/, "");
    return {
      title: `Novedades de ${nom} en ${n} — URUKU`,
      description: `Lo que publicaron hoy los comercios de ${nom} en ${n}, con foto, precio y el WhatsApp de cada local.`,
    };
  }
  return {
    title: "Novedades de " + n + " — URUKU",
    description: "Lo que cuentan los comercios: mercadería nueva, horarios, cambios de local y lo que está pasando hoy.",
  };
}

/**
 * /novedades — lo que publicaron TODOS los comercios de la ciudad, con su foto.
 *
 * La otra mitad está en la ficha de cada negocio (#novedades): el mismo
 * contenido visto desde un local. Acá se mira la ciudad; allá, un comercio.
 */
export default async function NovedadesPage({ searchParams }: Props) {
  const { ciudad } = await ciudadActual();
  const nombre = ciudad?.nombre ?? "Bermejo";
  const rubro = typeof searchParams?.rubro === "string" ? searchParams.rubro : null;
  // Se piden TODAS igual: la fila de rubros sale de acá, y el filtro se aplica
  // después. Con dos consultas la fila mostraría sólo el rubro ya elegido y no
  // habría forma de volver ni de saltar a otro.
  const todas = await getPublicaciones("novedad", 60, ciudad?.slug);
  const items = rubro ? todas.filter((p) => p.rubro_slug === rubro) : todas;
  const nomRubro = rubro ? (todas.find((p) => p.rubro_slug === rubro)?.rubro_nombre ?? rubro) : null;

  return (
    <UrukuShell showCatnav={false} activeNav="Novedades">
      <div className="uk-container uk-pub">
        <div className="uk-section-head">
          <h1>📣 Novedades {nomRubro ? `de ${nomRubro.replace(/^\S+\s/, "")}` : `de ${nombre}`}</h1>
          <SolapasPublicaciones activa="novedades" />
        </div>
        <RubrosDePublicaciones items={todas} ruta="/novedades" activo={rubro} />
        <p className="uk-pub-sub">Lo que cuentan los comercios: mercadería nueva, cambios de horario, lo que está pasando hoy.</p>

        <PublicacionesGrid
          items={items}
          vacio={faltaParaLanzamiento() ? (
            <div className="uk-lanzamiento">
              <span className="uk-lanzamiento-tag">Nuevo en URUKU</span>
              <h2>Las novedades empiezan {FECHA_LANZAMIENTO}</h2>
              <p>
                Desde ese día vas a ver acá, todos los días, lo que publican los comercios de {nombre}:
                la mercadería que llega, los cambios de horario, lo que está pasando. Directo del local a tu celular.
              </p>
              <div className="uk-lanzamiento-acciones">
                <Link href="/buscar?vista=mapa" className="uk-btn uk-btn-primary">Mientras tanto, ver los comercios</Link>
                <Link href="/planes" className="uk-btn-ghost">¿Tenés un negocio? Publicá lo tuyo</Link>
              </div>
            </div>
          ) : (
            <div className="uk-empty">
              Todavía no hay novedades publicadas. Los comercios las mandan por WhatsApp y aparecen acá apenas se aprueban.
              <Link className="uk-btn-ghost" style={{ marginTop: 10 }} href="/buscar?vista=mapa">Ver todos los comercios</Link>
            </div>
          )}
        />

        <UnirmeComunidad variante="chico" />
      </div>
    </UrukuShell>
  );
}
