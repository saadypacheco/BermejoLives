import type { Metadata } from "next";
import Link from "next/link";
import { UrukuShell } from "@/components/uruku-shell";
import {
  buscarComercios, getClima, getCotizacionHistorial, getCotizaciones, getFronteraEstado,
  getSaberLocalPorSeccion, getVideosPromo, RUBROS_SERVICIO, type FronteraEstado, type SaberLocalPublico,
} from "@/lib/data";
import { cambioFavorable, diasDesde, DIAS_VIEJA, formatoMonto, tasasDe } from "@/lib/cambio";
import { abiertoAhora, etiquetaHorario } from "@/lib/horario";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Guía para venir a Bermejo — URUKU",
  description: "Cómo está el paso hoy, documentos, aduana y franquicia, cambio, dónde comprar y a qué hora, transporte desde Orán y Salta, seguridad, chip e internet.",
};

/**
 * /guia — todo lo que necesita saber el que viene a Bermejo, en una página.
 *
 * Lo que es TEXTO sale del saber local por sección (Admin › Ayuda): es la
 * misma tabla que contesta el asistente, así que la guía y el chat nunca
 * dicen cosas distintas. Lo que es DATO DE HOY —el paso, el clima, el
 * cambio, quién está abierto— sale de la base en el momento.
 */
const SECCION: Record<string, { titulo: string; icono: string }> = {
  frontera: { titulo: "Cruzar", icono: "🌉" },
  documentos: { titulo: "Documentos", icono: "🪪" },
  aduana: { titulo: "Aduana: qué podés pasar", icono: "🛃" },
  comercios: { titulo: "Comprar: horarios, pagos, envíos", icono: "🛍️" },
  transporte: { titulo: "Cómo llegar: Orán, Salta, Tarija", icono: "🚌" },
  seguridad: { titulo: "Seguridad y emergencias", icono: "🆘" },
  conectividad: { titulo: "Chip e internet", icono: "📶" },
};

const ESTADO: Record<string, Record<string, [string, "ok" | "ojo" | "mal"]>> = {
  puente: { normal: ["Puente: normal", "ok"], demoras: ["Puente: con demoras", "ojo"], cerrado: ["Puente: CERRADO", "mal"] },
  chalanas: { operando: ["Chalanas: cruzando", "ok"], suspendidas: ["Chalanas: suspendidas", "mal"] },
  rio: { normal: ["Río: normal", "ok"], crecido: ["Río: crecido", "ojo"] },
};

function Preguntas({ items }: { items: SaberLocalPublico[] }) {
  if (!items?.length) return <p className="uk-guia-vacio">Todavía no hay nada cargado acá. Preguntale al botón de Ayuda.</p>;
  return (
    <div className="uk-guia-preguntas">
      {items.map((s) => (
        <details key={s.id} open={items.length <= 2}>
          <summary>{s.pregunta}</summary>
          <p>{s.respuesta}</p>
        </details>
      ))}
    </div>
  );
}

