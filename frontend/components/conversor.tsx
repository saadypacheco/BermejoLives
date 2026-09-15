"use client";

import { useState } from "react";
import { MONEDAS, convertir, formatoMonto, type Moneda, type Tasas } from "@/lib/cambio";

/**
 * El conversor: un monto, de una moneda a otra, con las cotizaciones del
 * sitio. Arranca en "1.000 pesos → bolivianos", que es la pregunta que trae
 * a la mitad de los que cruzan.
 */
export function Conversor({ tasas }: { tasas: Tasas }) {
  const [monto, setMonto] = useState("1000");
  const [de, setDe] = useState<Moneda>("ARS");
  const [a, setA] = useState<Moneda>("BOB");
  const n = Number(monto.replace(/\./g, "").replace(",", "."));
  const res = Number.isFinite(n) ? convertir(n, de, a, tasas) : null;
  const sim = (m: Moneda) => MONEDAS.find((x) => x.codigo === m)!.simbolo;

  return (
    <div className="uk-conv">
      <div className="uk-conv-fila">
        <input className="uk-conv-monto" inputMode="decimal" value={monto} onChange={(e) => setMonto(e.target.value)} aria-label="Monto" />
        <select value={de} onChange={(e) => setDe(e.target.value as Moneda)} aria-label="Moneda de origen">
          {MONEDAS.map((m) => <option key={m.codigo} value={m.codigo}>{m.nombre}</option>)}
        </select>
      </div>
      <button type="button" className="uk-conv-swap" onClick={() => { setDe(a); setA(de); }} aria-label="Invertir">⇅</button>
      <div className="uk-conv-fila">
        <div className="uk-conv-res" aria-live="polite">
          {res == null ? "—" : <><b>{sim(a)} {formatoMonto(res, a)}</b></>}
        </div>
        <select value={a} onChange={(e) => setA(e.target.value as Moneda)} aria-label="Moneda de destino">
          {MONEDAS.map((m) => <option key={m.codigo} value={m.codigo}>{m.nombre}</option>)}
        </select>
      </div>
      <div className="uk-conv-chips">
        {[["1000", "ARS"], ["5000", "ARS"], ["10000", "ARS"], ["50000", "ARS"], ["100", "BOB"], ["500", "BOB"], ["100", "USD"]].map(([m, mon]) => (
          <button key={m + mon} type="button" onClick={() => { setMonto(m); setDe(mon as Moneda); setA(mon === "BOB" ? "ARS" : "BOB"); }}>
            {sim(mon as Moneda)} {formatoMonto(Number(m), mon as Moneda)}
          </button>
        ))}
      </div>
    </div>
  );
}
