"use client";

// «Fotos del local» como una tienda: fotos grandes en columnas que siguen hacia
// abajo (2 en el celular, 3 en la tableta, 4 en la compu), no una tira de
// miniaturas. Con topes de 50 a 300 fotos por plan, la tira obligaba a tocar
// cuadradito por cuadradito para ver la mercadería; acá se recorre como una
// vidriera, con el dedo hacia abajo.
//
// Las ofertas y novedades del local van en la MISMA vidriera, primero, con su
// etiqueta («Oferta» / «Novedad») y, si es oferta, el precio abajo como en
// cualquier tienda. Arriba, un botón por tipo filtra la vidriera; el botón de
// un tipo que el local no tiene no aparece. Antes iban en secciones aparte,
// debajo de las fotos, y había que bajar todo para encontrarlas.
//
// En la grilla va SIEMPRE la miniatura (300×400, 13-28 KB); la grande (100-200
// KB) baja recién al abrir la foto. Con `srcSet` el celular —pantalla de alta
// densidad— elegía la grande para cada cuadrito y la ficha tardaba en mostrar
// algo. Arranca con 10 y suma 10 más cuando el que mira se acerca al final,
// sin botón: como cualquier tienda, se sigue bajando. Tocar una la abre grande,
// con flechas (y el teclado) para pasar; una oferta abierta muestra además su
// precio, el WhatsApp y «Reservar».

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { GaleriaFoto, GaleriaVideo } from "@/lib/data";
import { contactoDeOferta, precioFmt, vencimientoFmt, type FeedItem } from "@/lib/types";
import { Ic } from "@/components/ic";
import { LeadLink } from "@/components/lead-link";
import { ReservarBoton } from "@/components/reservar-boton";
import { WhatsApp } from "@/components/icons";

const DE_A = 10;

type Filtro = "oferta" | "novedad" | null;
type Item =
  | { clase: "pub"; id: string; url: string | null; pub: FeedItem }
  | { clase: "foto"; id: string; url: string; thumb: string | null };

