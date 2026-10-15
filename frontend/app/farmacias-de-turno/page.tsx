import type { Metadata } from "next";
import Link from "next/link";
import { cache } from "react";
import { UrukuShell } from "@/components/uruku-shell";
import { Ic } from "@/components/ic";
import { MapaFarmaciasTurno, type PinFarmacia } from "@/components/mapa-farmacias-turno";
import { ciudadActual } from "@/lib/ciudad-server";
import { getTurnosFarmacia } from "@/lib/data";
import { comoLlegarHref } from "@/lib/types";
import {
  etiquetaHasta, fechaLarga, horaBolivia, listaNombres, nombreCorto, proximosPorDia, rangoTurnos, telHref, turnosAhora,
} from "@/lib/turnos-farmacia";

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
  const vigentes = turnos ? turnosAhora(turnos, ahora) : [];
  const nombres = vigentes.map((t) => t.comercios?.nombre ?? "").filter(Boolean);
  const titulo = nombres.length
    ? `Farmacias de turno hoy en ${n}: ${listaNombres(nombres.map(nombreCorto))}`
    : `Farmacias de turno en ${n}`;
  const descripcion = nombres.length
    ? `De turno ahora en ${n}: ${listaNombres(nombres)}. Atienden las 24 horas, ${etiquetaHasta(vigentes[0].fin, ahora)}. Teléfono, dirección y cómo llegar.`
    : `Qué farmacia está de turno hoy en ${n}, con teléfono, dirección, cómo llegar y los turnos de los próximos días.`;
  const url = "https://uruku.bo/farmacias-de-turno";
  return {
    title: titulo,
    description: descripcion,
    alternates: { canonical: url },
    openGraph: { title: titulo, description: descripcion, url, siteName: "URUKU", type: "website", locale: "es_BO",
                 images: [{ url: "/og-image.png", width: 1200, height: 630 }] },
    twitter: { card: "summary_large_image", title: titulo, description: descripcion, images: ["/og-image.png"] },
  };
}

export default async function FarmaciasDeTurnoPage() {
  const { ciudad, ahora, turnos } = await cargar();
  const nombre = ciudad?.nombre ?? "Bermejo";
  const vigentes = turnos ? turnosAhora(turnos, ahora) : [];
  const dias = turnos ? proximosPorDia(turnos, ahora, 7) : [];
  const linkBuscar = "/buscar?rubro=farmacia&vista=mapa";

  const pines: PinFarmacia[] = vigentes.flatMap((t) => {
    const f = t.comercios;
    if (!f || f.lat == null || f.lng == null) return [];
    return [{ id: f.id, nombre: f.nombre, slug: f.slug, direccion: f.direccion, telefono: f.telefono, lat: f.lat, lng: f.lng, hasta: etiquetaHasta(t.fin, ahora) }];
  });

  return (
    <UrukuShell showCatnav={false}>
      <div className="uk-container uk-turno">
        <h1>Farmacias de turno en {nombre}</h1>
        <p className="uk-turno-sub">
          Las que atienden las 24 horas hoy, con su teléfono y cómo llegar, y quién sigue en los próximos días.
        </p>

        {/* ERROR: no se pudo leer. Se dice, no se muestra un «no hay turnos» que mentiría. */}
        {turnos === null && (
          <div className="uk-turno-aviso error" role="alert">
            <Ic n="aviso" s={20} />
            <span>No pudimos leer el rol de turnos ahora. Probá de nuevo en unos minutos, o mirá las <Link href={linkBuscar}>farmacias en el mapa</Link>.</span>
          </div>
        )}

        {/* VACÍO: la ciudad no tiene turnos cargados. */}
        {turnos !== null && turnos.length === 0 && (
          <div className="uk-turno-aviso" role="status">
            <Ic n="dato" s={20} />
            <span>Todavía no cargamos el rol de turnos de {nombre}. Mientras tanto, mirá las <Link href={linkBuscar}>farmacias en el mapa</Link>.</span>
          </div>
        )}

        {turnos !== null && turnos.length > 0 && (
          <>
            <h2><Ic n="turno_farmacia" s={24} tono="marca" /> De turno ahora</h2>
            {vigentes.length === 0 ? (
              <div className="uk-turno-aviso" role="status">
                <Ic n="dato" s={20} />
                <span>En este momento no hay una farmacia de turno cargada. Mirá los próximos turnos más abajo.</span>
              </div>
            ) : (
              <div className="uk-turno-grid">
                {vigentes.map((t) => {
                  const f = t.comercios;
                  if (!f) return null;
                  const tel = telHref(f.telefono);
                  return (
                    <article key={t.id} className="uk-turno-card">
                      <span className="uk-turno-sello">
                        <Ic n="turno_farmacia" s={18} peso="fill" />
                        De turno ahora · {etiquetaHasta(t.fin, ahora)} · atiende las 24 h
                      </span>
                      <h3><Link href={`/comercios/${f.slug}`}>{f.nombre}</Link></h3>
                      {f.direccion && <p className="uk-turno-dato"><Ic n="ubicacion" s={18} /> {f.direccion}</p>}
                      {f.telefono && <p className="uk-turno-dato"><Ic n="telefono" s={18} /> {f.telefono}</p>}
                      <div className="uk-turno-acciones">
                        {tel && <a className="uk-btn uk-btn-primary" href={tel}><Ic n="telefono" s={18} /> Llamar</a>}
                        <a className="uk-btn-ghost" href={comoLlegarHref(f)} target="_blank" rel="noopener noreferrer">
                          <Ic n="ubicacion" s={18} /> Cómo llegar
                        </a>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}

            {pines.length > 0 && (
              <>
                <h2><Ic n="mapa" s={24} tono="marca" /> En el mapa</h2>
                <MapaFarmaciasTurno pines={pines} ciudad={ciudad ?? null} />
              </>
            )}

            <h2><Ic n="calendario" s={24} tono="marca" /> Próximos 7 días</h2>
            {dias.length === 0 ? (
              <div className="uk-turno-aviso" role="status">
                <Ic n="dato" s={20} />
                <span>No hay turnos cargados para los próximos días.</span>
              </div>
            ) : (
              <ul className="uk-turno-dias">
                {dias.map((d) => (
                  <li key={d.fecha}>
                    <span className="uk-turno-dia">
                      <b>{fechaLarga(d.fecha, ahora)}</b>
                      <small>desde las {horaBolivia(d.turnos[0].inicio)}, 24 h</small>
                    </span>
                    <span className="farmacias">
                      {d.turnos.map((t) => (
                        <Link key={t.id} href={`/comercios/${t.comercios?.slug ?? ""}`}>
                          <Ic n="turno_farmacia" s={16} tono="marca" /> {t.comercios?.nombre}
                        </Link>
                      ))}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}

        <p className="uk-turno-norma">
          <Ic n="dato" s={16} /> El turno va de 08:00 a 08:00 del día siguiente (DS 25235, art. 74), con atención continua.
        </p>
      </div>
    </UrukuShell>
  );
}
