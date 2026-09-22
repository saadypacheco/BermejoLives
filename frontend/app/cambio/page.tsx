import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { UrukuShell } from "@/components/uruku-shell";
import { ciudadActual } from "@/lib/ciudad-server";
import { CambioCalculadora } from "@/components/cambio-calculadora";
import { UnirmeComunidad } from "@/components/unirme-comunidad";
import { buscarComercios, getCotizaciones } from "@/lib/data";
import { DIAS_VIEJA, diasDesde, tasasDe } from "@/lib/cambio";

export const dynamic = "force-dynamic";

// El título es la pregunta que la gente le hace a Google desde Orán y Salta
// antes de cruzar. Que la conteste URUKU, con el mapa de dónde cambiar al
// lado, es media publicidad hecha.
export const metadata: Metadata = {
  title: "Cotización en Bermejo hoy: cuánto te dan por tus pesos — URUKU",
  description: "Calculá cuántos bolivianos recibís por tus pesos argentinos con la cotización que te ofrecen, cómo se hace la cuenta, y las casas de cambio en el mapa.",
};

/**
 * /cambio — la calculadora con la cotización que ingresa la persona, la
 * cuenta explicada, y las casas de cambio en el mapa.
 *
 * La referencia del sitio (tabla `cotizaciones`, cargada a mano) es el punto
 * de partida, y SIEMPRE se dice de cuándo es: en la frontera cambia todos
 * los días. Pasados DIAS_VIEJA días la página lo dice en voz alta. Pero la
 * cuenta que le sirve a alguien es con el número que le acaban de decir en
 * el mostrador, y por eso los valores se pueden cambiar.
 */
export default async function CambioPage() {
  const { ciudad } = await ciudadActual();
  // El conversor es el de una frontera: cuánto son los pesos (o reales, o
  // soles) del otro lado. En una ciudad que no es frontera no tiene sentido.
  if (ciudad && !ciudad.es_frontera) notFound();
  const [cotizaciones, casas] = await Promise.all([
    getCotizaciones(),
    buscarComercios({ rubro: "cambio" }, 60, 0),
  ]);
  const t = tasasDe(cotizaciones);
  const dias = diasDesde(t.actualizado_en);
  const fecha = t.actualizado_en
    ? new Date(t.actualizado_en).toLocaleDateString("es-BO", { day: "numeric", month: "long", timeZone: "America/La_Paz" })
    : null;

  return (
    <UrukuShell showCatnav={false} activeNav="Cambio">
      <div className="uk-container uk-cambio">
        <h1>Cotización en Bermejo</h1>
        <p className="uk-cambio-sub">
          Ingresá la cotización que te ofrece la casa de cambio y calculá fácil cuánto recibís.
          Las casas de cambio hacen la cuenta con un factor: <em>pesos × 0,0068</em>, por ejemplo.
        </p>
        <UnirmeComunidad variante="chico" />
        <CambioCalculadora
          referencia={{
            ars_1000_bs: t.ars_bob != null ? t.ars_bob * 1000 : null,
            usd_bs: t.usd_bob, usd_ars: t.usd_ars,
            fecha, vieja: dias == null || dias > DIAS_VIEJA,
          }}
          casas={casas}
        />
      </div>
    </UrukuShell>
  );
}
