import type { MetadataRoute } from "next";

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
 * El ambiente lo hornea el build (`APP_ENV`, ver next.config.mjs). Ante la duda
 * —variable vacía, mal seteada— se BLOQUEA: un sitio de pruebas sin indexar no
 * le cuesta nada a nadie, uno indexado por error sí.
 */
export default function robots(): MetadataRoute.Robots {
  const esProd = (process.env.NEXT_PUBLIC_ENV_LABEL || "").toLowerCase() === "prod";
  return esProd
    ? { rules: { userAgent: "*", allow: "/" } }
    : { rules: { userAgent: "*", disallow: "/" } };
}
