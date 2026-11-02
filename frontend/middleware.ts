import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Rutas que SIGUEN funcionando en modo captura (relevamiento de campo + gestión).
const PERMITIDAS = ["/publicar", "/autoregistro", "/mi-comercio", "/campo", "/admin", "/proximamente", "/software", "/manual", "/que-es-uruku", "/contacto", "/pagar", "/agentes", "/comprar-en-bermejo"];

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
export const config = {
  matcher: "/((?!_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml|llms.txt|api|.*\\.txt).*)",
};
