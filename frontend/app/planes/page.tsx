import type { Metadata } from "next";
import Link from "next/link";
import { UrukuShell } from "@/components/uruku-shell";
import { getPlanes, type PlanPublico } from "@/lib/data";
import { waUruku } from "@/lib/contacto";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  // FUERA DEL SITIO (2/10). Los precios se deciden por ciudad: mostrar los de
  // Bermejo en Santa Cruz es prometer algo que todavía no está decidido. La
  // pantalla sigue existiendo —el trabajo no se tira— pero no se enlaza desde
  // ningún lado, no está en el sitemap y no se indexa.
  robots: { index: false, follow: false },
  title: "Planes para tu negocio — URUKU",
  description: "Aparecé en el mapa gratis. Después, tu negocio completo y un asistente que atiende a tus clientes.",
};

// El plan de entrada se reconoce por su clave: ya no hay precio para mirar.
const esGratis = (p: PlanPublico) => p.slug === "gratis";

/**
 * /planes — lo que se vende, leído de la base.
 *
 * Nombre, cuota, la frase que dice qué es y las viñetas salen de la tabla
 * `planes`, que se edita en Admin › Planes. Acá no hay ningún número escrito:
 * si cambia una cuota, cambia acá sin deploy.
 *
 * NO HAY PRECIOS DE PLANES. Se decide por ciudad y hablando con el comerciante,
 * así que donde iría el precio hay una forma de consultarlo (el WhatsApp de
 * URUKU). Lo único en plata que se muestra es la publicación extra: es lo que
 * el comerciante necesita saber para que la cuota no lo sorprenda.
 */
export default async function PlanesPage() {
  const planes = await getPlanes();
  const destacado = planes.find((p) => p.slug === "pro") ?? planes[Math.min(2, planes.length - 1)];

  return (
    <UrukuShell showCatnav={false}>
      <div className="uk-container uk-planes">
        <h1>Planes para tu negocio</h1>
        <p className="uk-planes-sub">
          Aparecer en el mapa es gratis. Cuando quieras más —tu negocio completo, un chatbot que
          atienda por vos— elegís hasta dónde.
        </p>

        <div className="uk-planes-grid">
          {planes.map((p) => (
            <article key={p.slug} className={`uk-plan${p.slug === destacado?.slug ? " uk-plan-destacado" : ""}`}>
              <header>
                <h2>{p.nombre}</h2>
                <div className="uk-plan-precio">
                  {esGratis(p)
                    ? <b>Gratis</b>
                    : <a href={waUruku(`Hola, quiero consultar el precio del plan ${p.nombre} de URUKU`)} target="_blank" rel="noopener"><b>Consultá el precio</b></a>}
                </div>
                {p.descripcion && <p className="uk-plan-desc">{p.descripcion}</p>}
              </header>
              <ul>
                {p.incluye.map((linea) => <li key={linea}>{linea}</li>)}
                <li className="uk-plan-cuota">
                  {p.publicaciones_mes == null
                    ? "Publicaciones sin límite"
                    : esGratis(p)
                      // El gratis no tiene cuota mensual que contar: cada foto se paga.
                      ? `Podés publicar fotos a Bs ${p.precio_publicacion_extra} cada una`
                      : `Hasta ${p.publicaciones_mes} publicaciones por mes`}
                  {!esGratis(p) && p.permite_extras && p.publicaciones_mes != null && p.precio_publicacion_extra > 0
                    ? ` · la extra, Bs ${p.precio_publicacion_extra}`
                    : ""}
                </li>
              </ul>
              {esGratis(p)
                ? <Link href="/autoregistro?modo=registro" className="uk-btn uk-btn-primary">Registrar mi negocio gratis</Link>
                : <Link href={`/mi-comercio?plan=${p.slug}`} className={p.slug === destacado?.slug ? "uk-btn uk-btn-primary" : "uk-btn-ghost"}>Quiero {p.nombre}</Link>}
            </article>
          ))}
        </div>

        <p className="uk-planes-nota">
          Se paga por mes, por QR de Bolivia o de Argentina, o por transferencia, desde <Link href="/mi-comercio">Mi negocio</Link>.
          Sin comisión por venta: cobrás vos, como siempre. ¿Dudas? Preguntale a Dax.
        </p>
      </div>
    </UrukuShell>
  );
}
