import type { Metadata } from "next";
import Link from "next/link";
import { UrukuShell } from "@/components/uruku-shell";
import { getPlanes } from "@/lib/data";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Planes para tu negocio — URUKU",
  description: "Aparecé en el mapa gratis. Después, tu negocio digitalizado, tus ofertas en las redes de URUKU y un chatbot que atiende a tus clientes.",
};

function precio(n: number): string {
  return n === 0 ? "Gratis" : `Bs ${n.toLocaleString("es-BO")}`;
}

/**
 * /planes — lo que se vende, leído de la base.
 *
 * Nombre, precio, cuota, la frase que dice qué es y las viñetas salen de la
 * tabla `planes`, que se edita en Admin › Planes. Acá no hay ningún número
 * escrito: si cambia un precio, cambia acá sin deploy. Es la única forma de
 * que la página de venta y lo que el sistema cobra digan lo mismo.
 */
export default async function PlanesPage() {
  const planes = await getPlanes();
  const destacado = planes.find((p) => p.slug === "pro") ?? planes[Math.min(2, planes.length - 1)];

  return (
    <UrukuShell showCatnav={false}>
      <div className="uk-container uk-planes">
        <h1>Planes para tu negocio</h1>
        <p className="uk-planes-sub">
          Aparecer en el mapa es gratis. Cuando quieras más —tu negocio digitalizado, tus ofertas en las
          redes de URUKU, un chatbot que atienda por vos— elegís hasta dónde.
        </p>

        <div className="uk-planes-grid">
          {planes.map((p) => (
            <article key={p.slug} className={`uk-plan${p.slug === destacado?.slug ? " uk-plan-destacado" : ""}`}>
              <header>
                <h2>{p.nombre}</h2>
                <div className="uk-plan-precio">
                  <b>{precio(p.precio_mes)}</b>{p.precio_mes > 0 && <span>/mes</span>}
                </div>
                {p.descripcion && <p className="uk-plan-desc">{p.descripcion}</p>}
              </header>
              <ul>
                {p.incluye.map((linea) => <li key={linea}>{linea}</li>)}
                <li className="uk-plan-cuota">
                  {p.publicaciones_mes == null
                    ? "Publicaciones sin límite"
                    : p.precio_mes === 0
                      // El gratis no tiene cuota mensual que contar: cada foto se paga.
                      ? `Podés publicar fotos a Bs ${p.precio_publicacion_extra} cada una`
                      : `Hasta ${p.publicaciones_mes} publicaciones por mes`}
                  {p.precio_mes > 0 && p.permite_extras && p.publicaciones_mes != null && p.precio_publicacion_extra > 0
                    ? ` · la extra, Bs ${p.precio_publicacion_extra}`
                    : ""}
                </li>
              </ul>
              {p.precio_mes === 0
                ? <Link href="/autoregistro?modo=registro" className="uk-btn uk-btn-primary">Registrar mi negocio gratis</Link>
                : <Link href={`/mi-comercio?plan=${p.slug}`} className={p.slug === destacado?.slug ? "uk-btn uk-btn-primary" : "uk-btn-ghost"}>Quiero {p.nombre}</Link>}
            </article>
          ))}
        </div>

        <p className="uk-planes-nota">
          Se paga por mes, por QR de Bolivia o de Argentina, o por transferencia, desde <Link href="/mi-comercio">Mi negocio</Link>.
          Sin comisión por venta: cobrás vos, como siempre. ¿Dudas? Preguntale al botón de Ayuda.
        </p>
      </div>
    </UrukuShell>
  );
}
