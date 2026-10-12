import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { UrukuShell } from "@/components/uruku-shell";
import { sinEmoji } from "@/lib/rubros";
import { Ic } from "@/components/ic";
import { WaLeadLink } from "@/components/wa-lead-link";
import { LeadLink } from "@/components/lead-link";
import { ReservaBarra } from "@/components/reserva-barra";
import { GuardarBoton } from "@/components/guardar-boton";
import { HorarioBadge } from "@/components/horario-badge";
import { EstrellaVerificado } from "@/components/estrella-verificado";
import { CompartirBoton } from "@/components/compartir-boton";
import QRCode from "qrcode";
import { getComercioBySlug, getOfertasComercio, getGaleriaComercio, nombreCiudadDe, getFuncionesDePlan, getPlanPublico } from "@/lib/data";
import { FichaGaleria } from "@/components/ficha-galeria";
import { GaleriaTienda } from "@/components/galeria-tienda";
import { VistaLogger } from "@/components/vista-logger";
import { VolverAResultados } from "@/components/volver-a-resultados";
import { MODALIDAD_LABEL } from "@/lib/types";
import { enlaceCanal, enlaceRed, urlHttp } from "@/lib/catalogo";
import {
  WhatsApp, Pin, Phone, Globe, Instagram, Facebook, TikTok,
} from "@/components/icons";

export const dynamic = "force-dynamic"; // el header (ciudad por cookie) es dinámico

/** El título y la vista previa de la ficha: es lo que se ve cuando alguien
 *  la comparte por WhatsApp o la encuentra en Google. Sin esto todas las
 *  fichas decían "URUKU — Comercios y ofertas en el mapa" y sin foto: un
 *  enlace compartido que no dice qué local es no se abre. */
