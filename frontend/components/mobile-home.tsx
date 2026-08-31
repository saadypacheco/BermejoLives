"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { HomeMap } from "@/components/home-map";
import { CitySelector } from "@/components/city-selector";
import { ThemeToggle } from "@/components/uruku-theme";
import { WhatsApp, Phone, Send, User, Search } from "@/components/icons";
import { type ComercioMapa, getRubros } from "@/lib/data";
import { type Ciudad, type Rubro } from "@/lib/types";
import { type FeedItem, precioFmt, vencimientoFmt } from "@/lib/types";
import { registrarLead } from "@/lib/campo";
import { distanciaMetros, formatDistancia } from "@/lib/distancia";
import { abiertoAhora } from "@/lib/horario";
import { GuardarBoton } from "@/components/guardar-boton";
import { HorarioBadge } from "@/components/horario-badge";
import { ImageLightbox } from "@/components/image-lightbox";

// Los chips salen de los comercios que hay EN EL MAPA, no de una lista fija.
//
// La lista fija tenía cinco y tres estaban muertas: "gastronomia", "mercado" y
// "tecnologia" no son slugs de ningún rubro (los reales son "restaurantes",
// "alimentos" y "computacion"). Tocarlas vaciaba la pantalla.
//
// Derivarlos de lo cargado tiene una garantía que una lista escrita a mano no
// puede dar: ningún chip puede devolver cero, porque sólo aparece si hay
// comercios de ese rubro a la vista.
const MAX_CHIPS = 8;

function chipsDe(comercios: ComercioMapa[], rubros: Rubro[]): { label: string; rubro: string }[] {
  const cuenta = new Map<string, number>();
  for (const c of comercios) {
    // Cuenta por TODOS sus rubros. Contando sólo el principal, categorías
    // grandes como "Deportes y fitness" —55 comercios— no llegaban a los
    // primeros puestos porque casi ninguno la tiene como principal.
    const suyos = c.rubro_slugs?.length ? c.rubro_slugs : (c.rubro_slug ? [c.rubro_slug] : []);
    for (const slug of suyos) {
      if (!slug || slug === "otros") continue;
      cuenta.set(slug, (cuenta.get(slug) ?? 0) + 1);
    }
  }
  const nombre = new Map(rubros.map((r) => [r.slug, r.nombre.replace(/^[^\p{L}\p{N}]+/u, "").trim()]));
  const top = [...cuenta.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, MAX_CHIPS)
    .map(([slug]) => ({ label: nombre.get(slug) || slug, rubro: slug }));
  return [{ label: "Todos", rubro: "" }, ...top];
}
const wa = (s?: string | null) => (s || "").replace(/\D/g, "");

