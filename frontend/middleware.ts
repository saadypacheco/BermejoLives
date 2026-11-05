import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Rutas que SIGUEN funcionando en modo captura (relevamiento de campo + gestión).
const PERMITIDAS = ["/publicar", "/autoregistro", "/mi-comercio", "/campo", "/admin", "/proximamente", "/software", "/manual", "/que-es-uruku", "/contacto", "/pagar", "/agentes", "/comprar-en-bermejo", "/terminos", "/privacidad", "/pieza"];

export function middleware(req: NextRequest) {
  // Si el flag no está en "1", el sitio funciona normal.
  if (process.env.NEXT_PUBLIC_MODO_CAPTURA !== "1") return NextResponse.next();

  const { pathname } = req.nextUrl;
  const permitido = PERMITIDAS.some((p) => pathname === p || pathname.startsWith(p + "/"));
  if (permitido) return NextResponse.next();

  // El resto (home, buscar, comercios…) muestra "Próximamente" sin cambiar la URL.
  const url = req.nextUrl.clone();
  url.pathname = "/proximamente";
  return NextResponse.rewrite(url);
}

// Sin pasar por el middleware: los archivos de texto y XML para robots
// (`robots.txt`, `sitemap.xml`, `llms.txt` y cualquier `*.txt`, como la clave de
// IndexNow). En modo captura el rewrite a /proximamente se los tragaba.
// Las exclusiones van ANCLADAS: sin anclar, `api` dejaba afuera `/apiario`, y
// `.*\.txt` cualquier ruta que contuviera ".txt" en el medio; `robots.txt` y
// compañía, con el punto sin escapar, también hubieran dejado pasar `/robotsXtxt`.
//   - `_next/static/`, `_next/image` e `api/`: sólo esa carpeta (o ese segmento).
//   - `favicon.ico`, `robots.txt`, `sitemap.xml`, `llms.txt`: el archivo exacto en la raíz.
//   - `[^/]+\.txt$`: un `.txt` en la raíz (la clave de IndexNow), no en subcarpetas.
export const config = {
  matcher: "/((?!_next/static/|_next/image(?:/|$)|api(?:/|$)|favicon\\.ico$|robots\\.txt$|sitemap\\.xml$|llms\\.txt$|[^/]+\\.txt$).*)",
};