export async function generateMetadata({ params }: { params: { slug: string } }): Promise<Metadata> {
  const c = await getComercioBySlug(params.slug);
  if (!c) return { title: "Comercio no encontrado — URUKU" };
  const ciudad = await nombreCiudadDe(c.ciudad_id);
  const que = c.subcategoria || sinEmoji(c.rubro_nombre) || "";
  const titulo = `${c.nombre.trim()}${que ? ` — ${que}` : ""} en ${ciudad} | URUKU`;
  const vende = (c.prod_obs_human || c.prod_det_ia || "").split(/[,;·]/).map((t) => t.trim()).filter(Boolean).slice(0, 6).join(", ");
  const descripcion = (c.descripcion?.trim() || (vende ? `Vende ${vende}.` : `${c.nombre.trim()} en el mapa de ${ciudad}.`))
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
  const ciudadNombre = await nombreCiudadDe(comercio.ciudad_id);
  // Un taxi, remis o chofer sin parada fija: no hay "cómo llegar", se lo llama.
  const sinParada = comercio.rubro_slug === "taxis" && !comercio.direccion && !comercio.lat;
  const responde = (comercio.contacto_ok ?? 0) >= 3 && (comercio.contacto_ok ?? 0) >= 2 * (comercio.contacto_no ?? 0);
  const noResponde = (comercio.contacto_no ?? 0) >= 5 && (comercio.contacto_ok ?? 0) === 0;
  // El QR de la ficha, el mismo que va en el volante y en la tarjeta de mesa.
  // En pantalla sirve para pasar la ficha de una compu a un celular sin
  // tipear, y para que el dueño la muestre desde su teléfono. Se genera acá,
  // en el servidor, por lo mismo que en el volante: la librería no viaja al
  // navegador.
  const urlFicha = `https://uruku.bo/comercios/${comercio.slug}`;
  const [feed, galeria, funcionesPlan, planPublico, qr] = await Promise.all([
    getOfertasComercio(comercio.id), getGaleriaComercio(comercio.id),
    // Las funciones del plan (decide si la ficha lleva el chatbot del local):
    // se leen junto con lo demás, no en serie.
    getFuncionesDePlan((comercio as { plan?: string | null }).plan),
    // La estrella «Verificado por URUKU» (plan pago al día o de cortesía). Si
    // la lectura falla, sin estrella.
    getPlanPublico(comercio.id),
    // Con `?ref=`: la vista que llegue por este QR queda marcada como tal
    // (0114), distinta de la que llega por el volante o la tarjeta de mesa.
    QRCode.toDataURL(`${urlFicha}?ref=ficha-${comercio.slug}`, { width: 240, margin: 1, errorCorrectionLevel: "M",
                                 color: { dark: "#0f2c33", light: "#ffffff" } }),
  ]);

  // Ofertas y novedades van en la vidriera de fotos, con su etiqueta y un
  // filtro por tipo (components/galeria-tienda.tsx). Los videos de TikTok no.
  const publicaciones = feed.filter((p) => p.tipo === "oferta" || p.tipo === "novedad");
  const vende = loQueVende(comercio.prod_obs_human || comercio.prod_det_ia);

  // Cada enlace pasa por `enlaceRed`: arma «@mitienda» como la dirección de la
  // red y descarta lo que no sea web. Antes iban tal cual al href, y un
  // `javascript:` cargado en «Sitio web» corría al tocarlo.
  const redes = [
    { label: "TikTok", href: enlaceRed("tiktok", comercio.tiktok_url), Icon: TikTok },
    { label: "Instagram", href: enlaceRed("instagram", comercio.instagram_url), Icon: Instagram },
    { label: "Facebook", href: enlaceRed("facebook", comercio.facebook_url), Icon: Facebook },
    { label: "Sitio web", href: enlaceRed("web", comercio.sitio_web), Icon: Globe },
  ].filter((r) => r.href) as { label: string; href: string; Icon: typeof TikTok }[];

  // «Lo que suma»: lo que el local cargó y hace que lo elijan. Todo opcional y
  // sin relleno: lo que falta no aparece, y sin nada no hay fila. Los enlaces
  // sólo si son web (http/https): un `href` suelto sería un botón roto.
  //
  // El canal y el catálogo llevan a otro lado bajo la marca URUKU: se muestran
  // sólo si alguien de URUKU respondió por ese comercio — verificado,
  // confiable, o cargado en la calle por un agente —. Un comercio recién
  // registrado solo no puede poner «Ver catálogo» apuntando a cualquier cosa
  // (la misma regla de confianza que las ofertas, AGENTS.md §4).
  const deConfianza = comercio.verificado === true || comercio.confiable === true || comercio.fuente === "campo";
  const canalHref = deConfianza ? enlaceCanal(comercio.canal_wa_url) : null;
  const catalogoHref = deConfianza ? urlHttp(comercio.catalogo_url) : null;
  const sellos = [
    comercio.tiene_pasero === true && { n: "pasero" as const, texto: "Tiene pasero" },
    comercio.envios_internacionales === true && { n: "envios" as const, texto: "Hace envíos" },
    comercio.tiene_factura === true && { n: "factura" as const, texto: "Da factura" },
    comercio.talles_especiales === true && { n: "ropa" as const, texto: "Talles especiales" },
  ].filter(Boolean) as { n: "pasero" | "envios" | "factura" | "ropa"; texto: string }[];
  const pedidoMinimo = (comercio.pedido_minimo ?? "").trim();

  const mapsHref =
    urlHttp(comercio.como_llegar) ??
    (comercio.lat && comercio.lng
      ? `https://www.google.com/maps/search/?api=1&query=${comercio.lat},${comercio.lng}`
      : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(comercio.direccion ?? ciudadNombre)}`);

  // En la ficha de un local cuyo plan trae el chatbot, la ayuda es el
  // asistente de ESE local. En las demás, la de URUKU. Se decide por la
  // FUNCIÓN del plan (`asistente_24_7`), no por su nombre: antes estaba fijo
  // «empleado_ia» y el chatbot no se veía en ningún otro plan. El servidor es
  // el que decide de verdad (403 si el plan no lo incluye); acá sólo se elige
  // qué cara mostrar. Si la lectura del plan falla, queda sin chatbot, como
  // si el plan no lo tuviera: mejor no mostrarlo que mostrar uno que da 403.
  const conChatbot = funcionesPlan?.asistente_24_7 === true;
  return (
    <UrukuShell showCatnav={false}
                asistente={conChatbot ? { id: comercio.id, nombre: comercio.nombre } : undefined}>
      <VistaLogger comercioId={comercio.id} />

      <div className="uk-container uk-ficha">
        <VolverAResultados />

        {/* ===== Arriba: la galería y la tarjeta de contacto ===== */}
        <div className="uk-ficha-top">
          <FichaGaleria
            portada={comercio.portada_url ?? null}
            fotos={galeria.fotos}
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
              {/* Sólo la estrella. La tilde `verificado` es interna (la pone el
                  admin al chequear los datos) y no se muestra en público. */}
              {planPublico.estrella && <EstrellaVerificado s={20} />}
            </h1>

            <div className="uk-ficha-pills">
              {comercio.rubro_nombre && <span className="uk-pill green">{sinEmoji(comercio.rubro_nombre)}</span>}
              {responde && <span className="uk-pill green" title="Los que le escribieron dicen que contesta"><Ic n="si" s={13} /> Responde</span>}
              {noResponde && <span className="uk-pill" style={{ color: "#b45309" }} title="Los que le escribieron dicen que no contestó">Últimamente no contesta</span>}
              {comercio.modalidad && (
                <span className="uk-pill blue">{MODALIDAD_LABEL[comercio.modalidad] ?? comercio.modalidad}</span>
              )}
              <HorarioBadge horario={comercio.horario} estimado={comercio.horario_estimado} />
            </div>

            {comercio.descripcion && <p className="uk-ficha-desc">{comercio.descripcion}</p>}

            {/* Lo que vende, en fichas. Es lo que más se mira y muchos locales
                están cargados sólo con esto. */}
            {vende.length > 0 && (
              <div className="uk-ficha-vende">
                {vende.map((v) => <span key={v}><Ic n="si" s={13} /> {v}</span>)}
              </div>
            )}

            {/* LO QUE SUMA. Entre lo que vende y el botón de WhatsApp: es lo que
                decide ir a ESTE local y se tiene que ver sin bajar. Los que abren
                algo son botones; los que son sólo un dato, sellos. */}
            {(canalHref || catalogoHref || sellos.length > 0) && (
              <div className="uk-suma" role="group" aria-label="Lo que suma este negocio">
                <span className="uk-suma-tit">Lo que suma</span>
                {(canalHref || catalogoHref) && (
                  <div className="uk-suma-botones">
                    {canalHref && (
                      <a className="uk-suma-btn" href={canalHref} target="_blank" rel="noopener">
                        <Ic n="whatsapp" s={18} /> Canal de WhatsApp
                      </a>
                    )}
                    {catalogoHref && (
                      <a className="uk-suma-btn" href={catalogoHref} target="_blank" rel="noopener">
                        <Ic n="catalogo" s={18} /> Ver catálogo
                      </a>
                    )}
                  </div>
                )}
                {sellos.length > 0 && (
                  <ul className="uk-suma-sellos">
                    {sellos.map((s) => <li key={s.n}><Ic n={s.n} s={17} /> {s.texto}</li>)}
                  </ul>
                )}
              </div>
            )}

            {comercio.whatsapp ? (
              <WaLeadLink className="uk-ficha-wa" comercioId={comercio.id} whatsapp={comercio.whatsapp} nombre={comercio.nombre}
                          mensaje={`Hola ${comercio.nombre}, te contacto desde URUKU`}>
                <WhatsApp style={{ width: 20, height: 20 }} />
                <span>WhatsApp<small>+{comercio.whatsapp}</small></span>
              </WaLeadLink>
            ) : comercio.telefono ? (
              <a className="uk-ficha-wa" href={`tel:${comercio.telefono.replace(/[^\d+]/g, "")}`}>
                <Phone style={{ width: 20, height: 20 }} />
                <span>Llamar<small>{comercio.telefono}</small></span>
              </a>
            ) : (
              /* SIN CONTACTO: decirlo. Son 1.115 de 1.253, y acá no había
                 nada — ni un botón ni una línea. El comprador no sabía si el
                 local no tiene WhatsApp o si URUKU no lo cargó, que son dos
                 cosas muy distintas para quien está por cruzar el puente. */
              <div className="uk-ficha-sincontacto">
                <b>Este local no tiene WhatsApp cargado</b>
                <span>Hay que ir hasta el local. Fijate cómo llegar acá abajo.</span>
              </div>
            )}

            <div className="uk-ficha-acciones">
              {!sinParada && (
                <LeadLink className="uk-btn-ghost" href={mapsHref} tipo="mapa" comercioId={comercio.id}>
                  <Pin style={{ width: 16, height: 16 }} /> Cómo llegar
                </LeadLink>
              )}
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

        {/* ===== Las fotos del local, como una tienda: a todo el ancho ===== */}
        <GaleriaTienda fotos={galeria.fotos} videos={galeria.videos} publicaciones={publicaciones}
                       nombre={comercio.nombre} comercioId={comercio.id} comercioWhatsapp={comercio.whatsapp ?? null} />

        {/* Sin ofertas ni novedades el comercio igual sirve —tiene teléfono,
            dirección y lo que vende—. Se dice por qué no hay, sin disimular. */}
        {publicaciones.length === 0 && (
          <section className="uk-ficha-sec uk-ficha-vacio">
            <p>
              Este negocio todavía no publicó ofertas en URUKU. Escribile por WhatsApp
              y consultale por precios y disponibilidad.
            </p>
          </section>
        )}

        {/* Los datos del negocio, a todo el ancho: las ofertas y novedades, que
            iban en la columna de al lado, ahora están en la vidriera. */}
        <div className="uk-ficha-body solo">

          <aside className="uk-ficha-side">
            <div className="uk-info-card" id="info">
              <h3>Información del negocio</h3>
              {comercio.horario && (
                <div className="uk-info-row">
                  <span className="ic"><Ic n="reloj" s={17} /></span>
                  <div>
                    <b>Horarios</b>{comercio.horario}{" "}
                    <HorarioBadge horario={comercio.horario} estimado={comercio.horario_estimado} />
                    {/* Decir de dónde salió el horario no es un detalle legal:
                        es la diferencia entre un dato y una promesa. */}
                    {comercio.horario_estimado && (
                      <small className="uk-info-nota">
                        Es el horario habitual de la zona. Confirmá antes de ir.
                      </small>
                    )}
                  </div>
                </div>
              )}
              {/* La calle sale del GPS (0127). Casi ningún comercio tiene
                  dirección tipeada, así que sin esto la ficha no dice dónde
                  queda en palabras — sólo un punto en el mapa. */}
              {!comercio.direccion && comercio.calle && (
                <div className="uk-info-row">
                  <span className="ic"><Ic n="ubicacion" s={17} /></span>
                  <div><b>Dónde queda</b>{comercio.calle}<small className="uk-info-nota">Sin altura: usá «Cómo llegar».</small></div>
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
                  <span className="ic"><Ic n="pagos" s={17} /></span>
                  <div><b>Acepta</b>{comercio.monedas_aceptadas.join(" · ")}</div>
                </div>
              )}
              {pedidoMinimo && (
                <div className="uk-info-row">
                  <span className="ic"><Ic n="comprar" s={17} /></span>
                  <div><b>Pedido mínimo</b>{pedidoMinimo}</div>
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

            {sinParada && (
              <div className="uk-info-card" id="ubicacion">
                <h3>Dónde atiende</h3>
                <p style={{ color: "var(--uk-ink-soft)", fontSize: 13, margin: 0 }}>
                  En toda la ciudad: no tiene parada fija, se pide por WhatsApp{comercio.telefono ? " o por teléfono" : ""}.
                </p>
              </div>
            )}
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

            {/* Acá estaba «Dejá un mensaje».
                Lo lee el comerciante desde /mi-comercio, y para eso tiene que
                tener cuenta y entrar. De 1.253 comercios activos, 138 tienen
                WhatsApp y muchísimos menos tienen cuenta: el formulario le
                pedía a un comprador que escribiera una consulta a un buzón que
                nadie iba a abrir. Un canal de contacto que no contesta es peor
                que no ofrecer ninguno — el comprador espera y no vuelve.

                Los mensajes que ya entraron siguen en la base y se leen desde
                /mi-comercio; lo que se saca es la promesa nueva. */}

            <div className="uk-info-card uk-ficha-reclamo">
              <h3>¿Hay algún dato incorrecto?</h3>
              <p>El horario, la dirección o el número pueden haber cambiado. Avisanos y lo corregimos.</p>
              <Link href={`/reclamos?comercio_id=${comercio.id}&nombre_comercio=${encodeURIComponent(comercio.nombre)}`}>
                Informar un problema →
              </Link>
            </div>
          </aside>
        </div>

        {/* Acá iba «Ref. XXXX», el código del comercio. Se sacó: con ese código
            cualquiera podía publicar a nombre del local por WhatsApp. El
            comerciante lo tiene en Mi comercio y en el volante. */}

        <ReservaBarra />
      </div>
    </UrukuShell>
  );
}
