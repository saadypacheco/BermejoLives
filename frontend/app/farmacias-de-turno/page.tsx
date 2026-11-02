import type { Metadata } from "next";
import { cache } from "react";
import { UrukuShell } from "@/components/uruku-shell";
import { FarmaciasTurnoVista, metaFarmaciasTurno } from "@/components/farmacias-turno-vista";
import { ciudadActual } from "@/lib/ciudad-server";
import { getTurnosFarmacia } from "@/lib/data";
import { rangoTurnos } from "@/lib/turnos-farmacia";

// Los turnos cambian a las 08:00 y a lo largo del día se leen igual: cinco
// minutos de caché alcanzan. (El marco del sitio lee la ciudad de una cookie,
// así que Next la sirve dinámica igual; la directiva queda para el día que el
// marco no dependa de la cookie. Igual que /novedades/uruku/[id].)
export const revalidate = 300;

/** Una sola lectura por pedido: la usan `generateMetadata` y la página. */
const cargar = cache(async () => {
  const { ciudad } = await ciudadActual();
  const ahora = new Date();
  const { desde, hasta } = rangoTurnos(ahora, 8);
  const turnos = await getTurnosFarmacia(ciudad?.id, desde, hasta);
  return { ciudad, ahora, turnos };
});

export async function generateMetadata(): Promise<Metadata> {
  const { ciudad, ahora, turnos } = await cargar();
  const n = ciudad?.nombre ?? "Bermejo";
  // La dirección que se indexa es la de la ciudad (/{ciudad}/farmacias-de-turno,
  // FJ de docs/visibilidad-buscadores-ia.md): esta es la misma pantalla, elegida
  // por cookie. Un robot no manda cookie, así que para él es la de Bermejo. Si
  // la ciudad no tiene turnos cargados, su página propia da 404: se apunta a la
  // de Bermejo en vez de a una dirección que no existe.
  const canonical = ciudad && turnos && turnos.length > 0
    ? `/${ciudad.slug}/farmacias-de-turno`
    : "/bermejo/farmacias-de-turno";
  return metaFarmaciasTurno(n, turnos, ahora, canonical);
}

export default async function FarmaciasDeTurnoPage() {
  const { ciudad, ahora, turnos } = await cargar();
  return (
    <UrukuShell showCatnav={false}>
      <FarmaciasTurnoVista ciudad={ciudad} turnos={turnos} ahora={ahora} />
    </UrukuShell>
  );
}
