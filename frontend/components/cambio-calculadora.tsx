"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MapResults } from "@/components/map-results";
import { distanciaMetros, formatDistancia } from "@/lib/distancia";
import { pedirUbicacion, permisoUbicacion, ubicacionGuardada, type Ubicacion } from "@/lib/ubicacion";
import { comoLlegarHref, type ResultadoBusqueda } from "@/lib/types";

/**
 * La calculadora de cambio, con la cotización que INGRESA la persona.
 *
 * La del sitio es la referencia (y se carga primero), pero cada casa de
 * cambio tiene la suya y cambia durante el día: la cuenta que le sirve a
 * alguien parado frente al mostrador es con el número que le acaban de
 * decir, no con el nuestro. Por eso los tres valores son campos editables y
 * lo que se escribe queda guardado en el navegador.
 *
 * LA CUENTA COMO LA HACEN LAS CASAS DE CAMBIO: pesos × factor. El factor es
 * los bolivianos que dan por UN peso (1.000 pesos = 6,8 Bs → 0,0068). Se
 * muestra y se explica porque es lo que la gente ve escrito en la pizarra.
 */
export type Referencia = {
  ars_1000_bs: number | null;   // Bs por 1.000 pesos argentinos
  usd_bs: number | null;        // Bs por 1 dólar
  usd_ars: number | null;       // pesos argentinos por 1 dólar
  fecha: string | null;         // texto ya formateado
  vieja: boolean;
};

const CLAVE = "uk-cambio-tasas";

/** "6,8", "6.8", "1.570", "100.000" y "100000" → el número que la persona
 *  quiso escribir. La coma siempre es decimal. Un punto es decimal salvo que
 *  le sigan exactamente tres dígitos (un mil), o haya más de uno. "6.8"
 *  tomado como 68 es lo que hizo que 100.000 pesos dieran 6.800 Bs. */
function num(s: string): number {
  let t = String(s).trim().replace(/\s/g, "");
  if (t.includes(",")) {
    t = t.replace(/\./g, "").replace(",", ".");
  } else {
    const puntos = (t.match(/\./g) || []).length;
    if (puntos === 1 && !/\.\d{3}$/.test(t)) {
      // un solo punto y no son tres dígitos: es decimal ("6.8", "10.80")
    } else {
      t = t.replace(/\./g, "");
    }
  }
  const n = Number(t);
  return Number.isFinite(n) ? n : 0;
}
function bs(n: number): string { return n.toLocaleString("es-BO", { maximumFractionDigits: n < 100 ? 2 : 0 }); }
function ars(n: number): string { return Math.round(n).toLocaleString("es-BO"); }
function factorTxt(f: number): string { return f.toLocaleString("es-BO", { minimumFractionDigits: 4, maximumFractionDigits: 5 }); }

