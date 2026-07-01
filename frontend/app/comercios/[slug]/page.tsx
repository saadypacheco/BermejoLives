import Link from "next/link";
import { Nav } from "@/components/nav";
import { MensajeComercioForm } from "@/components/mensaje-comercio-form";
import { WaLeadLink } from "@/components/wa-lead-link";
import { getComercioBySlug, getProductos } from "@/lib/data";
import { precioFmt, MODALIDAD_LABEL } from "@/lib/types";
import {
  WhatsApp, Verified, Pin, Phone, Globe, Instagram, Facebook, TikTok, Arrow,
} from "@/components/icons";

export const revalidate = 60; // SSG + ISR para catálogo (lesson KB)

export default async function ComercioPage({ params }: { params: { slug: string } }) {
  const comercio = await getComercioBySlug(params.slug);
  if (!comercio) return <div className="wrap" style={{ padding: 80 }}>Comercio no encontrado.</div>;
  const productos = await getProductos(comercio.id);

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

  return (
    <>
      <Nav active="negocios" />

      <div className="profile-cover">
        {comercio.portada_url && <img src={comercio.portada_url} alt="Portada" />}
      </div>

      <div className="wrap">
        <div className="profile-head">
          {comercio.logo_url && <img className="profile-logo" src={comercio.logo_url} alt="Logo" />}
          <div className="profile-info">
            <h1>
              {comercio.nombre}
              {comercio.verificado && <span className="pverif" title="Negocio verificado"><Verified /></span>}
            </h1>
            <div className="meta">
              {comercio.direccion && <span><Pin />{comercio.direccion}</span>}
              <span style={{ color: "var(--amber)" }}>★ {comercio.rating}</span>
              {comercio.modalidad && (
                <span className="pill" style={{ color: "var(--blue-soft)" }}>{MODALIDAD_LABEL[comercio.modalidad] ?? comercio.modalidad}</span>
              )}
            </div>
          </div>
          <div className="profile-cta">
            <WaLeadLink className="btn btn-wa" comercioId={comercio.id} whatsapp={comercio.whatsapp} mensaje={`Hola ${comercio.nombre}, te contacto desde Encontralo`}>
              <WhatsApp style={{ width: 18, height: 18 }} /> WhatsApp
            </WaLeadLink>
            <a className="btn btn-ghost" href={mapsHref} target="_blank" rel="noopener"><Pin /> Cómo llegar</a>
          </div>
        </div>

        {comercio.descripcion && (
          <p style={{ color: "var(--txt-2)", maxWidth: 640, margin: "18px 0 0" }}>{comercio.descripcion}</p>
        )}

        {/* INFO: todos los datos del vendedor */}
        <div className="info-grid" style={{ marginTop: 30 }}>
          <div className="info-card glass">
            <h3>Datos de contacto</h3>
            <div className="info-row">
              <span className="ic"><WhatsApp style={{ width: 17, height: 17 }} /></span>
              <div><b>WhatsApp</b>+{comercio.whatsapp}</div>
            </div>
            {comercio.telefono && (
              <div className="info-row"><span className="ic"><Phone /></span><div><b>Teléfono</b>{comercio.telefono}</div></div>
            )}
            {comercio.direccion && (
              <div className="info-row"><span className="ic"><Pin /></span><div><b>Dirección</b>{comercio.direccion}</div></div>
            )}
          </div>

          <div className="info-card glass">
            <h3>Redes y web</h3>
            {redes.length === 0 && <p style={{ color: "var(--txt-3)", fontSize: 13 }}>Este comercio aún no cargó redes.</p>}
            {redes.map((r) => (
              <a className="info-row" key={r.label} href={r.href} target="_blank" rel="noopener" style={{ color: "inherit" }}>
                <span className="ic"><r.Icon style={{ width: 17, height: 17 }} /></span>
                <div><b>{r.label}</b>{r.href.replace(/^https?:\/\//, "")}</div>
              </a>
            ))}
          </div>

          <MensajeComercioForm comercioId={comercio.id} nombre={comercio.nombre} />

          <div className="info-card glass" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <h3>¿Problema con este negocio?</h3>
            <p style={{ color: "var(--txt-3)", fontSize: 13 }}>Si tuviste un inconveniente, contanos y lo revisamos.</p>
            <Link className="btn btn-ghost btn-sm" href={`/reclamos?comercio_id=${comercio.id}&nombre_comercio=${encodeURIComponent(comercio.nombre)}`}>Dejar un reclamo</Link>
          </div>
        </div>

        {/* PRODUCTOS (reales, viven en Reservalo — cada uno linkea directo a su ficha) */}
        {productos.length > 0 && (
        <>
        <div className="section-head" style={{ marginTop: 40 }}>
          <div><h2 style={{ fontSize: 24 }}>Productos</h2></div>
        </div>
        <div className="product-grid">
          {productos.map((p) => (
            <article className="offer" key={p.id}>
              <div className="body">
                <a href={p.url ?? undefined} target="_blank" rel="noopener" style={{ color: "inherit" }}>
                  <h4>{p.nombre}</h4>
                </a>
                {p.precio != null && <div className="price">{precioFmt(p.precio, p.moneda)}</div>}
                <div className="foot">
                  <span className="biz">{comercio.nombre}</span>
                  <WaLeadLink className="wa-mini" comercioId={comercio.id} whatsapp={comercio.whatsapp} mensaje={`Hola, me interesa ${p.nombre}`}>
                    <WhatsApp style={{ width: 17, height: 17, color: "#04240f" }} />
                  </WaLeadLink>
                </div>
              </div>
            </article>
          ))}
        </div>
        </>
        )}

        <Link className="back-link" href="/" style={{ display: "inline-flex", marginTop: 24 }}>
          <Arrow style={{ transform: "rotate(180deg)" }} /> Volver al inicio
        </Link>
        <div style={{ height: 50 }} />
      </div>
    </>
  );
}