export default async function GuiaPage() {
  const ahora = new Date();
  const [saber, frontera, clima, cotizaciones, hist, videos, comercios, ...servicios] = await Promise.all([
    getSaberLocalPorSeccion(), getFronteraEstado(), getClima(), getCotizaciones(), getCotizacionHistorial("ars_bob", 8),
    getVideosPromo(6), buscarComercios({}, 300, 0),
    // Los servicios de la ciudad, por rubro: lo mismo que abre cada chip.
    ...RUBROS_SERVICIO.map(([slug]) => buscarComercios({ rubro: slug }, 40, 0)),
  ]);
  const t = tasasDe(cotizaciones);
  const diasCot = diasDesde(t.actualizado_en);
  const favorable = cambioFavorable(hist);
  const abiertos = comercios
    .filter((c) => c.horario && abiertoAhora(c.horario, ahora).estado === "abierto")
    .slice(0, 12);
  const horasFrontera = frontera?.actualizado_en ? Math.floor((Date.now() - new Date(frontera.actualizado_en).getTime()) / 3600000) : null;
  // Sólo los que tienen el servicio de rubro PRINCIPAL: el filtro también
  // trae a los que lo tienen de secundario, y en la guía sobran.
  const porServicio = RUBROS_SERVICIO
    .map(([slug, titulo], i) => [titulo, slug, (servicios[i] ?? []).filter((c) => c.rubro_slug === slug)] as const)
    .filter(([, , items]) => items.length > 0);

  return (
    <UrukuShell showCatnav={false} activeNav="Guía">
      <div className="uk-container uk-guia">
        <h1>Para el que viene a Bermejo</h1>
        <p className="uk-guia-sub">
          Lo que hay que saber antes de cruzar y mientras estás acá. Lo de hoy —el paso, el clima, el cambio— se
          actualiza en el día. Y lo que no esté acá, preguntalo al botón de <b>Ayuda</b>.
        </p>

        {/* ---------- HOY ---------- */}
        <section className="uk-guia-hoy">
          <div className="uk-guia-card">
            <h2>🌉 La frontera hoy</h2>
            {frontera ? (
              <>
                <div className="uk-guia-estados">
                  {(["puente", "chalanas", "rio"] as const).map((k) => {
                    const [txt, nivel] = ESTADO[k][frontera[k]] ?? [`${k}: ${frontera[k]}`, "ojo"];
                    return <span key={k} className={`uk-guia-estado ${nivel}`}>{txt}</span>;
                  })}
                </div>
                {frontera.nota && <p className="uk-guia-nota">{frontera.nota}</p>}
                <small className={horasFrontera != null && horasFrontera >= 24 ? "vieja" : ""}>
                  {horasFrontera == null ? "Sin dato cargado todavía"
                    : horasFrontera < 1 ? "Dato de hace menos de una hora"
                    : horasFrontera < 24 ? `Dato de hace ${horasFrontera} h`
                    : `Dato de hace ${Math.floor(horasFrontera / 24)} días — confirmá antes de salir`}
                  {clima?.temp_c != null && <> · {clima.icono || "☀"} {Math.round(clima.temp_c)}°{clima.descripcion ? `, ${clima.descripcion}` : ""}</>}
                </small>
              </>
            ) : <p className="uk-guia-vacio">Sin dato del paso todavía.</p>}
          </div>

          <div className="uk-guia-card">
            <h2>💱 El cambio hoy</h2>
            {t.ars_bob != null ? (
              <>
                <div className="uk-guia-tasas">
                  <span>1.000 pesos = <b>Bs {formatoMonto(t.ars_bob * 1000, "BOB")}</b></span>
                  {t.usd_bob != null && <span>1 dólar = <b>Bs {formatoMonto(t.usd_bob, "BOB")}</b></span>}
                </div>
                {favorable && <p className={`uk-guia-fav ${favorable.nivel}`}>{favorable.texto}</p>}
                <small className={diasCot == null || diasCot > DIAS_VIEJA ? "vieja" : ""}>
                  {diasCot == null ? "Sin fecha" : diasCot === 0 ? "Cotización de hoy" : `Cotización de hace ${diasCot} día${diasCot === 1 ? "" : "s"}`}
                  {" · "}<Link href="/cambio">Calculadora y casas de cambio →</Link>
                </small>
              </>
            ) : <p className="uk-guia-vacio">Sin cotización cargada. <Link href="/cambio">Calculadora →</Link></p>}
          </div>
        </section>

        {/* ---------- SECCIONES DE TEXTO ---------- */}
        {(["frontera", "documentos", "aduana"] as const).map((k) => (
          <section key={k} className="uk-guia-sec" id={k}>
            <h2>{SECCION[k].icono} {SECCION[k].titulo}</h2>
            <Preguntas items={saber[k] ?? []} />
          </section>
        ))}

        {/* ---------- COMPRAR ---------- */}
        <section className="uk-guia-sec" id="comercios">
          <h2>{SECCION.comercios.icono} {SECCION.comercios.titulo}</h2>
          <div className="uk-guia-abiertos">
            <div className="uk-guia-abiertos-cab">
              <b>Abiertos ahora</b>
              <Link href="/buscar?vista=mapa">Ver el mapa →</Link>
            </div>
            {abiertos.length === 0
              ? <p className="uk-guia-vacio">Ningún local tiene horario cargado para esta hora. Preguntale al botón de Ayuda «¿qué hay abierto?» o mirá el mapa.</p>
              : (
                <ul>
                  {abiertos.map((c) => (
                    <li key={c.id}>
                      <Link href={`/comercios/${c.slug}`}><b>{c.nombre}</b>{c.subcategoria ? <span> · {c.subcategoria}</span> : null}</Link>
                      <em>{(etiquetaHorario(abiertoAhora(c.horario, ahora), ahora) ?? "").toLowerCase()}</em>
                    </li>
                  ))}
                </ul>
              )}
          </div>
          <Preguntas items={saber.comercios ?? []} />
        </section>

        {/* ---------- MAPA DE SERVICIOS ---------- */}
        <section className="uk-guia-sec" id="mapa">
          <h2>🗺️ En el mapa</h2>
          <div className="uk-guia-chips">
            <Link href="/buscar?rubro=farmacia&vista=mapa">💊 Farmacias</Link>
            <Link href="/buscar?rubro=cambio&vista=mapa">💱 Casas de cambio</Link>
            <Link href="/buscar?rubro=restaurantes&vista=mapa">🍽️ Dónde comer</Link>
            <Link href="/buscar?rubro=hospedaje&vista=mapa">🛏️ Dónde dormir</Link>
            <Link href="/buscar?rubro=celulares&vista=mapa">📱 Celulares y chips</Link>
            <Link href="/buscar?rubro=taxis&vista=mapa">🚕 Taxis</Link>
            <Link href="/buscar?rubro=banos&vista=mapa">🚻 Baños</Link>
            <Link href="/buscar?rubro=estacionamiento&vista=mapa">🅿️ Estacionamientos</Link>
            <Link href="/buscar?rubro=cajeros&vista=mapa">🏧 Cajeros</Link>
            <Link href="/buscar?rubro=wifi&vista=mapa">📶 Wifi</Link>
          </div>
          {porServicio.length > 0 ? (
            <div className="uk-guia-servicios">
              {porServicio.map(([titulo, slug, items]) => (
                <div key={slug}>
                  <b><Link href={`/buscar?rubro=${slug}&vista=mapa`}>{titulo}</Link></b>
                  <ul>
                    {items.slice(0, 12).map((c) => (
                      <li key={c.id}>
                        {c.nombre}{c.direccion ? ` · ${c.direccion}` : ""}
                        {c.lat != null && c.lng != null && (
                          <a href={`https://www.google.com/maps/search/?api=1&query=${c.lat},${c.lng}`} target="_blank" rel="noopener"> · cómo llegar</a>
                        )}
                      </li>
                    ))}
                    {items.length > 12 && <li><Link href={`/buscar?rubro=${slug}&vista=mapa`}>Ver todos en el mapa →</Link></li>}
                  </ul>
                </div>
              ))}
            </div>
          ) : (
            <p className="uk-guia-vacio">Baños, estacionamientos, cajeros y wifi se están cargando. Mientras tanto, preguntá en cualquier local: en Bermejo se ayuda.</p>
          )}
        </section>

        {(["transporte", "seguridad", "conectividad"] as const).map((k) => (
          <section key={k} className="uk-guia-sec" id={k}>
            <h2>{SECCION[k].icono} {SECCION[k].titulo}</h2>
            <Preguntas items={saber[k] ?? []} />
          </section>
        ))}

        {/* ---------- OFERTAS Y VIDEOS ---------- */}
        <section className="uk-guia-sec" id="ofertas">
          <h2>🏷️ Ofertas y videos</h2>
          <div className="uk-guia-chips">
            <Link href="/buscar?of=1" className="uk-btn uk-btn-primary">Ver las ofertas de hoy →</Link>
          </div>
          {videos.length > 0 && (
            <div className="uk-guia-videos">
              {videos.map((v) => (
                <a key={v.id} href={v.url} target="_blank" rel="noopener">▶ {v.titulo || "Video"}</a>
              ))}
            </div>
          )}
        </section>

        <p className="uk-guia-pie">
          ¿Falta algo? Preguntalo al botón de Ayuda: lo que no sepa queda anotado y lo agregamos acá.
        </p>
      </div>
    </UrukuShell>
  );
}
