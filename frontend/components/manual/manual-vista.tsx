// Dibuja un manual ya parseado (lib/manual-md.ts) como elementos de React.
//
// Todo el texto entra como hijo de un elemento, así que React lo escapa solo:
// no hay `dangerouslySetInnerHTML` ni forma de que un .md meta HTML. Un
// componente sin estado ni efectos: sirve igual en el servidor (el HTML que
// llega ya trae el manual completo) y en el navegador.

import { Fragment, type ReactNode } from "react";
import { Ic } from "@/components/ic";
import {
  aplicarMarcas, separarPortada, textoPlano, usaMarca,
  type Bloque, type Inline, type ValoresMarca,
} from "@/lib/manual-md";

function enLinea(xs: Inline[], v: ValoresMarca): ReactNode {
  return aplicarMarcas(xs, v).map((n, i): ReactNode => {
    switch (n.t) {
      case "texto": return <Fragment key={i}>{n.v}</Fragment>;
      case "negrita": return <strong key={i}>{enLinea(n.c, v)}</strong>;
      case "cursiva": return <em key={i}>{enLinea(n.c, v)}</em>;
      case "codigo": return <code key={i}>{enLinea(n.c, v)}</code>;
      default: return null;   // las marcas ya se reemplazaron arriba
    }
  });
}

const CLASE_ALIN = { izq: "mn-izq", centro: "mn-centro", der: "mn-der" } as const;

function Bloques({ bloques, v }: { bloques: Bloque[]; v: ValoresMarca }) {
  // Un `---` al principio, al final o repetido dejaría una hoja en blanco al imprimir.
  const limpios = bloques.filter((b, i, arr) => b.t !== "salto" || (i > 0 && i < arr.length - 1 && arr[i - 1].t !== "salto"));
  return <>{limpios.map((b, i) => <UnBloque key={i} b={b} v={v} />)}</>;
}

function UnBloque({ b, v }: { b: Bloque; v: ValoresMarca }) {
  switch (b.t) {
    // Un segundo `#` en el cuerpo se dibuja como sección: el único h1 de la página es el de la portada.
    case "h1":
    case "h2": return <h2 className="mn-h2">{enLinea(b.c, v)}</h2>;
    case "h3": return <h3 className="mn-h3">{enLinea(b.c, v)}</h3>;
    case "p": return <p className="mn-p">{enLinea(b.c, v)}</p>;
    case "ul":
    case "ol": {
      const Lista = b.t;
      return (
        <Lista className={`mn-lista mn-${b.t}`} {...(b.t === "ol" && b.inicio !== 1 ? { start: b.inicio } : {})}>
          {b.items.map((it, i) => (
            <li key={i}>
              {enLinea(it.c, v)}
              {it.sub.length > 0 && <Bloques bloques={it.sub} v={v} />}
            </li>
          ))}
        </Lista>
      );
    }
    case "tabla":
      return (
        <div className="mn-tabla-caja" role="region" tabIndex={0} aria-label="Tabla">
          <table className="mn-tabla">
            {b.cab && (
              <thead>
                <tr>{b.cab.map((c, i) => <th key={i} scope="col" className={b.alin[i] ? CLASE_ALIN[b.alin[i]!] : undefined}>{enLinea(c, v)}</th>)}</tr>
              </thead>
            )}
            <tbody>
              {b.filas.map((f, i) => (
                <tr key={i}>{f.map((c, k) => <td key={k} data-label={b.cab ? textoPlano(aplicarMarcas(b.cab[k] ?? [], v)) : undefined} className={b.alin[k] ? CLASE_ALIN[b.alin[k]!] : undefined}>{enLinea(c, v)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    case "nota":
      return (
        <aside className="mn-nota">
          <span className="mn-nota-ic"><Ic n="dato" s={20} /></span>
          <div className="mn-nota-txt"><Bloques bloques={b.c} v={v} /></div>
        </aside>
      );
    case "salto": return <hr className="mn-salto" />;
    default: return null;
  }
}

/** El manual completo: portada (su propia hoja al imprimir) y cuerpo. */
export function ManualVista({ bloques, v, etiqueta }: {
  bloques: Bloque[];
  v: ValoresMarca;
  /** «Manual del agente»: la línea chica arriba del título de la portada. */
  etiqueta: string;
}) {
  const { portada, cuerpo } = separarPortada(bloques);
  // En la portada, un renglón del estilo «Para {{NOMBRE}}» sobra si no hay
  // nombre: se saca entero en vez de dejarlo a medias.
  const lugarPortada = portada.filter((b, i) => i === 0 || !((b.t === "p") && usaMarca(b.c, "NOMBRE") && !v.NOMBRE));
  return (
    <article className="mn-hoja">
      {lugarPortada.length > 0 && (
        <header className="mn-portada">
          {/* El logo es un archivo estático de la marca: un <img> común alcanza. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="mn-logo" src="/uruku-horizontal.svg" alt="URUKU" width={4157} height={1343} />
          <p className="mn-etiqueta">{etiqueta}</p>
          {lugarPortada.map((b, i) => (
            b.t === "h1"
              ? <h1 key={i} className="mn-h1">{enLinea(b.c, v)}</h1>
              : <PortadaBloque key={i} b={b} v={v} />
          ))}
        </header>
      )}
      <div className="mn-cuerpo">
        <Bloques bloques={cuerpo} v={v} />
      </div>
    </article>
  );
}

function PortadaBloque({ b, v }: { b: Bloque; v: ValoresMarca }) {
  if (b.t === "p") return <p className="mn-bajada">{enLinea(b.c, v)}</p>;
  return <UnBloque b={b} v={v} />;
}
