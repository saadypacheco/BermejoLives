import type { Metadata } from "next";
import Link from "next/link";
import { UrukuShell } from "@/components/uruku-shell";
import { sinEmoji } from "@/lib/rubros";
import { Ic } from "@/components/ic";
import { PublicacionesGrid, SolapasPublicaciones } from "@/components/publicaciones-grid";
import { UnirmeComunidad } from "@/components/unirme-comunidad";
import { FECHA_LANZAMIENTO, faltaParaLanzamiento } from "@/lib/lanzamiento";
import { getFarmaciasDeTurnoAhora, getNovedadesUruku, getPublicaciones } from "@/lib/data";
import { CarruselNovedades } from "@/components/carrusel-novedades";
import { getPromo, tarjetasPromo } from "@/components/tarjetas-promo";
import { NovedadUrukuCard } from "@/components/novedad-uruku-card";
import { RubrosDePublicaciones } from "@/components/rubros-publicaciones";
import { ciudadActual } from "@/lib/ciudad-server";

export const dynamic = "force-dynamic";

type Props = { searchParams?: Record<string, string | string[] | undefined> };

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const { ciudad, elegida } = await ciudadActual();
  // Sin ciudad elegida no se nombra ninguna: un robot no manda cookies, así
  // que para Google la ciudad siempre era la de respaldo y el buscador
  // publicaba «Novedades de Bermejo» para todo el país.
  const n = elegida ? ciudad?.nombre ?? null : null;
  const en = n ? ` en ${n}` : "";
  // El rubro va en el título porque este link se comparte: lo que se ve en la
  // vista previa de WhatsApp es esto, y «Novedades de Bermejo» no dice de qué.
  const rubro = typeof searchParams?.rubro === "string" ? searchParams.rubro : null;
  if (rubro) {
    const items = await getPublicaciones("novedad", 1, ciudad?.slug, rubro);
    const nom = sinEmoji(items[0]?.rubro_nombre ?? rubro);
    return {
      title: `Novedades de ${nom}${en} — URUKU`,
      description: `Lo que publicaron hoy los comercios de ${nom}${en}, con foto, precio y el WhatsApp de cada local.`,
    };
  }
  return {
    title: n ? `Novedades de ${n} — URUKU` : "Novedades — URUKU",
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
  const conGuia = (ciudad?.slug ?? "bermejo") === "bermejo";
  const [todas, deUruku, promo, turnos] = await Promise.all([
    getPublicaciones("novedad", 60, ciudad?.slug),
    // Con un rubro elegido se mira lo de los comercios de ese rubro: las de URUKU no tienen rubro.
    rubro ? Promise.resolve([]) : getNovedadesUruku(ciudad?.id, 24),
    // Lo mismo que pasa el carrusel de la portada: servicios y destacados.
    rubro ? Promise.resolve(null) : getPromo(ciudad?.slug),
    rubro ? Promise.resolve(null) : getFarmaciasDeTurnoAhora(ciudad?.id),
  ]);
  const items = rubro ? todas.filter((p) => p.rubro_slug === rubro) : todas;
  const nomRubro = rubro ? (todas.find((p) => p.rubro_slug === rubro)?.rubro_nombre ?? rubro) : null;

  return (
    <UrukuShell showCatnav={false} activeNav="Novedades">
      <div className="uk-container uk-pub">
        <div className="uk-section-head">
          <h1><Ic n="novedades" s={24} /> Novedades {nomRubro ? `de ${sinEmoji(nomRubro)}` : `de ${nombre}`}</h1>
          <SolapasPublicaciones activa="novedades" />
        </div>
        <RubrosDePublicaciones items={todas} ruta="/novedades" activo={rubro} />
        <p className="uk-pub-sub">Lo que cuenta URUKU y lo que cuentan los comercios: mercadería nueva, cambios de horario, lo que está pasando hoy.</p>

        {/* Servicios y comercios destacados (los que tienen plan), en carrusel. */}
        {promo && (conGuia || promo.destacados.length + promo.productos.length + (turnos ?? []).length > 0) && (
          <section className="uk-nov-grupo" aria-labelledby="uk-nov-destacados">
            <h2 id="uk-nov-destacados"><Ic n="destacado" s={20} tono="marca" /> Destacados y servicios</h2>
            <CarruselNovedades>
              {tarjetasPromo({ promo, turnos, conGuia })}
            </CarruselNovedades>
          </section>
        )}

        {/* Lo de URUKU, arriba: es lo que la marca quiere que se vea primero. */}
        {deUruku.length > 0 && (
          <section className="uk-nov-grupo" aria-labelledby="uk-nov-uruku">
            <h2 id="uk-nov-uruku"><Ic n="novedades" s={20} tono="marca" /> De URUKU</h2>
            <div className="uk-offers">
              {deUruku.map((n) => <NovedadUrukuCard key={n.id} n={n} />)}
            </div>
          </section>
        )}
        {deUruku.length > 0 && items.length > 0 && (
          <h2 style={{ fontSize: 18, margin: "0 0 12px" }}>De los comercios</h2>
        )}

        <PublicacionesGrid
          items={items}
          vacio={deUruku.length > 0 ? (
            <div className="uk-empty">Los comercios todavía no publicaron novedades.</div>
          ) : faltaParaLanzamiento() ? (
            <div className="uk-lanzamiento">
              <span className="uk-lanzamiento-tag">Nuevo en URUKU</span>
              <h2>Las novedades empiezan {FECHA_LANZAMIENTO}</h2>
              <p>
                Desde ese día vas a ver acá, todos los días, lo que publican los comercios de {nombre}:
                la mercadería que llega, los cambios de horario, lo que está pasando. Directo del local a tu celular.
              </p>
              <div className="uk-lanzamiento-acciones">
                <Link href="/buscar?vista=mapa" className="uk-btn uk-btn-primary">Mientras tanto, ver los comercios</Link>
                <Link href="/autoregistro" className="uk-btn-ghost">¿Tenés un negocio? Sumalo a URUKU</Link>
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