export function MobileHome({ comercios, feed, soloOfertas = false, center, ciudad, ciudades, embedded = false }: { comercios: ComercioMapa[]; feed: FeedItem[]; soloOfertas?: boolean; center?: [number, number] | null; ciudad?: Ciudad | null; ciudades?: Ciudad[]; embedded?: boolean }) {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [rubros, setRubros] = useState<Rubro[]>([]);
  useEffect(() => { getRubros().then(setRubros).catch(() => {}); }, []);
  const chips = chipsDe(comercios, rubros);
  const [soloAbiertos, setSoloAbiertos] = useState(false);
  // "Abierto ahora" sólo se muestra si ALGÚN comercio tiene horario cargado.
  // Medido el 27/8 sobre 680: ninguno lo tenía, así que el filtro estaba a la
  // vista y no podía dar un resultado correcto nunca. Acá no hace falta
  // consultar nada — los comercios ya están en memoria.
  const hayHorarios = comercios.some((c) => (c.horario ?? "").trim() !== "");
  const [sel, setSel] = useState<ComercioMapa | null>(null);
  const [fotoAmpliada, setFotoAmpliada] = useState<string | null>(null);
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
  // Se mira TODA la lista de rubros, no sólo el principal. Filtrar por
  // "Calzado" dejaba afuera a los locales que venden calzado pero tienen otro
  // rubro como principal — o sea, la mayoría: el promedio es 2,69 rubros por
  // comercio y sólo uno puede ser el principal.
  let filtered = cat
    ? comercios.filter((c) => c.rubro_slugs?.includes(cat) || c.rubro_slug === cat)
    : comercios;
  if (soloOfertas) filtered = filtered.filter((c) => offerSlugs.has(c.slug));
  if (soloAbiertos) filtered = filtered.filter((c) => abiertoAhora(c.horario).estado === "abierto");
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
    <div className={`mhome${embedded ? " embedded" : ""}`}>
      {/* Header propio (solo modo standalone; en /mapa lo provee el shell URUKU) */}
      {!embedded && (
      <div className="mhead">
        <div className="mtop">
          <Link href="/" className="mbrand">
            <span className="mbrand-name">URUKU</span>
            <span className="mtag">EN EL MAPA</span>
          </Link>
          <div className="mtop-right">
            {ciudades && ciudades.length > 0 && <CitySelector actual={ciudad ?? null} ciudades={ciudades} />}
            <ThemeToggle />
            <Link href="/mi-comercio" className="mavatar" aria-label="Ingresá tu negocio" title="¿Tenés un negocio? Ingresá acá"><User style={{ width: 20, height: 20 }} /></Link>
            <Link href="/autoregistro?modo=registro" className="mpublica">Publicá tu negocio <span aria-hidden>↗</span></Link>
          </div>
        </div>
        <form onSubmit={buscar} className="msearch">
          <Search style={{ width: 20, height: 20, color: "#7a8390" }} />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar locales o servicios…" aria-label="Buscar" />
        </form>
      </div>
      )}

      {/* Chips de categoría (texto simple, filtran el mapa) */}
      <div className="mchips">
        {hayHorarios && (
          <button type="button" className={`mchip mchip-open ${soloAbiertos ? "active" : ""}`} onClick={() => { setSoloAbiertos((v) => !v); setSel(null); }}>
            🟢 Abierto ahora
          </button>
        )}
        {chips.map((c) => (
          <button type="button" key={c.label} className={`mchip ${cat === c.rubro ? "active" : ""}`} onClick={() => { setCat(c.rubro); setSel(null); }}>
            {c.label}
          </button>
        ))}
      </div>

      {soloAbiertos && (
        <div className="mfilter-note">
          <span>🟢 Mostrando {filtered.length} {filtered.length === 1 ? "negocio abierto" : "negocios abiertos"} ahora</span>
          <button type="button" onClick={() => setSoloAbiertos(false)} style={{ background: "none", border: 0, color: "inherit", cursor: "pointer", font: "inherit" }}>Ver todos ✕</button>
        </div>
      )}

      {soloOfertas && (
        <div className="mfilter-note">
          <span>🔥 Mostrando solo negocios con ofertas</span>
          <Link href="/mapa">Ver todos ✕</Link>
        </div>
      )}

      {/* Mapa: crece y llena el espacio disponible */}
      <div className="mmap">
        <HomeMap comercios={filtered} onSelect={setSel} selectedId={sel?.id} descuentoPorId={descuentoPorId} center={center} ciudad={ciudad ?? null} />
        <Link href="/buscar" className="mmapbtn">⛶ Ver mapa completo</Link>

      {/* Tarjeta flotante sobre el mapa, conectada al pin por la flecha */}
      {sel && (
        <div className="mcard">
          <div className="mcard-row">
            <div className="mcard-img">
              {(sel.portada_url || sel.logo_url) && (
                <img
                  key={sel.id}
                  src={(sel.portada_thumb_url || sel.portada_url || sel.logo_url) as string}
                  alt="" loading="lazy" decoding="async"
                  onClick={() => setFotoAmpliada((sel.portada_url || sel.logo_url) as string)}
                  onError={(e) => { e.currentTarget.style.display = "none"; e.currentTarget.nextElementSibling?.removeAttribute("hidden"); }}
                />
              )}
              <span hidden={!!(sel.portada_url || sel.logo_url)}>🏪</span>
            </div>
            <div className="mcard-info">
              <div className="mcard-head">
                <b>{sel.nombre}</b>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <GuardarBoton comercioId={sel.id} className="mclose" />
                  <button className="mclose" onClick={() => setSel(null)} aria-label="Cerrar">✕</button>
                </div>
              </div>
              {sel.descripcion && <p>{sel.descripcion}</p>}
              {(sel.prod_obs_human || sel.prod_det_ia) && <p style={{ opacity: 0.85 }}>🛍️ {sel.prod_obs_human || sel.prod_det_ia}</p>}
              {sel.horario && <div className="mcard-line">🕐 {sel.horario} <HorarioBadge horario={sel.horario} /></div>}
              <div className="mcard-line star">★ {sel.rating}{distanciaSel != null && <span className="mcard-dist">· 📍 {formatDistancia(distanciaSel)}</span>}</div>
            </div>
          </div>
          <div className="mcard-act">
            <div className="mcard-icons">
              {wa(sel.whatsapp) && <a className="mab wa" href={`https://wa.me/${wa(sel.whatsapp)}`} target="_blank" rel="noopener" aria-label="WhatsApp" onClick={() => registrarLead(sel.id)}><WhatsApp style={{ width: 20, height: 20 }} /></a>}
              {sel.telefono && <a className="mab" href={`tel:${sel.telefono}`} aria-label="Llamar" onClick={() => registrarLead(sel.id, "telefono")}><Phone style={{ width: 18, height: 18 }} /></a>}
              <a className="mab" href={sel.como_llegar ?? `https://www.google.com/maps/search/?api=1&query=${sel.lat},${sel.lng}`} target="_blank" rel="noopener" aria-label="Cómo llegar" onClick={() => registrarLead(sel.id, "mapa")}><Send style={{ width: 18, height: 18 }} /></a>
            </div>
            {/* "Más información" (ficha completa) — visible para todos en el lanzamiento */}
            <Link className="btn btn-primary mver" href={`/comercios/${sel.slug}`}>Más información</Link>
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
      {fotoAmpliada && (
        <ImageLightbox src={fotoAmpliada} alt={sel?.nombre} onClose={() => setFotoAmpliada(null)} />
      )}
    </div>
  );
}
