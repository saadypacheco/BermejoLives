"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { HomeMap } from "@/components/home-map";
import { WhatsApp, Phone, Send, User, Search } from "@/components/icons";
import { type ComercioMapa } from "@/lib/data";
import { type FeedItem, precioFmt, vencimientoFmt } from "@/lib/types";
import { registrarLead } from "@/lib/campo";
import { distanciaMetros, formatDistancia } from "@/lib/distancia";

const CHIPS: { label: string; rubro: string }[] = [
  { label: "Todos", rubro: "" },
  { label: "Talleres", rubro: "gomeria" },
  { label: "Farmacias", rubro: "farmacia" },
  { label: "Restaurantes", rubro: "gastronomia" },
  { label: "Mercados", rubro: "mercado" },
  { label: "Tecnología", rubro: "tecnologia" },
];
const wa = (s?: string | null) => (s || "").replace(/\D/g, "");

export function MobileHome({ comercios, feed, soloOfertas = false }: { comercios: ComercioMapa[]; feed: FeedItem[]; soloOfertas?: boolean }) {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [sel, setSel] = useState<ComercioMapa | null>(null);
  const [miUbicacion, setMiUbicacion] = useState<{ lat: number; lng: number } | null>(null);
  const router = useRouter();

  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => setMiUbicacion({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => {},
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 600000 },
    );
  }, []);

  const distanciaSel = sel && miUbicacion && sel.lat != null && sel.lng != null
    ? distanciaMetros(miUbicacion.lat, miUbicacion.lng, sel.lat, sel.lng)
    : null;
  // Negocios que tienen al menos una oferta en el feed
  const offerSlugs = new Set(feed.map((f) => f.comercio_slug));
  let filtered = cat ? comercios.filter((c) => c.rubro_slug === cat) : comercios;
  if (soloOfertas) filtered = filtered.filter((c) => offerSlugs.has(c.slug));
  const ofertasNegocio = sel ? feed.filter((f) => f.comercio_slug === sel.slug) : [];

  // Mayor % de descuento activo por comercio, para el badge del pin en el mapa
  const descuentoPorId: Record<string, number> = {};
  for (const f of feed) {
    if (!f.descuento_pct) continue;
    const c = comercios.find((c) => c.slug === f.comercio_slug);
    if (!c) continue;
    if (!descuentoPorId[c.id] || f.descuento_pct > descuentoPorId[c.id]) descuentoPorId[c.id] = f.descuento_pct;
  }

  function buscar(e: React.FormEvent) {
    e.preventDefault();
    router.push(`/buscar${q.trim() ? `?q=${encodeURIComponent(q.trim())}` : ""}`);
  }

  return (
    <div className="mhome">
      {/* Header oscuro: marca + tagline + acciones + buscador */}
      <div className="mhead">
        <div className="mtop">
          <Link href="/" className="mbrand">
            <span className="mbrand-name">ENCON<i>TRALO</i></span>
            <span className="mtag">EN EL MAPA</span>
          </Link>
          <div className="mtop-right">
            <Link href="/mi-comercio" className="mavatar" aria-label="Perfil"><User style={{ width: 20, height: 20 }} /></Link>
            <Link href="/autoregistro?modo=registro" className="mpublica">Publicá tu negocio <span aria-hidden>↗</span></Link>
          </div>
        </div>
        <form onSubmit={buscar} className="msearch">
          <Search style={{ width: 20, height: 20, color: "#7a8390" }} />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar locales o servicios…" aria-label="Buscar" />
        </form>
      </div>

      {/* Chips de categoría (texto simple, filtran el mapa) */}
      <div className="mchips">
        {CHIPS.map((c) => (
          <button type="button" key={c.label} className={`mchip ${cat === c.rubro ? "active" : ""}`} onClick={() => { setCat(c.rubro); setSel(null); }}>
            {c.label}
          </button>
        ))}
      </div>

      {soloOfertas && (
        <div className="mfilter-note">
          <span>🔥 Mostrando solo negocios con ofertas</span>
          <Link href="/">Ver todos ✕</Link>
        </div>
      )}

      {/* Mapa: crece y llena el espacio disponible */}
      <div className="mmap">
        <HomeMap comercios={filtered} onSelect={setSel} selectedId={sel?.id} descuentoPorId={descuentoPorId} />
        <Link href="/buscar" className="mmapbtn">⛶ Ver mapa completo</Link>

      {/* Tarjeta flotante sobre el mapa, conectada al pin por la flecha */}
      {sel && (
        <div className="mcard">
          <div className="mcard-row">
            <div className="mcard-img">
              {(sel.portada_url || sel.logo_url) && (
                <img
                  key={sel.id}
                  src={(sel.portada_url || sel.logo_url) as string}
                  alt="" loading="lazy" decoding="async"
                  onError={(e) => { e.currentTarget.style.display = "none"; e.currentTarget.nextElementSibling?.removeAttribute("hidden"); }}
                />
              )}
              <span hidden={!!(sel.portada_url || sel.logo_url)}>🏪</span>
            </div>
            <div className="mcard-info">
              <div className="mcard-head">
                <b>{sel.nombre}</b>
                <button className="mclose" onClick={() => setSel(null)} aria-label="Cerrar">✕</button>
              </div>
              {sel.descripcion && <p>{sel.descripcion}</p>}
              {sel.horario && <div className="mcard-line">🕐 {sel.horario}</div>}
              <div className="mcard-line star">★ {sel.rating}{distanciaSel != null && <span className="mcard-dist">· 📍 {formatDistancia(distanciaSel)}</span>}</div>
            </div>
          </div>
          <div className="mcard-act">
            <div className="mcard-icons">
              {wa(sel.whatsapp) && <a className="mab wa" href={`https://wa.me/${wa(sel.whatsapp)}`} target="_blank" rel="noopener" aria-label="WhatsApp" onClick={() => registrarLead(sel.id)}><WhatsApp style={{ width: 20, height: 20 }} /></a>}
              {sel.telefono && <a className="mab" href={`tel:${sel.telefono}`} aria-label="Llamar" onClick={() => registrarLead(sel.id, "telefono")}><Phone style={{ width: 18, height: 18 }} /></a>}
              <a className="mab" href={sel.como_llegar ?? `https://www.google.com/maps/search/?api=1&query=${sel.lat},${sel.lng}`} target="_blank" rel="noopener" aria-label="Cómo llegar"><Send style={{ width: 18, height: 18 }} /></a>
            </div>
            <Link className="btn btn-primary mver" href={`/comercios/${sel.slug}`}>Ver tienda</Link>
          </div>

          {/* Ofertas de este negocio (si tiene) */}
          {ofertasNegocio.length > 0 && (
            <div className="mcard-ofertas">
              <div className="mco-head"><b>Ofertas de este negocio</b></div>
              <div className="mco-rail">
                {ofertasNegocio.map((o) => (
                  <Link key={o.id} href={`/comercios/${o.comercio_slug}`} className="mco">
                    <div className="mco-img">
                      {o.descuento_pct != null && <span className="off-badge">-{o.descuento_pct}%</span>}
                      {o.imagen_url && (
                        <img
                          src={o.imagen_url} alt="" loading="lazy" decoding="async"
                          onError={(e) => { e.currentTarget.style.display = "none"; }}
                        />
                      )}
                    </div>
                    <div className="mco-b">
                      <b>{o.titulo}</b>
                      {o.precio != null && <span className="mco-price">{precioFmt(o.precio, o.moneda)}</span>}
                      {o.vence_el && <span className="off-vence">Válido hasta {vencimientoFmt(o.vence_el)}</span>}
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      </div>

      {/* Ofertas cerca tuyo: se oculta si hay un local seleccionado, o si ningún comercio tiene ofertas todavía */}
      {!sel && feed.length > 0 && (
      <div className="moffers">
        <div className="moffers-head"><b>Ofertas cerca tuyo</b><Link href="/buscar">Ver todas</Link></div>
        <div className="moffers-rail">
          {feed.slice(0, 8).map((p) => (
            <Link key={p.id} href={`/comercios/${p.comercio_slug}`} className="moffer">
              <div className="moffer-img">
                {p.descuento_pct != null && <span className="off-badge">-{p.descuento_pct}%</span>}
                {p.imagen_url && <img src={p.imagen_url} alt="" loading="lazy" decoding="async" />}
              </div>
              <div className="moffer-b">
                <b>{p.titulo}</b>
                <small>{p.comercio_nombre}</small>
                {p.precio != null && <div className="moffer-price">{precioFmt(p.precio, p.moneda)}</div>}
                {p.vence_el && <small className="off-vence">Válido hasta {vencimientoFmt(p.vence_el)}</small>}
              </div>
            </Link>
          ))}
        </div>
      </div>
      )}
    </div>
  );
}
