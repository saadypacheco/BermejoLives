import { redirect } from "next/navigation";

/**
 * /software era la landing comercial vieja: otro diseño, otros planes
 * (Publica 15/mes, Destacado con canal de WhatsApp, Pro "consultá") y una
 * promoción de lanzamiento que ya no corre. Contradecía a /planes, que es
 * donde están los planes de verdad. Queda la ruta por los volantes viejos.
 */
export default function SoftwarePage() { redirect("/planes"); }
