// El QR de pago de URUKU: lo carga el admin en el backend y esta pantalla lo
// muestra. SIN precios de planes: el monto lo dice URUKU por WhatsApp.

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type QrPagoInfo = {
  disponible: boolean;
  titular: string | null;
  banco: string | null;
  nota: string | null;
  actualizado: string | null;
  huella: string | null;
  whatsapp_comprobante: string;
};

/** Trae los datos del QR. Si el backend no contesta devuelve `null` (la pantalla
 *  muestra «todavía no está cargado», que es lo honesto: no inventa un QR). */
export async function getQrPagoInfo(): Promise<QrPagoInfo | null> {
  try {
    const res = await fetch(`${API}/pago/qr/info`, { next: { revalidate: 300 } });
    if (!res.ok) return null;
    return (await res.json()) as QrPagoInfo;
  } catch {
    return null;
  }
}

/** La imagen del QR; `?v=<huella>` corta la caché cuando el admin sube otra. */
export function urlQrPagoImagen(huella: string | null): string {
  return `${API}/pago/qr/imagen${huella ? `?v=${encodeURIComponent(huella)}` : ""}`;
}

/** «59167671888» → «67 671 888». Si no tiene la forma de Bolivia, lo deja como viene. */
export function numeroLegible(n: string): string {
  const d = n.replace(/\D/g, "");
  return d.length === 11 && d.startsWith("591") ? `${d.slice(3, 5)} ${d.slice(5, 8)} ${d.slice(8)}` : d;
}
