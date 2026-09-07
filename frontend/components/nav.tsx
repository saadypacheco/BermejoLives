import Link from "next/link";
import { Search, Send, User } from "@/components/icons";

/** mapOnly: header minimal (solo marca + link a Mapa), estilo del home. Para
 * pantallas donde no queremos toda la navegación (ej. login de mi-comercio). */
export function Nav({ active, mapOnly = false }: { active?: string; mapOnly?: boolean }) {
  const links = [
    { href: "/", label: "Inicio", key: "inicio" },
    { href: "/buscar", label: "Ofertas", key: "buscar" },
    { href: "/#mapa", label: "Mapa", key: "mapa" },
    // Apuntaba a /comercios/importadora-abc: un comercio de demo escrito a mano.
    // Todo el que tocaba "Negocios" en el menú aterrizaba en la ficha de ese
    // local — o en un 404, según si el slug sobrevivió a la carga real.
    { href: "/buscar", label: "Negocios", key: "negocios" },
    { href: "/#zonas", label: "Categorías", key: "zonas" },
  ];

  if (mapOnly) {
    return (
      <header className="nav">
        <div className="wrap">
          <Link className="brand" href="/">
            {/* El logo y no las letras: es el que está en los carteles y en el
                resto del sitio, y es lo que el comerciante reconoce. */}
            <img src="/logouruku-wordmark.png" alt="URUKU" className="brand-logo" />
            <span>EN EL MAPA</span>
          </Link>
          <div className="nav-actions">
            <Link className="icon-btn" href="/" aria-label="Mapa" title="Mapa" style={{ width: "auto", padding: "0 14px", fontSize: 13, fontWeight: 600 }}>
              Mapa
            </Link>
          </div>
        </div>
      </header>
    );
  }

  return (
    <header className="nav">
      <div className="wrap">
        <Link className="brand" href="/">
          <img src="/logouruku-wordmark.png" alt="URUKU" className="brand-logo" />
          <span>EN EL MAPA</span>
        </Link>
        <nav className="nav-links">
          {links.map((l) => (
            <Link key={l.key} href={l.href} className={active === l.key ? "active" : ""}>
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="nav-actions">
          <Link className="icon-btn" href="/buscar" aria-label="Buscar" title="Buscar"><Search /></Link>
          <Link className="icon-btn" href="/publicar?modo=login" aria-label="Ingresar" title="Ingresar">
            <User />
          </Link>
          <Link className="btn btn-primary btn-sm" href="/publicar?modo=registro">
            Publicá tus ofertas <Send />
          </Link>
        </div>
      </div>
    </header>
  );
}
