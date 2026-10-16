// El armado de una página de manual del lado del servidor: lee el Markdown de
// `content/manuales/<tipo>.md` y, para «Qué es URUKU», suma el contacto con su
// QR. Lo usan /manual/<tipo> y la dirección corta /que-es-uruku, para que las
// dos muestren exactamente lo mismo.
//
// El .md se lee durante `next build` (las dos rutas son estáticas) y queda
// adentro del HTML generado: en producción no se abre ningún archivo.

import { access, readFile } from "node:fs/promises";
import path from "node:path";
import QRCode from "qrcode";
import { ManualPagina } from "@/components/manual/manual-pagina";
import { parsearManual, type Bloque } from "@/lib/manual-md";
import type { TipoManual } from "@/lib/manuales";
import { WA_URUKU_TEXTO, waUruku } from "@/lib/contacto";

export async function PaginaManualServidor({ tipo }: { tipo: TipoManual }) {
  let md: string;
  try {
    md = await readFile(path.join(process.cwd(), "content", "manuales", `${tipo}.md`), "utf8");
  } catch {
    // Sin el archivo no hay manual que mostrar: que el build lo diga en vez de
    // publicar una página vacía.
    throw new Error(`Falta content/manuales/${tipo}.md`);
  }
  const extra = tipo === "uruku" ? await contactoConQr() : undefined;
  const bloques = await sinCapturasFaltantes(parsearManual(md));
  return <ManualPagina tipo={tipo} bloques={bloques} extra={extra} />;
}

/** Saca las capturas cuyo archivo todavía no está en `public/` (el .md puede
 *  nombrar una captura antes de que se saque). Se resuelve en el build, así que
 *  el manual publicado no muestra un ícono de imagen rota; si igual faltara una
 *  en el navegador, `ManualImagen` la esconde. */
async function sinCapturasFaltantes(bloques: Bloque[]): Promise<Bloque[]> {
  const existe = async (src: string) => {
    try { await access(path.join(process.cwd(), "public", ...src.split("/").filter(Boolean))); return true; }
    catch { return false; }
  };
  const out: Bloque[] = [];
  for (const b of bloques) {
    if (b.t === "img") { if (await existe(b.src)) out.push(b); continue; }
    if (b.t === "nota") { out.push({ ...b, c: await sinCapturasFaltantes(b.c) }); continue; }
    if (b.t === "ul" || b.t === "ol") {
      const items = [];
      for (const it of b.items) items.push({ ...it, sub: await sinCapturasFaltantes(it.sub) });
      out.push({ ...b, items });
      continue;
    }
    out.push(b);
  }
  return out;
}

/** El WhatsApp de URUKU con su QR, al final de «Qué es URUKU». Estilos en
 *  línea: tiene que verse igual en la pantalla y en el PDF impreso. */
async function contactoConQr() {
  const enlace = waUruku("Hola, quiero contactar a URUKU");
  const qr = await QRCode.toDataURL(enlace, {
    width: 360, margin: 1, errorCorrectionLevel: "M", color: { dark: "#0f2c33", light: "#ffffff" },
  }).catch(() => null);
  return (
    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 24, maxWidth: 760,
                  margin: "8px auto 48px", padding: "20px 24px", borderRadius: 16,
                  border: "1px solid rgba(29,141,82,.35)", background: "#ffffff", color: "#214533",
                  breakInside: "avoid" }}>
      {qr && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={qr} alt={`QR para escribirle a URUKU por WhatsApp al ${WA_URUKU_TEXTO}`}
             width={160} height={160} style={{ display: "block", borderRadius: 8 }} />
      )}
      <div style={{ flex: "1 1 220px" }}>
        <div style={{ fontSize: 14, opacity: 0.75 }}>WhatsApp de URUKU</div>
        <div style={{ fontSize: 32, fontWeight: 800, letterSpacing: 1 }}>{WA_URUKU_TEXTO}</div>
        <a href={enlace} target="_blank" rel="noopener"
           style={{ display: "inline-block", marginTop: 8, padding: "10px 16px", borderRadius: 12,
                    background: "#1D8D52", color: "#ffffff", fontWeight: 700, textDecoration: "none" }}>
          Escribinos por WhatsApp
        </a>
        <div style={{ fontSize: 14, marginTop: 10, opacity: 0.75 }}>uruku.bo</div>
      </div>
    </div>
  );
}
