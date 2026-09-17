import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { UrukuShell } from "@/components/uruku-shell";
import { MensajeComercioForm } from "@/components/mensaje-comercio-form";
import { WaLeadLink } from "@/components/wa-lead-link";
import { LeadLink } from "@/components/lead-link";
import { ReservarBoton } from "@/components/reservar-boton";
import { ReservaBarra } from "@/components/reserva-barra";
import { GuardarBoton } from "@/components/guardar-boton";
import { HorarioBadge } from "@/components/horario-badge";
import { CompartirBoton } from "@/components/compartir-boton";
import QRCode from "qrcode";
import { getComercioBySlug, getOfertasComercio, getGaleriaComercio } from "@/lib/data";
import { FichaGaleria } from "@/components/ficha-galeria";
import { VistaLogger } from "@/components/vista-logger";
import { VolverAResultados } from "@/components/volver-a-resultados";
import { precioFmt, vencimientoFmt, contactoDeOferta, MODALIDAD_LABEL } from "@/lib/types";
import {
  WhatsApp, Verified, Pin, Phone, Globe, Instagram, Facebook, TikTok,
} from "@/components/icons";

export const dynamic = "force-dynamic"; // el header (ciudad por cookie) es dinámico

/** El título y la vista previa de la ficha: es lo que se ve cuando alguien
 *  la comparte por WhatsApp o la encuentra en Google. Sin esto todas las
 *  fichas decían "URUKU — Comercios y ofertas en el mapa" y sin foto: un
 *  enlace compartido que no dice qué local es no se abre. */
export async function generateMetadata({ params }: { params: { slug: string } }): Promise<Metadata> {
  const c = await getComercioBySlug(params.slug);
  if (!c) return { title: "Comercio no encontrado — URUKU" };
  const que = c.subcategoria || c.rubro_nombre?.replace(/^\S+\s/, "") || "";
  const titulo = `${c.nombre.trim()}${que ? ` — ${que}` : ""} en Bermejo | URUKU`;
  const vende = (c.prod_obs_human || c.prod_det_ia || "").split(/[,;·]/).map((t) => t.trim()).filter(Boolean).slice(0, 6).join(", ");
  const descripcion = (c.descripcion?.trim() || (vende ? `Vende ${vende}.` : `${c.nombre.trim()} en el mapa de Bermejo.`))
    + " Cómo llegar, WhatsApp y ofertas en URUKU.";
  const imagen = c.portada_url || c.logo_url || "https://uruku.bo/logouruku.png";
  return {
    title: titulo,
    description: descripcion.slice(0, 300),
    alternates: { canonical: `https://uruku.bo/comercios/${c.slug}` },
    openGraph: { title: titulo, description: descripcion.slice(0, 300), url: `https://uruku.bo/comercios/${c.slug}`,
                 siteName: "URUKU", type: "website", locale: "es_BO", images: [{ url: imagen }] },
    twitter: { card: "summary_large_image", title: titulo, description: descripcion.slice(0, 200), images: [imagen] },
  };
}

/** Lo que vende, partido en fichas. Viene como texto separado por comas —lo
 *  escribió el agente o lo leyó la IA de la vidriera— y en una sola línea larga
 *  no se lee. Cortado, contesta de un vistazo "¿tiene lo que busco?". */
function loQueVende(texto: string | null | undefined): string[] {
  return (texto ?? "")
    .split(/[,;·]/)
    .map((t) => t.trim())
    .filter((t) => t.length > 1)
    .slice(0, 12);
}

