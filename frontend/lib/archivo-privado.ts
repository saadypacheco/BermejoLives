// Archivos PRIVADOS del admin (comprobantes de pago, foto del trámite de cambio de
// número): el backend ya no los sirve como URL pública, los listados traen una RUTA del
// backend (`/admin/pagos/<id>/comprobante`, `/admin/solicitudes-cambio-numero/<id>/foto`)
// que sólo responde con el Bearer del admin. Un <img src> no manda ese encabezado, así que
// se pide con fetch y se muestra como blob (igual que la foto de la bandeja de WhatsApp).
//
// Acá va la parte pura: qué es una ruta aceptable. La descarga está en lib/api.ts
// (`getArchivoPrivado`) y el dibujo en components/imagen-privada.tsx.

/** Rutas del backend que se piden con Bearer. Todo lo demás no se pide con la credencial del admin. */
const RUTAS_PRIVADAS = [
  /^\/admin\/pagos\/[A-Za-z0-9_-]+\/comprobante$/,
  /^\/admin\/solicitudes-cambio-numero\/[A-Za-z0-9_-]+\/foto$/,
];

/** La ruta del backend a pedir, o null si el valor no es una ruta privada conocida.
 *
 *  Acepta `/admin/...` y también la URL completa del propio backend (`<api>/admin/...`). Nunca otro
 *  origen: el Bearer del admin no se manda a ningún lado que no sea el backend. */
export function rutaPrivada(valor: string | null | undefined, api: string): string | null {
  if (!valor) return null;
  let ruta = valor.trim();
  const base = api.replace(/\/+$/, "");
  if (base && ruta.startsWith(`${base}/`)) ruta = ruta.slice(base.length);
  if (!ruta.startsWith("/")) return null;
  // Sin consulta ni fragmento: las rutas privadas no los llevan.
  return RUTAS_PRIVADAS.some((re) => re.test(ruta)) ? ruta : null;
}
