"use client";

// Gráficos propios del panel (SVG + CSS, sin librerías): barras verticales,
// líneas múltiples, barras horizontales y barras de progreso.
//
// TRES DECISIONES QUE CONVIENE CONOCER
// ====================================
//
// 1. EL SVG SE DIBUJA A TAMAÑO REAL. Un viewBox fijo de 600 px que se achica a
//    320 px deja el texto de los ejes en 6 px: ilegible en el celular, que es
//    donde más se usa el panel. Por eso se mide el ancho del contenedor y el
//    viewBox es ese ancho: 1 unidad = 1 px, el texto mantiene su tamaño y lo
//    que se adapta es la cantidad de rótulos del eje X.
// 2. EN EL CELULAR NO HAY HOVER. Tocar (o arrastrar el dedo) sobre el gráfico
//    elige el día y su valor se lee arriba, en texto. Con mouse alcanza con
//    pasar por encima; con teclado, flechas izquierda/derecha.
// 3. NO SE LEE SÓLO POR COLOR. Cada serie tiene nombre y trazo distinto
//    (continuo / punteado), cada barra de progreso dice su número y su %, y el
//    gráfico entero lleva `aria-label` con el resumen en palabras.

import { useCallback, useEffect, useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent, ReactNode } from "react";
import "@/app/styles/admin-dashboard.css";

/* ───────────────────────────── utilidades ───────────────────────────── */

/** 1300 → «1.300» (es-AR). */
export function fmt(n: number): string {
  return n.toLocaleString("es-AR");
}

/** Porcentaje entero para mostrar. Nunca redondea hacia un 100% que no es
 *  (99,6% → «99%») ni hacia un 0% que no es (0,3% → «<1%»). */
export function pct(parte: number, total: number): string {
  if (total <= 0) return "—";
  if (parte >= total) return "100%";
  if (parte <= 0) return "0%";
  const p = (parte / total) * 100;
  if (p < 1) return "<1%";
  return `${Math.min(99, Math.round(p))}%`;
}

/** El mismo porcentaje como número (para el ancho de la barra). */
export function pctNum(parte: number, total: number): number {
  if (total <= 0) return 0;
  return Math.max(0, Math.min(100, (parte / total) * 100));
}

/** «2026-10-06» → «6/10». */
export function fechaCorta(iso: string): string {
  const [, m, d] = iso.split("-");
  if (!m || !d) return iso;
  return `${Number(d)}/${Number(m)}`;
}

const DIAS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];

/** «2026-10-06» → «mar 6/10». */
export function fechaConDia(iso: string): string {
  const [a, m, d] = iso.split("-").map(Number);
  if (!a || !m || !d) return iso;
  const dia = DIAS[new Date(Date.UTC(a, m - 1, d)).getUTCDay()];
  return `${dia} ${d}/${m}`;
}

/** Tope y paso «redondos» para el eje Y (enteros: son conteos). */
function escalaY(max: number): { tope: number; paso: number } {
  if (max <= 0) return { tope: 4, paso: 1 };
  const crudo = max / 4;
  const mag = Math.pow(10, Math.floor(Math.log10(crudo)));
  const paso = Math.max(1, [1, 2, 5, 10].map((k) => k * mag).find((p) => p >= crudo) ?? 10 * mag);
  return { tope: paso * Math.ceil(max / paso), paso };
}

/** Mide el ancho del contenedor para dibujar el SVG a 1:1. */
function useAncho(inicial: number) {
  const ref = useRef<HTMLDivElement>(null);
  const [ancho, setAncho] = useState(inicial);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const medir = () => {
      const w = Math.floor(el.getBoundingClientRect().width);
      if (w > 0) setAncho(w);
    };
    medir();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", medir);
      return () => window.removeEventListener("resize", medir);
    }
    const ro = new ResizeObserver(medir);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, Math.max(240, ancho)] as const;
}

