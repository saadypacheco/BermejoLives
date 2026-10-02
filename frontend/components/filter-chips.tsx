"use client";

import { useEffect, useRef, useState } from "react";
import { Ic, type NombreIcono } from "@/components/ic";

/* Chip que abre un dropdown moderno (reusable: Home y /buscar) */
export function FilterChip({ icon, label, value, active, children }: {
  icon: NombreIcono; label: string; value?: string; active?: boolean;
  children: (close: () => void) => React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function onDoc(e: MouseEvent) { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);
  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button type="button" className={`fchip ${active ? "active" : ""}`} onClick={() => setOpen((o) => !o)}>
        <Ic n={icon} s={15} />{value || label}<span className="fchip-caret"><Ic n="desplegar" s={13} /></span>
      </button>
      {open && <div className="fchip-pop">{children(() => setOpen(false))}</div>}
    </div>
  );
}

export function OptionList({ items, sel, onPick }: {
  items: { slug: string; nombre: string }[]; sel: string; onPick: (v: string) => void;
}) {
  return (
    <div className="optlist">
      {items.map((it) => (
        <button type="button" key={it.slug || "todas"} className={sel === it.slug ? "active" : ""} onClick={() => onPick(it.slug)}>{it.nombre}</button>
      ))}
    </div>
  );
}
