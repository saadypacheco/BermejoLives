import { Ic } from "@/components/ic";
import { fechaLarga } from "@/lib/seo-paginas";

/** «Revisado el 25 de octubre»: cuándo se tocó por última vez el saber de una
 *  sección de /guia o /comprar-en-bermejo (§3.8). Sin fecha legible no dice nada
 *  (nunca inventa una). */
export function Revisado({ iso }: { iso: string | undefined | null }) {
  const f = fechaLarga(iso);
  if (!f) return null;
  return (
    <small className="uk-guia-revisado" style={{ display: "block", opacity: 0.75, margin: "0 0 10px" }}>
      <Ic n="reloj" s={14} /> Revisado el {f}
    </small>
  );
}
