"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, WhatsApp } from "@/components/icons";

// La tienda (Reservalo). Su buscador de productos vive en /productos?search=
const RESERVALO_URL = "https://reservalo.store";

const QUICK: { label: string; rubro: string }[] = [
  { label: "Gastronomía", rubro: "gastronomia" },
  { label: "Farmacias", rubro: "farmacia" },
  { label: "Servicios", rubro: "servicios" },
  { label: "Mercados", rubro: "mercado" },
  { label: "Tecnología", rubro: "tecnologia" },
];

type Opt = { slug: string; nombre: string };

export function SearchHero({ rubros, zonas }: { rubros: Opt[]; zonas: Opt[] }) {
  const [modo, setModo] = useState<"negocios" | "productos">("negocios");
  const [q, setQ] = useState("");
  const [rubro, setRubro] = useState("");
  const [zona, setZona] = useState("");
  const [precio, setPrecio] = useState("");
  const router = useRouter();

  function buscar(query?: string, rb?: string) {
    if (modo === "productos") {
      // Hand-off al buscador de productos de Reservalo (la tienda).
      const term = (query ?? q).trim();
      window.location.href = `${RESERVALO_URL}/productos${term ? `?search=${encodeURIComponent(term)}` : ""}`;
      return;
    }
    const p = new URLSearchParams();
    const term = (query ?? q).trim();
    if (term) p.set("q", term);
    const r = rb ?? rubro;
    if (r) p.set("rubro", r);
    if (zona) p.set("zona", zona);
    if (precio) p.set("precio_max", precio);
    router.push(`/buscar?${p.toString()}`);
  }

  const ph = modo === "negocios"
    ? "Ej: farmacia, mecánico, hotel, restaurante, gomería…"
    : "Ej: zapatillas, iphone, perfume, electrodoméstico…";

  return (
    <div className="search-hero">
      <div className="modo-toggle">
        <button type="button" className={modo === "negocios" ? "active" : ""} onClick={() => setModo("negocios")}>
          🗺️ Negocios <small>en el mapa</small>
        </button>
        <button type="button" className={modo === "productos" ? "active" : ""} onClick={() => setModo("productos")}>
          🛍️ Productos <small>en la tienda</small>
        </button>
      </div>

      <form onSubmit={(e) => { e.preventDefault(); buscar(); }} className="bigsearch">
        <Search style={{ width: 22, height: 22, color: "var(--txt-3)", flexShrink: 0 }} />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={ph} aria-label="Buscar" />
        <a className="bs-wa" href="https://wa.me/59170000000?text=Hola%2C%20busco%20en%20Encontralo" target="_blank" rel="noopener" title="Consultar por WhatsApp">
          <WhatsApp style={{ width: 20, height: 20 }} />
        </a>
      </form>

      {modo === "negocios" ? (
        <>
          <div className="qfilters">
            {QUICK.map((c) => (
              <button type="button" key={c.rubro} onClick={() => { setRubro(c.rubro); buscar(undefined, c.rubro); }}>{c.label}</button>
            ))}
          </div>
          <div className="sfilters">
            <select className="adm-input" value={rubro} onChange={(e) => setRubro(e.target.value)} aria-label="Rubro">
              <option value="">Todos los rubros</option>
              {rubros.map((r) => <option key={r.slug} value={r.slug}>{r.nombre}</option>)}
            </select>
            <select className="adm-input" value={zona} onChange={(e) => setZona(e.target.value)} aria-label="Zona">
              <option value="">Todas las zonas</option>
              {zonas.map((z) => <option key={z.slug} value={z.slug}>{z.nombre}</option>)}
            </select>
            <input className="adm-input" type="number" inputMode="numeric" value={precio} onChange={(e) => setPrecio(e.target.value)} placeholder="Precio máx." />
          </div>
        </>
      ) : (
        <div className="reservalo-banner" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <span>🛍️ Tu búsqueda se abre en <b style={{ color: "var(--txt)" }}>Reservalo</b>, la tienda — con sus filtros de categoría, talle y precio.</span>
          <a className="btn btn-primary btn-sm" href={`${RESERVALO_URL}/productos`} style={{ whiteSpace: "nowrap" }}>Ir a la tienda →</a>
        </div>
      )}
    </div>
  );
}