export function GaleriaTienda({ fotos, videos, publicaciones, nombre, comercioId, comercioWhatsapp }: {
  fotos: GaleriaFoto[];
  videos: GaleriaVideo[];
  /** Ofertas y novedades del local (las del feed; los videos de TikTok no). */
  publicaciones: FeedItem[];
  nombre: string;
  comercioId: string;
  comercioWhatsapp: string | null;
}) {
  const [cuantas, setCuantas] = useState(DE_A);
  const [filtro, setFiltro] = useState<Filtro>(null);
  const [abierta, setAbierta] = useState<number | null>(null);
  const [video, setVideo] = useState<string | null>(null);
  const seccion = useRef<HTMLElement>(null);
  const fin = useRef<HTMLDivElement>(null);

  const nOfertas = publicaciones.filter((p) => p.tipo === "oferta").length;
  const nNovedades = publicaciones.filter((p) => p.tipo === "novedad").length;

  const items = useMemo<Item[]>(() => {
    const pubs: Item[] = publicaciones
      .filter((p) => (p.tipo === "oferta" || p.tipo === "novedad") && (!filtro || p.tipo === filtro))
      .map((p) => ({ clase: "pub", id: `p-${p.id}`, url: p.imagen_url, pub: p }));
    if (filtro) return pubs;
    return [...pubs, ...fotos.map<Item>((f) => ({ clase: "foto", id: `f-${f.id}`, url: f.url, thumb: f.thumb_url ?? null }))];
  }, [publicaciones, fotos, filtro]);

  // El buscador y las páginas de Ofertas / Novedades mandan acá con
  // `#ofertas` o `#novedades`: se llega con la vidriera ya filtrada.
  useEffect(() => {
    const h = window.location.hash;
    const t: Filtro = h === "#ofertas" ? "oferta" : h === "#novedades" ? "novedad" : null;
    if (!t || (t === "oferta" ? nOfertas : nNovedades) === 0) return;
    setFiltro(t);
    seccion.current?.scrollIntoView({ block: "start" });
  }, [nOfertas, nNovedades]);

  // Sumar 10 más cuando el final de la grilla está a menos de ~una pantalla.
  const hayMas = cuantas < items.length;
  useEffect(() => {
    const el = fin.current;
    if (!el || !hayMas) return;
    const obs = new IntersectionObserver((entradas) => {
      if (entradas.some((e) => e.isIntersecting)) setCuantas((c) => c + DE_A);
    }, { rootMargin: "0px 0px 800px 0px" });
    obs.observe(el);
    return () => obs.disconnect();
  }, [hayMas, cuantas]);

  const mover = useCallback((paso: number) => {
    setAbierta((n) => (n === null ? n : (n + paso + items.length) % items.length));
  }, [items.length]);

  useEffect(() => {
    if (abierta === null) return;
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") setAbierta(null);
      else if (e.key === "ArrowRight") mover(1);
      else if (e.key === "ArrowLeft") mover(-1);
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [abierta, mover]);

  if (items.length === 0 && videos.length === 0 && !filtro) return null;
  const visibles = items.slice(0, cuantas);
  const quedan = items.length - visibles.length;
  const item = abierta !== null ? items[abierta] : null;

  const elegir = (t: Exclude<Filtro, null>) => {
    setFiltro((f) => (f === t ? null : t));
    setCuantas(DE_A);
  };

  return (
    <section id="fotos" ref={seccion} className="uk-tienda" aria-labelledby="uk-tienda-tit">
      <div className="uk-section-head">
        <h2 id="uk-tienda-tit"><Ic n="foto" s={22} /> Fotos del local</h2>
        {(nOfertas > 0 || nNovedades > 0) && (
          <div className="uk-tienda-filtros" role="group" aria-label="Filtrar">
            {nOfertas > 0 && (
              <button type="button" aria-pressed={filtro === "oferta"} onClick={() => elegir("oferta")}>
                <Ic n="ofertas" s={16} /> Ofertas ({nOfertas})
              </button>
            )}
            {nNovedades > 0 && (
              <button type="button" aria-pressed={filtro === "novedad"} onClick={() => elegir("novedad")}>
                <Ic n="novedades" s={16} /> Novedades ({nNovedades})
              </button>
            )}
          </div>
        )}
      </div>

      <ul className="uk-tienda-grid">
        {visibles.map((it, n) => (
          <li key={it.id}>
            <button type="button" onClick={() => setAbierta(n)}
                    aria-label={it.clase === "pub" ? `${etiqueta(it.pub)}: ${it.pub.titulo ?? nombre}` : `Ver la foto ${n + 1}`}>
              {it.url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={it.clase === "foto" ? (it.thumb || it.url) : it.url}
                  alt={it.clase === "pub" ? (it.pub.titulo ?? "") : `${nombre}, foto ${n + 1}`}
                  loading="lazy" decoding="async"
                />
              ) : (
                // Una novedad sin foto: el texto en el lugar de la imagen.
                <span className="uk-tienda-texto">
                  <Ic n={it.clase === "pub" && it.pub.tipo === "oferta" ? "ofertas" : "novedades"} s={30} />
                  {it.clase === "pub" ? (it.pub.titulo ?? it.pub.descripcion ?? etiqueta(it.pub)) : ""}
                </span>
              )}
              {it.clase === "pub" && (
                <span className={`uk-tienda-tag ${it.pub.tipo}`}>{etiqueta(it.pub)}</span>
              )}
              {it.clase === "pub" && it.pub.descuento_pct != null && (
                <span className="uk-tienda-off">{it.pub.descuento_pct}% OFF</span>
              )}
            </button>
            {/* Como en cualquier tienda: abajo de la foto, qué es y cuánto sale. */}
            {it.clase === "pub" && it.url && (it.pub.titulo || it.pub.precio != null) && (
              <div className="uk-tienda-pie">
                {it.pub.titulo && <span>{it.pub.titulo}</span>}
                {it.pub.precio != null && <b>{precioFmt(it.pub.precio, it.pub.moneda)}</b>}
              </div>
            )}
          </li>
        ))}
        {/* Los videos al final de la grilla, con su ícono de play. */}
        {quedan === 0 && !filtro && videos.map((v) => (
          <li key={v.id}>
            <button type="button" className="con-video" onClick={() => setVideo(v.url)} aria-label="Ver el video">
              <video src={v.url} preload="metadata" muted playsInline />
              <span><Ic n="video_play" s={40} /></span>
            </button>
          </li>
        ))}
      </ul>

      {/* El aviso para cargar más: invisible, al pie de la grilla. */}
      {quedan > 0 && <div ref={fin} className="uk-tienda-fin" aria-hidden />}

      {item && abierta !== null && (
        <div className={`gf-lightbox uk-tienda-visor${item.clase === "pub" ? " con-detalle" : ""}`} onClick={() => setAbierta(null)} role="dialog" aria-modal
             aria-label={`${abierta + 1} de ${items.length}`}>
          {item.url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={item.url} alt={item.clase === "pub" ? (item.pub.titulo ?? "") : `${nombre}, foto ${abierta + 1}`}
                 onClick={(e) => e.stopPropagation()} />
          ) : <span />}
          {item.clase === "pub" && (
            <DetallePub pub={item.pub} comercioId={comercioId} comercioWhatsapp={comercioWhatsapp} />
          )}
          {items.length > 1 && (
            <>
              <button type="button" className="uk-tienda-flecha izq" aria-label="Anterior"
                      onClick={(e) => { e.stopPropagation(); mover(-1); }}>
                <Ic n="volver" s={24} />
              </button>
              <button type="button" className="uk-tienda-flecha der" aria-label="Siguiente"
                      onClick={(e) => { e.stopPropagation(); mover(1); }}>
                <Ic n="seguir" s={24} />
              </button>
              {item.clase === "foto" && <span className="uk-tienda-cuenta">{abierta + 1} / {items.length}</span>}
            </>
          )}
          <button type="button" className="gf-close" aria-label="Cerrar"><Ic n="cerrar" s={18} /></button>
        </div>
      )}

      {video && (
        <div className="gf-lightbox" onClick={() => setVideo(null)} role="dialog" aria-modal>
          <video src={video} controls autoPlay playsInline onClick={(e) => e.stopPropagation()} />
          <button type="button" className="gf-close" aria-label="Cerrar"><Ic n="cerrar" s={18} /></button>
        </div>
      )}
    </section>
  );
}

