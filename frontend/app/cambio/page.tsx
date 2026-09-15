import type { Metadata } from "next";
import Link from "next/link";
import { UrukuShell } from "@/components/uruku-shell";
import { Conversor } from "@/components/conversor";
import { buscarComercios, getCotizaciones } from "@/lib/data";
import { DIAS_VIEJA, diasDesde, formatoMonto, tasasDe } from "@/lib/cambio";

export const dynamic = "force-dynamic";

// El título es la pregunta que la gente le hace a Google desde Orán y Salta
// antes de cruzar. Que la conteste URUKU, con el mapa de dónde cambiar al
// lado, es media publicidad hecha.
export const metadata: Metadata = {
  title: "Cotización en Bermejo hoy: peso argentino, boliviano y dólar — URUKU",
  description: "Cuánto te dan por 1.000 pesos argentinos en Bermejo, el dólar en bolivianos, conversor y las casas de cambio en el mapa.",
};

/**
 * /cambio — la cotización del día, un conversor y las casas de cambio.
 *
 * La tasa es la que carga el equipo en /contenido, y eso obliga a una regla:
 * SIEMPRE se muestra de cuándo es. En la frontera cambia todos los días; una
 * cotización de hace una semana presentada como "hoy" hace que alguien cambie
 * mal y no vuelva. Pasados DIAS_VIEJA días, la página lo dice en voz alta.
 */
export default async function CambioPage() {
  const [cotizaciones, casas] = await Promise.all([
    getCotizaciones(),
    buscarComercios({ rubro: "cambio" }, 8, 0),
  ]);
  const t = tasasDe(cotizaciones);
  const dias = diasDesde(t.actualizado_en);
  const vieja = dias == null || dias > DIAS_VIEJA;
  const fecha = t.actualizado_en
    ? new Date(t.actualizado_en).toLocaleDateString("es-BO", { day: "numeric", month: "long", timeZone: "America/La_Paz" })
    : null;

  return (
    <UrukuShell showCatnav={false} activeNav="Cambio">
      <div className="uk-container uk-cambio">
        <h1>Cotización en Bermejo</h1>
        <p className={`uk-cambio-fecha${vieja ? " vieja" : ""}`}>
          {fecha ? `Actualizada el ${fecha}` : "Sin fecha de actualización"}
          {dias != null && dias >= 1 ? ` · hace ${dias} ${dias === 1 ? "día" : "días"}` : dias === 0 ? " · hoy" : ""}
          {vieja && " — puede estar desactualizada: compará en el lugar antes de cambiar."}
        </p>

        <div className="uk-cambio-tasas">
          {t.ars_bob != null && (
            <div className="uk-cambio-tasa">
              <span>1.000 pesos argentinos</span>
              <b>Bs {formatoMonto(t.ars_bob * 1000, "BOB")}</b>
            </div>
          )}
          {t.usd_bob != null && (
            <div className="uk-cambio-tasa">
              <span>1 dólar en bolivianos</span>
              <b>Bs {formatoMonto(t.usd_bob, "BOB")}</b>
            </div>
          )}
          {t.usd_ars != null && (
            <div className="uk-cambio-tasa">
              <span>1 dólar en pesos argentinos</span>
              <b>$ {formatoMonto(t.usd_ars, "ARS")}</b>
            </div>
          )}
        </div>

        <Conversor tasas={t} />

        <p className="uk-cambio-nota">
          Es la referencia del mercado de Bermejo, no una cotización oficial: cada casa de cambio y cada cambista
          tiene la suya, y cambia durante el día. Traer dólares suele rendir más que traer pesos.
        </p>

        <section className="uk-cambio-casas">
          <div className="uk-cambio-casas-cab">
            <h2>Dónde cambiar</h2>
            <Link href="/buscar?rubro=cambio&vista=mapa" className="uk-btn-ghost">Ver todas en el mapa →</Link>
          </div>
          {casas.length === 0 ? (
            <p className="uk-empty">Todavía no hay casas de cambio cargadas.</p>
          ) : (
            <ul>
              {casas.map((c) => (
                <li key={c.id}>
                  <Link href={`/comercios/${c.slug}`}><b>{c.nombre}</b>{c.direccion ? <span> · {c.direccion}</span> : null}</Link>
                </li>
              ))}
              {casas.length >= 8 && <li className="uk-cambio-mas"><Link href="/buscar?rubro=cambio">y más…</Link></li>}
            </ul>
          )}
        </section>
      </div>
    </UrukuShell>
  );
}
