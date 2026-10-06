import Link from "next/link";

/** Header mínimo: sólo la marca y un enlace al mapa. Es el de las pantallas
 * de cuenta (Mi comercio, publicar, perfil, guardados, reservas). */
export function Nav() {
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