export default async function ComercioPage({ params }: { params: { slug: string } }) {
  const comercio = await getComercioBySlug(params.slug);
  // 404 de verdad (app/not-found.tsx): un slug viejo o mal copiado no es
  // una página que existe, y así lo entienden los buscadores y el navegador.
  if (!comercio) notFound();
  // El QR de la ficha, el mismo que va en el volante y en la tarjeta de mesa.
  // En pantalla sirve para pasar la ficha de una compu a un celular sin
  // tipear, y para que el dueño la muestre desde su teléfono. Se genera acá,
  // en el servidor, por lo mismo que en el volante: la librería no viaja al
  // navegador.
  const urlFicha = `https://uruku.bo/comercios/${comercio.slug}`;
  const [feed, galeria, qr] = await Promise.all([
    getOfertasComercio(comercio.id), getGaleriaComercio(comercio.id),
    // Con `?ref=`: la vista que llegue por este QR queda marcada como tal
    // (0114), distinta de la que llega por el volante o la tarjeta de mesa.
    QRCode.toDataURL(`${urlFicha}?ref=ficha-${comercio.slug}`, { width: 240, margin: 1, errorCorrectionLevel: "M",
                                 color: { dark: "#0f2c33", light: "#ffffff" } }),
  ]);

  // El feed del comercio trae los tres tipos mezclados. Separarlos es lo que
  // permite darle a cada uno su sección: una novedad no es una oferta —no tiene
  // precio ni vence— y mezclarlas hacía que ninguna se leyera como lo que es.
  const ofertas = feed.filter((p) => p.tipo === "oferta");
  const novedades = feed.filter((p) => p.tipo === "novedad");
  const vende = loQueVende(comercio.prod_obs_human || comercio.prod_det_ia);

  /** Devuelve null si no hay a quién escribirle: sin número, el botón sería
   *  un enlace roto con cara de funcionar. */
  const contacto = (p: (typeof feed)[number]) =>
    (p.contacto_whatsapp || comercio.whatsapp)
      ? contactoDeOferta({ ...p, comercio_whatsapp: comercio.whatsapp ?? "" })
      : null;

  const redes = [
    comercio.tiktok_url && { label: "TikTok", href: comercio.tiktok_url, Icon: TikTok },
    comercio.instagram_url && { label: "Instagram", href: comercio.instagram_url, Icon: Instagram },
    comercio.facebook_url && { label: "Facebook", href: comercio.facebook_url, Icon: Facebook },
    comercio.sitio_web && { label: "Sitio web", href: comercio.sitio_web, Icon: Globe },
  ].filter(Boolean) as { label: string; href: string; Icon: typeof TikTok }[];

  const mapsHref =
    comercio.como_llegar ??
    (comercio.lat && comercio.lng
      ? `https://www.google.com/maps/search/?api=1&query=${comercio.lat},${comercio.lng}`
      : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(comercio.direccion ?? "Bermejo")}`);

  // Las secciones que existen de verdad, para la barra de anclas. Se arma con
  // datos y no con una lista fija: una pestaña "Productos" que lleva a un hueco
  // es peor que no tenerla — enseña que el sitio está vacío justo cuando el
  // comprador estaba por escribir.
  const secciones = [
    { id: "info", label: "Información" },
    ofertas.length > 0 && { id: "ofertas", label: `Ofertas (${ofertas.length})` },
    novedades.length > 0 && { id: "novedades", label: "Novedades" },
    (comercio.direccion || comercio.lat) && { id: "ubicacion", label: "Ubicación" },
  ].filter(Boolean) as { id: string; label: string }[];

  // En la ficha de un local con el plan Empleado Digital, la ayuda es el
  // asistente de ESE local. En las demás, la de URUKU. El servidor es el que
  // decide de verdad (403 si el plan no lo incluye); acá sólo se elige qué
  // cara mostrar.
  return (
    <UrukuShell showCatnav={false}
                asistente={(comercio as { plan?: string | null }).plan === "empleado_ia"
                  ? { id: comercio.id, nombre: comercio.nombre } : undefined}>
      <VistaLogger comercioId={comercio.id} />

      <div className="uk-container uk-ficha">
        <VolverAResultados />

        {/* ===== Arriba: la galería y la tarjeta de contacto ===== */}
        <div className="uk-ficha-top">
          <FichaGaleria
            portada={comercio.portada_url ?? null}
            fotos={galeria.fotos}
            videos={galeria.videos}
            nombre={comercio.nombre}
            posicion={(comercio as { portada_pos?: number | null }).portada_pos ?? null}
          />

          {/* La tarjeta de contacto va ARRIBA y no al final de la página.
              Todo lo que hay acá existe para que alguien escriba o camine hasta
              el local; dejar el WhatsApp abajo de todo era pedirle que se gane
              el derecho a contactar leyendo primero. */}
          <aside className="uk-ficha-card">
            <h1>
              {comercio.nombre}
              {comercio.verificado && (
                <span className="uk-verif" title="Negocio verificado">
                  <Verified style={{ width: 20, height: 20 }} />
                </span>
              )}
            </h1>

            <div className="uk-ficha-pills">
              {comercio.rubro_nombre && <span className="uk-pill green">{comercio.rubro_nombre}</span>}
              {comercio.modalidad && (
                <span className="uk-pill blue">{MODALIDAD_LABEL[comercio.modalidad] ?? comercio.modalidad}</span>
              )}
              <HorarioBadge horario={comercio.horario} />
            </div>

            {comercio.descripcion && <p className="uk-ficha-desc">{comercio.descripcion}</p>}

            {/* Lo que vende, en fichas. Es lo que más se mira y muchos locales
                están cargados sólo con esto. */}
            {vende.length > 0 && (
              <div className="uk-ficha-vende">
                {vende.map((v) => <span key={v}>✓ {v}</span>)}
              </div>
            )}

            {comercio.whatsapp ? (
              <WaLeadLink className="uk-ficha-wa" comercioId={comercio.id} whatsapp={comercio.whatsapp}
                          mensaje={`Hola ${comercio.nombre}, te contacto desde URUKU`}>
                <WhatsApp style={{ width: 20, height: 20 }} />
                <span>WhatsApp<small>+{comercio.whatsapp}</small></span>
              </WaLeadLink>
            ) : comercio.telefono ? (
              <a className="uk-ficha-wa" href={`tel:${comercio.telefono.replace(/[^\d+]/g, "")}`}>
                <Phone style={{ width: 20, height: 20 }} />
                <span>Llamar<small>{comercio.telefono}</small></span>
              </a>
            ) : null}

            <div className="uk-ficha-acciones">
              <LeadLink className="uk-btn-ghost" href={mapsHref} tipo="mapa" comercioId={comercio.id}>
                <Pin style={{ width: 16, height: 16 }} /> Cómo llegar
              </LeadLink>
              {comercio.telefono && comercio.whatsapp && (
                <a className="uk-btn-ghost" href={`tel:${comercio.telefono.replace(/[^\d+]/g, "")}`}>
                  <Phone style={{ width: 16, height: 16 }} /> Llamar
                </a>
              )}
              <GuardarBoton comercioId={comercio.id} className="uk-btn-ghost" />
              <CompartirBoton titulo={comercio.nombre} texto={`${comercio.nombre} en URUKU`} className="uk-btn-ghost" />
            </div>

            <div className="uk-ficha-qr">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={qr} alt={`QR de ${comercio.nombre} en URUKU`} width={88} height={88} />
              <div>
                <b>El QR de este negocio</b>
                <span>Escaneado, abre esta ficha · {urlFicha.replace("https://", "")}</span>
              </div>
            </div>
          </aside>
        </div>

        {/* ===== Las secciones que hay, como anclas ===== */}
        {secciones.length > 1 && (
          <nav className="uk-ficha-tabs">
            {secciones.map((s) => <a key={s.id} href={`#${s.id}`}>{s.label}</a>)}
          </nav>
        )}

        <div className="uk-ficha-body">
          <main>
            {ofertas.length > 0 && (
              <section id="ofertas" className="uk-ficha-sec">
                <div className="uk-section-head">
                  <h2>🔥 Ofertas de {comercio.nombre}</h2>
                  <span style={{ color: "var(--uk-ink-soft)", fontSize: 13 }}>
                    {ofertas.length} publicada{ofertas.length === 1 ? "" : "s"} por el negocio
                  </span>
                </div>
                <div className="uk-product-grid">
                  {ofertas.map((p) => {
                    const wa = contacto(p);
                    return (
                      <article className="uk-product" key={p.id}>
                        {/* La foto es lo que decide en ropa, calzado y bazar, y es
                            lo único que SIEMPRE viene: el título puede faltar y el
                            precio es opcional a propósito. */}
                        {p.imagen_url && (
                          <div className="uk-product-img">
                            <img src={p.imagen_url} alt={p.titulo ?? ""} loading="lazy" decoding="async" />
                            {p.descuento_pct != null && (
                              <span className="uk-product-off">{p.descuento_pct}% OFF</span>
                            )}
                          </div>
                        )}
                        <h4>{p.titulo ?? "Oferta"}</h4>
                        {p.descripcion && <p className="uk-product-desc">{p.descripcion}</p>}
                        {/* Sin precio no decimos "consultar precio" y listo: el
                            precio lo pone el comerciante si quiere, y muchos acá
                            no pueden porque se les mueve con el cambio del día. */}
                        {p.precio != null && <div className="price">{precioFmt(p.precio, p.moneda)}</div>}
                        <ReservarBoton oferta={p} />
                        {p.contacto_es_uruku && <span className="uk-marca-uruku">URUKU</span>}
                        <div className="foot">
                          <span>{p.vence_el ? `Hasta el ${vencimientoFmt(p.vence_el)}` : comercio.nombre}</span>
                          {/* El lead se registra como contacto DEL COMERCIO aunque
                              lo reciba URUKU: es el número que hay que poder
                              mostrarle cuando se le ofrezca un plan. */}
                          {wa && (
                            <LeadLink className="wa-mini" comercioId={comercio.id} href={wa.href} tipo="whatsapp">
                              <WhatsApp style={{ width: 17, height: 17, color: "#fff" }} />
                            </LeadLink>
                          )}
                        </div>
                      </article>
                    );
                  })}
                </div>
              </section>
            )}

            {novedades.length > 0 && (
              <section id="novedades" className="uk-ficha-sec">
                <div className="uk-section-head"><h2>✨ Novedades</h2></div>
                <div className="uk-novedades">
                  {novedades.map((n) => (
                    <article key={n.id} className="uk-novedad">
                      {n.imagen_url && <img src={n.imagen_url} alt="" loading="lazy" decoding="async" />}
                      <div>
                        <b>{n.titulo ?? "Novedad"}</b>
                        {n.descripcion && <p>{n.descripcion}</p>}
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            )}

            {/* Sin ofertas ni novedades el comercio igual sirve —tiene teléfono,
                dirección y lo que vende— pero la columna quedaría en blanco al
                lado de una barra llena. Se dice por qué, sin disimular. */}
            {ofertas.length === 0 && novedades.length === 0 && (
              <section className="uk-ficha-sec uk-ficha-vacio">
                <p>
                  Este negocio todavía no publicó ofertas en URUKU. Escribile por WhatsApp
                  y consultale por precios y disponibilidad.
                </p>
              </section>
            )}
          </main>

          <aside className="uk-ficha-side">
            <div className="uk-info-card" id="info">
              <h3>Información del negocio</h3>
              {comercio.horario && (
                <div className="uk-info-row">
                  <span className="ic" aria-hidden>🕐</span>
                  <div><b>Horarios</b>{comercio.horario} <HorarioBadge horario={comercio.horario} /></div>
                </div>
              )}
              {comercio.whatsapp && (
                <div className="uk-info-row">
                  <span className="ic"><WhatsApp style={{ width: 17, height: 17 }} /></span>
                  <div><b>WhatsApp</b>+{comercio.whatsapp}</div>
                </div>
              )}
              {comercio.telefono && (
                <div className="uk-info-row">
                  <span className="ic"><Phone style={{ width: 17, height: 17 }} /></span>
                  <div><b>Teléfono</b><a href={`tel:${comercio.telefono.replace(/[^\d+]/g, "")}`}>{comercio.telefono}</a></div>
                </div>
              )}
              {comercio.direccion && (
                <div className="uk-info-row">
                  <span className="ic"><Pin style={{ width: 17, height: 17 }} /></span>
                  <div><b>Dirección</b>{comercio.direccion}</div>
                </div>
              )}
              {/* Sólo si el comercio lo cargó. "Formas de pago: efectivo" puesto
                  por defecto no es un dato, es un supuesto con cara de dato. */}
              {comercio.monedas_aceptadas && comercio.monedas_aceptadas.length > 0 && (
                <div className="uk-info-row">
                  <span className="ic" aria-hidden>💳</span>
                  <div><b>Acepta</b>{comercio.monedas_aceptadas.join(" · ")}</div>
                </div>
              )}
              {redes.length > 0 && redes.map((r) => (
                <a className="uk-info-row" key={r.label} href={r.href} target="_blank" rel="noopener"
                   style={{ color: "inherit" }}>
                  <span className="ic"><r.Icon style={{ width: 17, height: 17 }} /></span>
                  <div><b>{r.label}</b>{r.href.replace(/^https?:\/\//, "")}</div>
                </a>
              ))}
            </div>

            {(comercio.direccion || comercio.lat) && (
              <div className="uk-info-card" id="ubicacion">
                <h3>Ubicación</h3>
                {comercio.direccion && (
                  <p style={{ color: "var(--uk-ink-soft)", fontSize: 13, margin: "0 0 10px" }}>
                    {comercio.direccion}
                  </p>
                )}
                <LeadLink className="uk-btn-wa" href={mapsHref} tipo="mapa" comercioId={comercio.id}>
                  <Pin style={{ width: 16, height: 16 }} /> Cómo llegar
                </LeadLink>
              </div>
            )}

            <MensajeComercioForm comercioId={comercio.id} nombre={comercio.nombre} />

            <div className="uk-info-card uk-ficha-reclamo">
              <h3>¿Hay algún dato incorrecto?</h3>
              <p>El horario, la dirección o el número pueden haber cambiado. Avisanos y lo corregimos.</p>
              <Link href={`/reclamos?comercio_id=${comercio.id}&nombre_comercio=${encodeURIComponent(comercio.nombre)}`}>
                Informar un problema →
              </Link>
            </div>
          </aside>
        </div>

        <ReservaBarra />
      </div>
    </UrukuShell>
  );
}
