// /contacto/uruku.vcf: el contacto de URUKU para agendar con un toque. Lo usa
// el botón «Guardar contacto» de /contacto cuando el enlace se abre en el mismo
// celular (ahí no hay QR que escanear).
import { vcardUruku } from "@/lib/contacto";

export const dynamic = "force-static";

export function GET() {
  return new Response(vcardUruku(), {
    headers: {
      "Content-Type": "text/vcard; charset=utf-8",
      "Content-Disposition": 'attachment; filename="URUKU.vcf"',
    },
  });
}
