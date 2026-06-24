import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Rutas que SIGUEN funcionando en modo captura (relevamiento de campo + gestión).
const PERMITIDAS = ["/publicar", "/autoregistro", "/mi-comercio", "/campo", "/bermejo", "/admin", "/proximamente", "/software"];

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

export const config = {
  matcher: "/((?!_next/static|_next/image|favicon.ico|robots.txt|api).*)",
};
