import type { Metadata } from "next";
import Link from "next/link";
import { UrukuShell } from "@/components/uruku-shell";
import { Ic, IcRubro } from "@/components/ic";
import { JsonLd } from "@/components/json-ld";
import { Revisado } from "@/components/revisado";
import {
  getCiudadesReales, getCityCategoryPagesOrNull, getCotizaciones, getFeed, getFronteraEstado, getSaberLocalPorSeccion,
  type FronteraEstado, type SaberLocalPublico,
} from "@/lib/data";
import { getSaberRevisado } from "@/lib/saber-revisado";
import { formatoMonto, tasasDe } from "@/lib/cambio";
import { breadcrumbNode, categoryPath, faqPageNode, indexablePagesOfCity, jsonLdGraph } from "@/lib/seo";
import { esFresca, fechaLarga } from "@/lib/seo-paginas";
import { MARCA, SITE_URL } from "@/lib/marca";
import { WA_URUKU_TEXTO, waUruku } from "@/lib/contacto";
import { precioFmt } from "@/lib/types";
import { PrecioArs } from "@/components/precio-ars";
import { hasSupabase } from "@/lib/supabase";

/**
 * /comprar-en-bermejo — para quien viene de Aguas Blancas, Orán, Salta, Jujuy o
 * Tucumán (docs/visibilidad-buscadores-ia.md §3.8, tarea FE).
 *
 * Cada sección es una pregunta con la respuesta primero. El texto sale del saber
 * local VERIFICADO (el mismo de /guia y del asistente), los datos del día de la
 * base con su fecha, y nada se inventa: si una pregunta no está cargada, esa
 * sección no se dibuja. ISR (3600) con el marco fijo en Bermejo: no lee cookies.
 *
 * Marcado FAQPage: sólo las preguntas de la sección `comercios` (las demás se
 * marcan en /guia y /que-es-uruku; cada pregunta, en una sola página).
 */
export const revalidate = 3600;
// Estática con regeneración horaria. `force-static` es a propósito: sin ella Next la
// marca dinámica (el build detectó un `cookies()` que no se ve en este archivo ni en
// el marco con `fixedCity`) y se perdería el ISR; ninguna parte de esta página
// depende de la cookie de ciudad.
export const dynamic = "force-static";

const TITULO = "Comprar en Bermejo desde Argentina: qué conviene, cómo cruzar y cómo pagar";
const DESCRIPCION =
  "Si venís de Aguas Blancas, Orán, Salta o Jujuy: qué conviene comprar en Bermejo, cómo cruzar, qué documentos llevar, cuánto te dan por tus pesos y cómo pagar.";

export const metadata: Metadata = {
  title: TITULO,
  description: DESCRIPCION,
  alternates: { canonical: "/comprar-en-bermejo" },
  // El openGraph de una página reemplaza al del layout (no lo completa): se repite lo necesario.
  openGraph: {
    title: TITULO, description: DESCRIPCION, siteName: MARCA, type: "website",
    url: `${SITE_URL}/comprar-en-bermejo`, locale: "es_BO", alternateLocale: ["es_AR"],
    images: [{ url: "/og-image.png", width: 1200, height: 630 }],
  },
};

/** Los rubros que le importan a quien viene a comprar, en este orden; sólo salen los indexables. */
const RUBROS_COMPRA = [
  "ropa", "calzado", "lenceria", "electronica", "electrodomesticos", "celulares", "bazar", "jugueteria", "limpieza",
];

/** Las primeras `n` oraciones de una respuesta (la respuesta va primero; el detalle, en /guia). */
function resumen(texto: string, n = 2): string {
  const t = texto.replace(/\s+/g, " ").trim();
  const partes = t.split(/(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡])/);
  return partes.slice(0, n).join(" ");
}

function primera(items: SaberLocalPublico[] | undefined, re?: RegExp): SaberLocalPublico | null {
  if (!items?.length) return null;
  return (re && items.find((s) => re.test(s.pregunta))) || items[0] || null;
}