export function CambioCalculadora({ referencia: ref, casas }: { referencia: Referencia; casas: ResultadoBusqueda[] }) {
  // Los tres valores, como texto (para que se pueda escribir "6,8").
  const [t, setT] = useState({
    ars: ref.ars_1000_bs != null ? bs(ref.ars_1000_bs) : "",
    usd: ref.usd_bs != null ? bs(ref.usd_bs) : "",
    usdArs: ref.usd_ars != null ? ars(ref.usd_ars) : "",
  });
  const [propios, setPropios] = useState(false);
  useEffect(() => {
    try {
      const g = localStorage.getItem(CLAVE);
      if (g) { setT(JSON.parse(g)); setPropios(true); }
    } catch { /* modo privado */ }
  }, []);
  function cambiar(k: keyof typeof t, v: string) {
    const nuevo = { ...t, [k]: v };
    setT(nuevo); setPropios(true);
    try { localStorage.setItem(CLAVE, JSON.stringify(nuevo)); } catch { /* modo privado */ }
  }
  function volverAReferencia() {
    setT({ ars: ref.ars_1000_bs != null ? bs(ref.ars_1000_bs) : "", usd: ref.usd_bs != null ? bs(ref.usd_bs) : "", usdArs: ref.usd_ars != null ? ars(ref.usd_ars) : "" });
    setPropios(false);
    try { localStorage.removeItem(CLAVE); } catch { /* modo privado */ }
  }

  const ars1000 = num(t.ars);          // Bs por 1.000 ARS
  const factor = ars1000 / 1000;       // Bs por 1 ARS
  const usdBs = num(t.usd);
  const usdArs = num(t.usdArs);

  const [pesos, setPesos] = useState("100000");
  const [bolivianos, setBolivianos] = useState("1000");
  const [dolares, setDolares] = useState("100");
  const recibis = num(pesos) * factor;
  const necesitas = factor > 0 ? num(bolivianos) / factor : 0;

  // Dónde está la persona, para las distancias a las casas de cambio.
  const [ubicacion, setUbicacion] = useState<Ubicacion | null>(null);
  const [centrar, setCentrar] = useState(0);
  useEffect(() => {
    const g = ubicacionGuardada();
    if (g) { setUbicacion(g); return; }
    permisoUbicacion().then((p) => { if (p === "granted") pedirUbicacion().then(setUbicacion).catch(() => {}); });
  }, []);
  const dist = (c: ResultadoBusqueda) => ubicacion && c.lat != null && c.lng != null ? distanciaMetros(ubicacion.lat, ubicacion.lng, c.lat, c.lng) : null;
  const casasOrdenadas = ubicacion ? [...casas].sort((a, b) => (dist(a) ?? 1e12) - (dist(b) ?? 1e12)) : casas;

  return (
    <div className="uk-cambio-calc">
      {/* 1. La cotización, editable */}
      <section className="uk-cc-card">
        <div className="uk-cc-cab">
          <h2>Ingresá la cotización que te ofrecen</h2>
          <span className={ref.vieja && !propios ? "vieja" : ""}>
            {propios
              ? <>Estás usando tus valores · <button type="button" className="uk-cc-link" onClick={volverAReferencia}>volver a la referencia</button></>
              : ref.fecha
                ? <>Referencia del sitio, actualizada el {ref.fecha}{ref.vieja ? " — puede estar vieja, confirmá en el lugar" : ""}</>
                : "Sin referencia cargada: escribí la que te dan"}
          </span>
        </div>
        <div className="uk-cc-tasas">
          <label><span>1.000 pesos argentinos =</span><input inputMode="decimal" value={t.ars} onChange={(e) => cambiar("ars", e.target.value)} /><b>Bs</b></label>
          <label><span>1 dólar =</span><input inputMode="decimal" value={t.usd} onChange={(e) => cambiar("usd", e.target.value)} /><b>Bs</b></label>
          <label><span>1 dólar =</span><input inputMode="decimal" value={t.usdArs} onChange={(e) => cambiar("usdArs", e.target.value)} /><b>$ arg.</b></label>
        </div>
        {factor > 0 && (
          <p className="uk-cc-factor">
            Factor: <b>{factorTxt(factor)}</b> bolivianos por cada peso. Es el número que usan las casas de cambio:
            <em> pesos × {factorTxt(factor)} = bolivianos</em>.
          </p>
        )}
      </section>

      {/* 2. Las dos cuentas */}
      <div className="uk-cc-dos">
        <section className="uk-cc-card uk-cc-verde">
          <h2>¿Cuánto recibís?</h2>
          <p>Ingresá los pesos argentinos que traés.</p>
          <div className="uk-cc-in"><span>$</span><input inputMode="decimal" value={pesos} onChange={(e) => setPesos(e.target.value)} aria-label="Pesos argentinos" /></div>
          <div className="uk-cc-res"><small>Vas a recibir aproximadamente</small><b>Bs {bs(recibis)}</b>
            {factor > 0 && <small>{ars(num(pesos))} × {factorTxt(factor)} = {bs(recibis)}</small>}</div>
        </section>
        <section className="uk-cc-card">
          <h2>¿Cuántos pesos necesitás?</h2>
          <p>Ingresá los bolivianos que querés tener.</p>
          <div className="uk-cc-in"><span>Bs</span><input inputMode="decimal" value={bolivianos} onChange={(e) => setBolivianos(e.target.value)} aria-label="Bolivianos" /></div>
          <div className="uk-cc-res"><small>Vas a necesitar aproximadamente</small><b>$ {ars(necesitas)}</b>
            {factor > 0 && <small>{bs(num(bolivianos))} ÷ {factorTxt(factor)} = {ars(necesitas)}</small>}</div>
        </section>
        <section className="uk-cc-card">
          <h2>Si traés dólares</h2>
          <p>Rinden más que los pesos: mirá cuánto.</p>
          <div className="uk-cc-in"><span>US$</span><input inputMode="decimal" value={dolares} onChange={(e) => setDolares(e.target.value)} aria-label="Dólares" /></div>
          <div className="uk-cc-res">
            <small>En bolivianos</small><b>Bs {bs(num(dolares) * usdBs)}</b>
            <small>En pesos argentinos: $ {ars(num(dolares) * usdArs)}</small>
          </div>
        </section>
      </div>

      {/* 3. La cuenta, explicada */}
      <section className="uk-cc-card">
        <h2>Forma simple de hacer la cuenta</h2>
        <p>Así calculan las casas de cambio. Con estos ejemplos hacés las tuyas.</p>
        <div className="uk-cc-formulas">
          <div><b>De pesos a bolivianos</b><code>pesos × {factorTxt(factor)}</code><small>100.000 × {factorTxt(factor)} = Bs {bs(100000 * factor)}</small></div>
          <div><b>De bolivianos a pesos</b><code>bolivianos ÷ {factorTxt(factor)}</code><small>1.000 ÷ {factorTxt(factor)} = $ {factor > 0 ? ars(1000 / factor) : "—"}</small></div>
          <div><b>De dólares a bolivianos</b><code>dólares × {bs(usdBs)}</code><small>100 × {bs(usdBs)} = Bs {bs(100 * usdBs)}</small></div>
          <div><b>De dólares a pesos</b><code>dólares × {ars(usdArs)}</code><small>100 × {ars(usdArs)} = $ {ars(100 * usdArs)}</small></div>
        </div>
        <div className="uk-cc-ejemplos">
          {[50000, 100000, 200000].map((p) => (
            <button key={p} type="button" onClick={() => setPesos(String(p))}>Si llevás $ {ars(p)} → recibís <b>Bs {bs(p * factor)}</b></button>
          ))}
          {[500, 1000].map((b) => (
            <button key={b} type="button" onClick={() => setBolivianos(String(b))}>Si querés Bs {b.toLocaleString("es-BO")} → necesitás <b>$ {factor > 0 ? ars(b / factor) : "—"}</b></button>
          ))}
        </div>
        <p className="uk-cc-aviso">La cotización cambia entre casas de cambio y durante el día. Confirmá el valor antes de cambiar, y contá la plata ahí mismo.</p>
      </section>

      {/* 4. Dónde cambiar */}
      <section className="uk-cc-card">
        <div className="uk-cc-cab">
          <h2>Dónde cambiar</h2>
          <Link href="/buscar?rubro=cambio&vista=mapa" className="uk-btn-ghost">Ver todas en el buscador →</Link>
        </div>
        {casas.length === 0 ? <p className="uk-empty">Todavía no hay casas de cambio cargadas.</p> : (
          <div className="uk-cc-mapa">
            <div className="uk-cc-mapa-canvas">
              <MapResults results={casas} hayFiltro ubicacion={ubicacion} centrarEnMi={centrar}
                          onPedirUbicacion={() => pedirUbicacion().then((u) => { setUbicacion(u); setCentrar((n) => n + 1); }).catch(() => {})} />
            </div>
            <ul>
              {casasOrdenadas.slice(0, 8).map((c) => (
                <li key={c.id}>
                  <Link href={`/comercios/${c.slug}`}><b>{c.nombre}</b>{c.direccion ? <span>{c.direccion}</span> : null}</Link>
                  <span className="uk-cc-dist">{dist(c) != null ? `a ${formatDistancia(dist(c) as number)}` : ""}</span>
                  <a className="uk-btn-ghost" href={comoLlegarHref(c)} target="_blank" rel="noopener">Cómo llegar</a>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}
