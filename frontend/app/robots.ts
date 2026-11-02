import type { MetadataRoute } from "next";
import { absoluteUrl, ALLOWED_CRAWLERS, BLOCKED_AI_CRAWLERS, BLOCKED_SCRAPERS, PRIVATE_PATHS } from "@/lib/seo";

/**
 * QA no se indexa. Producción sí.
 *
 * POR QUÉ
 * =======
 *
 * Había un `public/robots.txt` con "Allow: /" servido por los DOS ambientes, así
 * que encontralo.store (QA) se indexaba como un sitio duplicado de uruku.bo.
 * Dos problemas, y el segundo es el que importa:
 *
 *   1. Contenido duplicado: Google reparte la autoridad entre los dos dominios
 *      y puede terminar mostrando el de QA en los resultados.
 *   2. Cuando QA tenga una copia de los datos de producción —que es lo que hace
 *      falta para probar con volumen real— los comercios de Bermejo quedarían
 *      publicados y buscables en un dominio que no es el suyo, con su nombre,
 *      su teléfono y su foto.
 *
 * En producción hay tres grupos: los robots permitidos (cada uno con las rutas
 * privadas), los abusivos (Bytespider y los scrapers: todo bloqueado) y `*`.
 * Ojo: Cloudflare puede anteponer su propio bloque y cortar con 403 en el WAF;
 * cambiar este archivo no alcanza sin la tarea O-2 del dueño.
 *
 * El ambiente lo hornea el build (`APP_ENV`, ver next.config.mjs). Ante la duda
 * —variable vacía, mal seteada— se BLOQUEA: un sitio de pruebas sin indexar no
 * le cuesta nada a nadie, uno indexado por error sí.
 */
export default function robots(): MetadataRoute.Robots {
  const esProd = (process.env.NEXT_PUBLIC_ENV_LABEL || "").toLowerCase() === "prod";
  if (!esProd) return { rules: { userAgent: "*", disallow: "/" } };
  // Decisión del dueño (2/11): se permite todo —buscadores, asistentes que visitan
  // a pedido de un usuario y robots de entrenamiento— salvo lo abusivo. Un robot
  // que coincide con un grupo con nombre IGNORA el grupo `*`, así que las rutas
  // privadas se repiten en cada grupo que permite.
  const privadas = [...PRIVATE_PATHS];
  return {
    rules: [
      { userAgent: [...ALLOWED_CRAWLERS], allow: "/", disallow: privadas },
      { userAgent: [...BLOCKED_AI_CRAWLERS, ...BLOCKED_SCRAPERS], disallow: "/" },
      { userAgent: "*", allow: "/", disallow: privadas },
    ],
    sitemap: absoluteUrl("/sitemap.xml"),
  };
}
