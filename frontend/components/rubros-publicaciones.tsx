import Link from "next/link";
import type { FeedItem } from "@/lib/types";

/**
 * Los rubros que HOY tienen algo publicado, como filtros.
 *
 * Existe por una razón concreta: poder mandar UN link con lo que le interesa a
 * alguien. Un mensaje con treinta ofertas de todos los rubros se silencia el
 * primer día; uno que dice «las ofertas de ropa de hoy» y lleva a esas cinco,
 * se abre. Por eso la lista sale de lo que hay publicado y no de los 67 rubros
 * del catálogo: un filtro que lleva a una pantalla vacía es peor que no estar.
 */
export function RubrosDePublicaciones({ items, ruta, activo }: {
  /** TODAS las publicaciones del tipo, sin filtrar: de ahí salen los rubros. */
  items: FeedItem[];
  ruta: "/ofertas" | "/novedades";
  activo?: string | null;
}) {
  const cuenta = new Map<string, { nombre: string; n: number }>();
  for (const p of items) {
    const slug = p.rubro_slug ?? "";
    if (!slug) continue;
    const y = cuenta.get(slug) ?? { nombre: p.rubro_nombre ?? slug, n: 0 };
    cuenta.set(slug, { nombre: y.nombre, n: y.n + 1 });
  }
  // Con un solo rubro no hay nada que elegir y la fila sería decorado.
  if (cuenta.size < 2) return null;
  const rubros = [...cuenta.entries()].sort((a, b) => b[1].n - a[1].n);

  return (
    <div className="uk-pub-rubros">
      <Link href={ruta} className={!activo ? "on" : ""}>
        Todo <b>{items.length}</b>
      </Link>
      {rubros.map(([slug, r]) => (
        <Link key={slug} href={`${ruta}?rubro=${slug}`} className={activo === slug ? "on" : ""}>
          {r.nombre} <b>{r.n}</b>
        </Link>
      ))}
    </div>
  );
}
