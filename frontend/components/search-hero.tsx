"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, WhatsApp } from "@/components/icons";
import { FilterChip, OptionList } from "@/components/filter-chips";

type Opt = { slug: string; nombre: string };

export function SearchHero({ rubros, zonas }: { rubros: Opt[]; zonas: Opt[] }) {
  const [q, setQ] = useState("");
  const [rubro, setRubro] = useState("");
  const [zona, setZona] = useState("");
  const [precio, setPrecio] = useState("");
  const router = useRouter();

  function buscar(ov: { q?: string; rubro?: string; zona?: string; precio?: string } = {}) {
    const p = new URLSearchParams();
    const term = (ov.q ?? q).trim(); if (term) p.set("q", term);
    const r = ov.rubro ?? rubro; if (r) p.set("rubro", r);
    const z = ov.zona ?? zona; if (z) p.set("zona", z);
    const pr = ov.precio ?? precio; if (pr) p.set("precio_max", pr);
    router.push(`/buscar?${p.toString()}`);
  }

  const ph = "Ej: zapatillas, ferretería, farmacia, iPhone…";
  const rubroNom = rubros.find((r) => r.slug === rubro)?.nombre;
  const zonaNom = zonas.find((z) => z.slug === zona)?.nombre;

  return (
    <div className="search-hero">
      <form onSubmit={(e) => { e.preventDefault(); buscar(); }} className="bigsearch">
        <Search style={{ width: 20, height: 20, color: "var(--txt-3)", flexShrink: 0 }} />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={ph} aria-label="Buscar" />
        <a className="bs-wa" href="https://wa.me/59170000000?text=Hola%2C%20busco%20en%20URUKU" target="_blank" rel="noopener" title="Consultar por WhatsApp">
          <WhatsApp style={{ width: 19, height: 19 }} />
        </a>
      </form>

      {(
        <div className="chipbar" style={{ justifyContent: "center", marginTop: 12 }}>
          <FilterChip icon="🏷" label="Categoría" value={rubroNom} active={!!rubro}>
            {(close) => <OptionList items={[{ slug: "", nombre: "Todas las categorías" }, ...rubros]} sel={rubro} onPick={(v) => { setRubro(v); close(); buscar({ rubro: v }); }} />}
          </FilterChip>
          <FilterChip icon="📍" label="Zona" value={zonaNom} active={!!zona}>
            {(close) => <OptionList items={[{ slug: "", nombre: "Todas las zonas" }, ...zonas]} sel={zona} onPick={(v) => { setZona(v); close(); buscar({ zona: v }); }} />}
          </FilterChip>
          <FilterChip icon="💰" label="Precio" value={precio ? `hasta ${precio}` : undefined} active={!!precio}>
            {(close) => (
              <div style={{ padding: 12, minWidth: 190 }}>
                <input className="adm-input" type="number" inputMode="numeric" value={precio} onChange={(e) => setPrecio(e.target.value)} placeholder="Precio máximo" />
                <button className="btn btn-primary btn-sm" style={{ marginTop: 8, width: "100%" }} onClick={() => { close(); buscar({ precio }); }}>Aplicar</button>
              </div>
            )}
          </FilterChip>
        </div>
      )}
    </div>
  );
}
