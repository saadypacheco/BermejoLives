import Link from "next/link";
import { UrukuShell } from "@/components/uruku-shell";

/**
 * La página que no existe, con la cara del sitio y no la de Next en inglés.
 * Llega gente desde un QR viejo, un enlace mal copiado o un negocio que se
 * dio de baja: lo que necesita es el buscador y la vuelta al inicio, no
 * «This page could not be found».
 */
export default function NotFound() {
  return (
    <UrukuShell showCatnav={false}>
      <div className="uk-container uk-404">
        <p className="uk-404-num">404</p>
        <h1>Esta página no existe</h1>
        <p>
          Puede que el enlace esté mal copiado, o que el negocio ya no esté en URUKU.
          Buscalo arriba, o seguí por acá:
        </p>
        <div className="uk-404-links">
          <Link href="/" className="uk-btn uk-btn-primary">Ir al inicio</Link>
          <Link href="/buscar?vista=mapa" className="uk-btn-ghost">Ver el mapa</Link>
          <Link href="/guia" className="uk-btn-ghost">Guía para tu visita</Link>
        </div>
      </div>
    </UrukuShell>
  );
}