/** Elegir un día tocando, pasando el mouse o con el teclado. */
function useSeleccion(n: number, izq: number, util: number) {
  const [activo, setActivo] = useState<number | null>(null);

  const desdeX = useCallback((e: PointerEvent<SVGSVGElement>) => {
    if (n <= 0) return;
    const r = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - r.left - izq;
    setActivo(Math.min(n - 1, Math.max(0, Math.floor(x / (util / n)))));
  }, [n, izq, util]);

  const manejadores = {
    onPointerDown: desdeX,
    // Con el dedo, pointermove sólo llega mientras se arrastra (buttons = 1).
    onPointerMove: (e: PointerEvent<SVGSVGElement>) => { if (e.pointerType === "mouse" || e.buttons) desdeX(e); },
    // El mouse que se va limpia la selección; el dedo que se levanta, no
    // (el valor tiene que seguir a la vista para leerlo).
    onPointerLeave: (e: PointerEvent<SVGSVGElement>) => { if (e.pointerType === "mouse") setActivo(null); },
    onKeyDown: (e: KeyboardEvent<SVGSVGElement>) => {
      if (n <= 0) return;
      if (e.key === "ArrowLeft") { e.preventDefault(); setActivo((a) => (a === null ? n - 1 : Math.max(0, a - 1))); }
      else if (e.key === "ArrowRight") { e.preventDefault(); setActivo((a) => (a === null ? n - 1 : Math.min(n - 1, a + 1))); }
      else if (e.key === "Home") { e.preventDefault(); setActivo(0); }
      else if (e.key === "End") { e.preventDefault(); setActivo(n - 1); }
      else if (e.key === "Escape") setActivo(null);
    },
  };
  return { activo, manejadores };
}

const AYUDA_TOQUE = "Tocá (o pasá el mouse por) el gráfico para ver el valor de cada día.";

/* ─────────────────────────── barras verticales ─────────────────────────── */

export type PuntoBarra = {
  /** Rótulo corto del eje X («6/10»). */
  etiqueta: string;
  /** Rótulo completo para el valor leído («mar 6/10»). */
  detalle: string;
  valor: number;
};