function etiqueta(p: FeedItem) {
  return p.tipo === "oferta" ? "Oferta" : "Novedad";
}

/** Lo que traía la tarjeta de la oferta en la sección vieja: descripción,
 *  precio, hasta cuándo, «Reservar» y el WhatsApp. Sin número no hay botón:
 *  sería un enlace roto con cara de funcionar. */
function DetallePub({ pub, comercioId, comercioWhatsapp }: {
  pub: FeedItem; comercioId: string; comercioWhatsapp: string | null;
}) {
  const wa = (pub.contacto_whatsapp || comercioWhatsapp)
    ? contactoDeOferta({ ...pub, comercio_whatsapp: comercioWhatsapp ?? "" })
    : null;
  return (
    <div className="uk-tienda-detalle" onClick={(e) => e.stopPropagation()}>
      <span className={`uk-tienda-tag ${pub.tipo}`}>{etiqueta(pub)}</span>
      {pub.titulo && <b className="tit">{pub.titulo}</b>}
      {pub.descripcion && <p>{pub.descripcion}</p>}
      {pub.precio != null && <b className="precio">{precioFmt(pub.precio, pub.moneda)}</b>}
      {pub.vence_el && <small>Hasta el {vencimientoFmt(pub.vence_el)}</small>}
      {(pub.tipo === "oferta" || wa) && (
        <div className="acciones">
          {pub.tipo === "oferta" && <ReservarBoton oferta={pub} />}
          {/* El lead se registra como contacto DEL COMERCIO aunque lo reciba
              URUKU: es el número que hay que poder mostrarle cuando se le
              ofrezca un plan. */}
          {wa && (
            <LeadLink className="uk-btn-wa" comercioId={comercioId} href={wa.href} tipo="whatsapp">
              <WhatsApp style={{ width: 17, height: 17 }} /> Consultar
            </LeadLink>
          )}
        </div>
      )}
      {pub.contacto_es_uruku && <span className="uk-marca-uruku">URUKU</span>}
    </div>
  );
}