const ESTADO: Record<string, Record<string, string>> = {
  puente: { normal: "habilitado", demoras: "con demoras", cerrado: "cerrado" },
  chalanas: { operando: "cruzando", limitadas: "con restricciones", suspendidas: "suspendidas" },
};

function estadoPaso(f: FronteraEstado): string {
  const partes = [`Puente: ${ESTADO.puente[f.puente] ?? f.puente}`];
  if (f.chalanas !== "no_aplica") partes.push(`chalanas: ${ESTADO.chalanas[f.chalanas] ?? f.chalanas}`);
  if (f.rio === "crecido") partes.push("río crecido");
  return partes.join(" · ");
}

const ES_BUILD = process.env.NEXT_PHASE === "phase-production-build";

export default async function ComprarEnBermejoPage() {
  // ISR: una lectura fallida NO se guarda como «sin rubros» ni con las ciudades demo
  // (su `id` no es el de Bermejo): se lanza y Next conserva la versión anterior. En
  // el build no se lanza (no depende de la base): la página sale sin esos bloques.
  const ciudades = await getCiudadesReales();
  if (ciudades === null && hasSupabase && !ES_BUILD) throw new Error("/comprar-en-bermejo: falló la lectura de ciudades");
  const bermejo = (ciudades ?? []).find((c) => c.slug === "bermejo");
  const [saber, revisado, frontera, cotizaciones, feed, parLeidos] = await Promise.all([
    getSaberLocalPorSeccion(bermejo?.id), getSaberRevisado(bermejo?.id), getFronteraEstado(bermejo?.id),
    getCotizaciones(), getFeed(12, "bermejo"), getCityCategoryPagesOrNull(),
  ]);
  if (parLeidos === null && hasSupabase && !ES_BUILD) throw new Error("/comprar-en-bermejo: falló la lectura de los pares ciudad+rubro");
  const pares = parLeidos ?? [];

  // --- Preguntas de la sección `comercios` (las que se marcan acá) ---
  const comercios = saber.comercios ?? [];
  const conviene = comercios.find((s) => /conviene/i.test(s.pregunta)) ?? null;
  const pagos = comercios.find((s) => /moneda|pago|pagar/i.test(s.pregunta)) ?? null;
  const envios = comercios.find((s) => /env[ií]|mand|encomienda|orán|oran|salta|jujuy/i.test(s.pregunta) && s !== conviene) ?? null;
  const usadas = new Set([conviene, pagos, envios].filter((x): x is SaberLocalPublico => x !== null));
  const otras = comercios.filter((s) => !usadas.has(s));

  // --- Datos del día, con su fecha (§3.8: sólo se dice «hoy» si tiene < 36 h) ---
  const t = tasasDe(cotizaciones);
  const cotFresca = esFresca(t.actualizado_en);
  const cotFecha = fechaLarga(t.actualizado_en);
  const pasoFresco = esFresca(frontera?.actualizado_en);
  const pasoFecha = fechaLarga(frontera?.actualizado_en);

  const rubros = indexablePagesOfCity(pares, "bermejo")
    .filter((p) => RUBROS_COMPRA.includes(p.category_slug))
    .sort((a, b) => RUBROS_COMPRA.indexOf(a.category_slug) - RUBROS_COMPRA.indexOf(b.category_slug));

  const cruzo = primera(saber.frontera, /cruzo|cruzar/i);
  const docs = primera(saber.documentos);
  const aduana = primera(saber.aduana, /llevar de vuelta|sin pagar/i);
  const ofertas = feed.filter((f) => f.tipo === "oferta").slice(0, 4);

  const faq = comercios.map((s) => ({ pregunta: s.pregunta, respuesta: s.respuesta }));
  const datos = jsonLdGraph([
    breadcrumbNode([{ name: "URUKU", path: "/" }, { name: "Comprar en Bermejo desde Argentina" }]),
    faq.length > 0 ? faqPageNode(faq) : null,
  ]);

  return (
    <UrukuShell showCatnav={false} activeNav="Guía" fixedCity={bermejo}>
      <JsonLd data={datos} />
      <div className="uk-container uk-guia">
        <h1>Comprar en Bermejo desde Argentina</h1>
        <p className="uk-guia-sub">
          Para quien viene de Aguas Blancas, Orán, Salta o Jujuy: qué conviene comprar, cómo cruzar, qué documentos
          llevar, cuánto te dan por tus pesos y cómo pagar. Lo que cambia día a día lleva su fecha.
        </p>

        {/* 1. Qué conviene comprar */}
        <section className="uk-guia-sec" id="que-conviene">
          <h2><Ic n="comprar" s={22} /> {conviene?.pregunta ?? "¿Qué conviene comprar en Bermejo?"}</h2>
          <Revisado iso={revisado.comercios} />
          {conviene
            ? <p>{conviene.respuesta}</p>
            : <p>Los comercios de Bermejo están en el mapa y en el buscador, con lo que vende cada local y su WhatsApp.</p>}
          {rubros.length > 0 && (
            <div className="uk-guia-chips">
              {rubros.map((p) => (
                <Link key={p.category_slug} href={categoryPath(p.city_slug, p.category_slug)}>
                  <IcRubro slug={p.category_slug} s={16} /> {p.category_name} en Bermejo
                </Link>
              ))}
            </div>
          )}
        </section>

        {/* 2. Cómo cruzo */}
        <section className="uk-guia-sec" id="como-cruzo">
          <h2><Ic n="frontera" s={22} /> {cruzo?.pregunta ?? "¿Cómo cruzo desde Aguas Blancas?"}</h2>
          <Revisado iso={revisado.frontera} />
          {cruzo && <p>{resumen(cruzo.respuesta)}</p>}
          {frontera && pasoFecha && (
            <p className="uk-guia-nota">
              <Ic n="frontera" s={16} /> {estadoPaso(frontera)}.{" "}
              {pasoFresco ? `Dato del ${pasoFecha}.` : `Dato del ${pasoFecha}: confirmá antes de salir.`}
            </p>
          )}
          <p><Link href="/guia#frontera">El paso, los horarios y las chalanas, en la guía →</Link></p>
        </section>

        {/* 3. Documentos */}
        <section className="uk-guia-sec" id="documentos">
          <h2><Ic n="documentos" s={22} /> {docs?.pregunta ?? "¿Qué documentos necesito?"}</h2>
          <Revisado iso={revisado.documentos} />
          {docs && <p>{resumen(docs.respuesta)}</p>}
          <p><Link href="/guia#documentos">Todos los documentos, en la guía →</Link></p>
        </section>

        {/* 4. Cuánto me dan por mis pesos */}
        <section className="uk-guia-sec" id="cambio">
          <h2><Ic n="cambio" s={22} /> ¿Cuánto me dan por mis pesos?</h2>
          {t.ars_bob != null && cotFecha ? (
            <>
              <p>
                {cotFresca ? "Hoy, con la referencia de URUKU, " : `Con la referencia cargada el ${cotFecha}, `}
                1.000 pesos argentinos equivalen a <b>Bs {formatoMonto(t.ars_bob * 1000, "BOB")}</b>
                {t.usd_bob != null && <> y 1 dólar a <b>Bs {formatoMonto(t.usd_bob, "BOB")}</b></>}.
                {" "}La cuenta final depende de la casa de cambio: comparás con la que te ofrezcan.
              </p>
              <small className={cotFresca ? "" : "vieja"}>
                {cotFresca ? `Referencia actualizada el ${cotFecha}.` : `Referencia del ${cotFecha}: puede estar vieja, confirmá en el lugar.`}
              </small>
            </>
          ) : (
            <p>La referencia de cambio se está cargando. Mientras tanto, la calculadora te deja poner la cotización que te ofrezcan.</p>
          )}
          <p><Link href="/cambio">Calculadora y casas de cambio →</Link></p>
        </section>

        {/* 5. Cómo pago */}
        <section className="uk-guia-sec" id="pagos">
          <h2><Ic n="pagos" s={22} /> {pagos?.pregunta ?? "¿Cómo pago?"}</h2>
          <Revisado iso={revisado.comercios} />
          {pagos
            ? <p>{pagos.respuesta}</p>
            : <p>Cada comercio dice en su ficha qué monedas acepta. Lo más seguro es preguntárselo por WhatsApp antes de ir.</p>}
        </section>

        {/* 6. ¿Me lo mandan? (sólo si está cargada la pregunta) */}
        {envios && (
          <section className="uk-guia-sec" id="envios">
            <h2><Ic n="envios" s={22} /> {envios.pregunta}</h2>
            <Revisado iso={revisado.comercios} />
            <p>{envios.respuesta}</p>
          </section>
        )}

        {/* 7. Franquicia */}
        <section className="uk-guia-sec" id="aduana">
          <h2><Ic n="aduana" s={22} /> {aduana?.pregunta ?? "¿Cuánto puedo pasar sin pagar?"}</h2>
          <Revisado iso={revisado.aduana} />
          {aduana && <p>{resumen(aduana.respuesta)}</p>}
          <p><Link href="/guia#aduana">La franquicia y lo que no se puede pasar, en la guía →</Link></p>
        </section>

        {/* 8. Encargos y guardería */}
        <section className="uk-guia-sec" id="encargos">
          <h2><Ic n="encargo" s={22} /> Encargos y guardería de URUKU</h2>
          <p>
            URUKU puede comprar por encargo en comercios de Bermejo y guardarte las compras hasta que las retires,
            con garantía de custodia. No cruza mercadería. Para pedirlo, escribinos por WhatsApp al {WA_URUKU_TEXTO}.
          </p>
          <p>
            <a className="uk-btn uk-btn-primary" href={waUruku("Hola URUKU, quiero que retiren o hagan mis compras en Bermejo y me las guarden en la guardería")} target="_blank" rel="noopener">
              <Ic n="whatsapp" s={18} /> Escribir por WhatsApp
            </a>
          </p>
        </section>

        {/* Las demás preguntas de compras (las que se marcan como FAQPage y no tienen sección propia) */}
        {otras.length > 0 && (
          <section className="uk-guia-sec" id="mas-preguntas">
            <h2><Ic n="ayuda" s={22} /> Más preguntas sobre comprar</h2>
            {otras.map((s) => (
              <div key={s.id}>
                <h3>{s.pregunta}</h3>
                <p>{s.respuesta}</p>
              </div>
            ))}
          </section>
        )}

        {/* 9. Ofertas */}
        {ofertas.length > 0 && (
          <section className="uk-guia-sec" id="ofertas">
            <h2><Ic n="ofertas" s={22} /> Ofertas de hoy en Bermejo</h2>
            <div className="uk-offers">
              {ofertas.map((o) => (
                <Link key={o.id} href={`/comercios/${o.comercio_slug}`}
                  className={`uk-offer${o.imagen_url ? "" : " sin-foto"}`}
                  style={o.imagen_url ? { backgroundImage: `url('${o.imagen_url}')` } : undefined}>
                  <span className="uk-offer-tag">{o.zona_nombre || o.comercio_nombre}</span>
                  {!o.imagen_url && <span className="uk-offer-emoji"><IcRubro slug={o.rubro_slug} s={64} peso="fill" /></span>}
                  <div className="uk-offer-body">
                    <h3>{o.titulo}</h3>
                    <small>{o.comercio_nombre}</small>
                    {o.precio != null && <strong>{precioFmt(o.precio, o.moneda)}</strong>}
                    <PrecioArs precio={o.precio} moneda={o.moneda} />
                  </div>
                </Link>
              ))}
            </div>
            <p><Link href="/ofertas">Ver todas las ofertas →</Link></p>
          </section>
        )}

        <p className="uk-guia-pie">
          ¿Falta algo? <Link href="/guia">La guía completa</Link> · <Link href="/que-es-uruku">Qué es URUKU</Link>.
        </p>
      </div>
    </UrukuShell>
  );
}