export function BarrasVerticales(props: {
  datos: PuntoBarra[];
  /** Color CSS, p.ej. `var(--neon)`. */
  color: string;
  /** Cómo se llama lo que se cuenta: «alta» / «altas». */
  unidad: { uno: string; otros: string };
  /** El resumen en palabras (lo lee el lector de pantalla). */
  resumen: string;
  alto?: number;
}) {
  const { datos, color, unidad, resumen, alto = 210 } = props;
  const [ref, ancho] = useAncho(560);
  const n = datos.length;
  const max = datos.reduce((m, d) => Math.max(m, d.valor), 0);
  const { tope, paso } = escalaY(max);

  const arriba = 12, abajo = 28, der = 14;
  const izq = fmt(tope).length * 7 + 14;
  const util = Math.max(1, ancho - izq - der);
  const altoUtil = alto - arriba - abajo;
  const slot = util / Math.max(1, n);
  const anchoBarra = Math.max(2, Math.min(28, slot * 0.68));
  const y = (v: number) => arriba + altoUtil - (v / tope) * altoUtil;

  const { activo, manejadores } = useSeleccion(n, izq, util);
  // Un rótulo cada tanto, contando desde HOY hacia atrás.
  const cadaCuanto = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(util / 48))));

  const ticks: number[] = [];
  for (let v = 0; v <= tope; v += paso) ticks.push(v);

  const sel = activo !== null ? datos[activo] : null;

  return (
    <figure className="adb-fig">
      <div className="adb-readout" role="status" aria-live="polite">
        {sel
          ? <><b>{sel.detalle}</b><span>{fmt(sel.valor)} {sel.valor === 1 ? unidad.uno : unidad.otros}</span></>
          : <small>{AYUDA_TOQUE}</small>}
      </div>
      <div ref={ref} className="adb-svgwrap">
        <svg viewBox={`0 0 ${ancho} ${alto}`} width="100%" height={alto} role="img" aria-label={resumen}
             tabIndex={0} className="adb-svg" {...manejadores}>
          {ticks.map((v) => (
            <g key={v}>
              <line x1={izq} x2={ancho - der} y1={y(v)} y2={y(v)} className={v === 0 ? "adb-eje" : "adb-grilla"} />
              <text x={izq - 8} y={y(v) + 4} textAnchor="end" className="adb-txt">{fmt(v)}</text>
            </g>
          ))}
          {datos.map((d, k) => {
            const cx = izq + (k + 0.5) * slot;
            const h = (d.valor / tope) * altoUtil;
            const esActivo = k === activo;
            return (
              <g key={k}>
                {esActivo && <rect x={izq + k * slot} y={arriba} width={slot} height={altoUtil} className="adb-banda" />}
                {d.valor > 0 && (
                  <rect x={cx - anchoBarra / 2} y={y(d.valor)} width={anchoBarra} height={Math.max(2, h)} rx={Math.min(3, anchoBarra / 2)}
                        style={{ fill: color, opacity: activo === null || esActivo ? 1 : 0.45 }} />
                )}
                {(n - 1 - k) % cadaCuanto === 0 && (
                  <text x={cx} y={alto - 8} textAnchor="middle" className={esActivo ? "adb-txt adb-txt-on" : "adb-txt"}>{d.etiqueta}</text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </figure>
  );
}

/* ──────────────────────────── líneas múltiples ──────────────────────────── */

export type SerieLinea = {
  nombre: string;
  /** Color CSS, p.ej. `var(--blue-soft)`. */
  color: string;
  valores: number[];
  /** Trazo punteado: distingue la serie sin depender del color. */
  punteada?: boolean;
};

export function Lineas(props: {
  /** Un rótulo por punto. `etiquetas[k]` es el eje X; `detalles[k]`, el valor leído. */
  etiquetas: string[];
  detalles: string[];
  series: SerieLinea[];
  resumen: string;
  alto?: number;
}) {
  const { etiquetas, detalles, series, resumen, alto = 220 } = props;
  const [ref, ancho] = useAncho(560);
  const n = etiquetas.length;
  const max = series.reduce((m, s) => Math.max(m, ...s.valores, 0), 0);
  const { tope, paso } = escalaY(max);

  const arriba = 12, abajo = 28, der = 14;
  const izq = fmt(tope).length * 7 + 14;
  const util = Math.max(1, ancho - izq - der);
  const altoUtil = alto - arriba - abajo;
  const slot = util / Math.max(1, n);
  const x = (k: number) => izq + (k + 0.5) * slot;
  const y = (v: number) => arriba + altoUtil - (v / tope) * altoUtil;

  const { activo, manejadores } = useSeleccion(n, izq, util);
  const cadaCuanto = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(util / 48))));
  const ticks: number[] = [];
  for (let v = 0; v <= tope; v += paso) ticks.push(v);

  const trazo = (vals: number[]) => vals.map((v, k) => `${k === 0 ? "M" : "L"}${x(k).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");

  return (
    <figure className="adb-fig">
      <div className="adb-readout" role="status" aria-live="polite">
        {activo !== null
          ? <>
              <b>{detalles[activo]}</b>
              {series.map((s) => (
                <span key={s.nombre} className="adb-readout-serie">
                  <i className="adb-muestra" style={{ background: s.color }} aria-hidden />
                  {s.nombre} <b>{fmt(s.valores[activo] ?? 0)}</b>
                </span>
              ))}
            </>
          : <small>{AYUDA_TOQUE}</small>}
      </div>
      <div ref={ref} className="adb-svgwrap">
        <svg viewBox={`0 0 ${ancho} ${alto}`} width="100%" height={alto} role="img" aria-label={resumen}
             tabIndex={0} className="adb-svg" {...manejadores}>
          {ticks.map((v) => (
            <g key={v}>
              <line x1={izq} x2={ancho - der} y1={y(v)} y2={y(v)} className={v === 0 ? "adb-eje" : "adb-grilla"} />
              <text x={izq - 8} y={y(v) + 4} textAnchor="end" className="adb-txt">{fmt(v)}</text>
            </g>
          ))}
          {etiquetas.map((e, k) => (n - 1 - k) % cadaCuanto === 0 && (
            <text key={k} x={x(k)} y={alto - 8} textAnchor="middle" className={k === activo ? "adb-txt adb-txt-on" : "adb-txt"}>{e}</text>
          ))}
          {activo !== null && <line x1={x(activo)} x2={x(activo)} y1={arriba} y2={arriba + altoUtil} className="adb-guia" />}
          {series.map((s) => (
            <g key={s.nombre}>
              <path d={trazo(s.valores)} fill="none" strokeWidth={2.4} strokeLinejoin="round" strokeLinecap="round"
                    strokeDasharray={s.punteada ? "6 5" : undefined} style={{ stroke: s.color }} />
              {activo !== null && (
                <circle cx={x(activo)} cy={y(s.valores[activo] ?? 0)} r={5} strokeWidth={2} className="adb-punto" style={{ stroke: s.color }} />
              )}
            </g>
          ))}
        </svg>
      </div>
    </figure>
  );
}

/** La leyenda de un gráfico de líneas: muestra del trazo + nombre + total. */
export function LeyendaLineas(props: { items: { nombre: string; color: string; punteada?: boolean; detalle?: string }[] }) {
  return (
    <ul className="adb-leyenda">
      {props.items.map((it) => (
        <li key={it.nombre}>
          <svg width="26" height="10" aria-hidden>
            <line x1="1" x2="25" y1="5" y2="5" strokeWidth="3" strokeLinecap="round"
                  strokeDasharray={it.punteada ? "5 4" : undefined} style={{ stroke: it.color }} />
          </svg>
          <b>{it.nombre}</b>
          {it.detalle && <span>{it.detalle}</span>}
        </li>
      ))}
    </ul>
  );
}

/* ─────────────────────────── barras horizontales ─────────────────────────── */

export type FilaBarra = {
  id: string;
  etiqueta: string;
  /** Valor principal (la barra grande). */
  valor: number;
  /** Texto chico junto al nombre («la que estás mirando»). */
  nota?: string;
  destacada?: boolean;
  /** Barras finas debajo de la principal, a la misma escala. */
  extras?: { etiqueta: string; valor: number; color: string }[];
};

export function BarrasHorizontales(props: { filas: FilaBarra[]; color: string; resumen: string }) {
  const { filas, color, resumen } = props;
  const max = filas.reduce((m, f) => Math.max(m, f.valor, ...(f.extras ?? []).map((e) => e.valor)), 0);
  const ancho = (v: number) => (max > 0 ? Math.max(v > 0 ? 1.5 : 0, (v / max) * 100) : 0);
  return (
    <ul className="adb-hbar" aria-label={resumen}>
      {filas.map((f) => (
        <li key={f.id} className={f.destacada ? "adb-hfila adb-hfila-on" : "adb-hfila"} aria-current={f.destacada ? "true" : undefined}>
          <div className="adb-hhead">
            <span className="adb-hnombre">{f.etiqueta}{f.nota && <small>{f.nota}</small>}</span>
            <b className="adb-hvalor">{fmt(f.valor)}</b>
          </div>
          <div className="adb-pista" aria-hidden><div className="adb-relleno" style={{ width: `${ancho(f.valor)}%`, background: color }} /></div>
          {f.extras && f.extras.length > 0 && (
            <div className="adb-extras">
              {f.extras.map((e) => (
                <div key={e.etiqueta} className="adb-extra">
                  <span className="adb-extra-txt">{e.etiqueta}</span>
                  <div className="adb-pista adb-pista-fina" aria-hidden><div className="adb-relleno" style={{ width: `${ancho(e.valor)}%`, background: e.color }} /></div>
                  <b className="adb-extra-num">{fmt(e.valor)}</b>
                </div>
              ))}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

/* ───────────────────────────── barra de progreso ───────────────────────────── */

export function Progreso(props: { etiqueta: string; valor: number; total: number; icono?: ReactNode }) {
  const { etiqueta, valor, total, icono } = props;
  const p = pctNum(valor, total);
  // El color acompaña, no informa solo: el número y el % están escritos.
  const tono = p >= 80 ? "var(--neon)" : p >= 50 ? "var(--amber)" : "var(--pink)";
  return (
    <div className="adb-prog">
      <div className="adb-prog-head">
        <span className="adb-prog-nombre">{icono}{etiqueta}</span>
        <span className="adb-prog-num"><b>{fmt(valor)}</b> de {fmt(total)} · <b>{pct(valor, total)}</b></span>
      </div>
      <div className="adb-pista" role="progressbar" aria-label={etiqueta} aria-valuemin={0} aria-valuemax={100}
           aria-valuenow={Math.round(p)} aria-valuetext={`${fmt(valor)} de ${fmt(total)}, ${pct(valor, total)}`}>
        <div className="adb-relleno" style={{ width: `${p}%`, background: tono }} />
      </div>
    </div>
  );
}
