import { ImageResponse } from "next/og";
import { cargarFichaBasica } from "@/lib/ficha-data";
import { COLOR, SITE_URL } from "@/lib/marca";
import { esHostPropio } from "@/lib/seo";

/**
 * La imagen que se ve al compartir una ficha (WhatsApp, Facebook, X) y en los
 * resultados de buscadores y asistentes: 1200×630, con el nombre del local, su
 * rubro y su ciudad, y la portada de fondo si la tiene.
 *
 * `next/og` viene con Next (sin dependencia nueva). Next la publica sola como
 * `og:image` de la ficha, con su `og:image:alt`, `width` y `height`.
 *
 * Peso (< 300 kB): `next/og` sólo entrega PNG, y el PNG de una foto a pantalla
 * completa (1200×630) pesa 450-650 kB aun con un velo encima. Por eso la portada
 * NO va de fondo sino como una tarjeta de 300×400 (la miniatura, a su tamaño
 * natural) al costado, y el resto es color plano, que casi no pesa.
 *
 * Tipografía: la de `next/og` (Noto Sans). Poppins (`app/fonts`) sólo existe en
 * WOFF2 y `next/og` lee TTF/OTF/WOFF.
 */
export const alt = "Ficha del comercio en URUKU: nombre, rubro y ciudad";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
/** Edge: en Node, `next/og` falla al cargar su fuente en Windows (ERR_INVALID_URL
 *  en `fileURLToPath`), y así la imagen se puede probar en las máquinas del
 *  equipo. En el VPS (Linux) también andaría `runtime = "nodejs"`. */
export const runtime = "edge";

const MAX_FOTO_BYTES = 600_000;
/** La portada, a su tamaño natural (la miniatura es 300×400): ver «Peso». */
const FOTO_W = 300;
const FOTO_H = 400;

/** Descarga la portada y la devuelve como `data:` (sólo JPEG/PNG: `next/og` no
 *  lee WebP). Ante cualquier falla —sin foto, lenta, enorme, otro formato— `null`
 *  y la imagen sale sin foto: la vista previa nunca tiene que romperse por esto.
 *
 *  La URL la cargó un comercio, así que acá no se confía en ella (SSRF):
 *   - sólo hosts propios (uruku.bo y el host de la API: `esHostPropio`), por https;
 *     `http://localhost` sólo fuera de producción, para trabajar en la máquina;
 *   - `redirect: "error"`: un 30x hacia otro host (o hacia la red interna) corta;
 *   - el `content-length` se mira ANTES de leer el cuerpo, y es obligatorio. */
async function fotoComoDataUri(url: string | null | undefined): Promise<string | null> {
  const u = (url ?? "").trim();
  if (!u) return null;
  let destino: URL;
  try { destino = new URL(u, SITE_URL); } catch { return null; }
  const enDesarrollo = process.env.NODE_ENV !== "production";
  const localOk = enDesarrollo && destino.protocol === "http:" && ["localhost", "127.0.0.1"].includes(destino.hostname);
  if (!localOk && (destino.protocol !== "https:" || !esHostPropio(destino.hostname))) return null;
  try {
    const res = await fetch(destino, { signal: AbortSignal.timeout(2500), redirect: "error" });
    if (!res.ok) return null;
    const tipo = (res.headers.get("content-type") ?? "").split(";")[0].trim().toLowerCase();
    if (tipo !== "image/jpeg" && tipo !== "image/png") return null;
    const largo = Number(res.headers.get("content-length"));
    if (!Number.isFinite(largo) || largo <= 0 || largo > MAX_FOTO_BYTES) { await res.body?.cancel(); return null; }
    const bytes = new Uint8Array(await res.arrayBuffer());
    if (bytes.byteLength === 0 || bytes.byteLength > MAX_FOTO_BYTES) return null;
    let bin = "";
    for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return `data:${tipo};base64,${btoa(bin)}`;
  } catch {
    return null;
  }
}

/** Corta un texto largo con «…» (la imagen no tiene `overflow` amable). */
function recortar(s: string, max: number): string {
  const t = s.trim();
  return t.length <= max ? t : `${t.slice(0, max - 1).trimEnd()}…`;
}

export default async function OgFicha({ params }: { params: { slug: string } }) {
  const f = await cargarFichaBasica(params.slug);
  const nombre = recortar(f?.comercio.nombre ?? "URUKU", 64);
  const queEs = f ? (f.que || f.rubro) : "";
  const ciudad = f?.ciudad.nombre ?? "";
  const linea = [queEs, ciudad].filter(Boolean).join(" · ");
  // La miniatura (300×400, 13-28 KB) pesa poco; la grande sólo si no hay miniatura.
  const miniatura = (f?.comercio as { portada_thumb_url?: string | null } | undefined)?.portada_thumb_url;
  const foto = f ? await fotoComoDataUri(miniatura || f.comercio.portada_url) : null;
  // Nombres largos: letra más chica para que entren en tres renglones.
  const tamano = nombre.length > 44 ? 52 : nombre.length > 28 ? 62 : 74;

  const imagen = new ImageResponse(
    (
      <div style={{ display: "flex", width: "100%", height: "100%", background: COLOR.verdeHondo, color: "#ffffff" }}>
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", flex: 1,
                      padding: `56px ${foto ? 40 : 72}px 52px 72px` }}>
          <div style={{ display: "flex", alignItems: "center", fontSize: 40, fontWeight: 800, letterSpacing: 6 }}>
            URUKU
          </div>

          <div style={{ display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", fontSize: tamano, fontWeight: 800, lineHeight: 1.08 }}>{nombre}</div>
            {linea && (
              <div style={{ display: "flex", marginTop: 28 }}>
                <div style={{ display: "flex", fontSize: 34, fontWeight: 700, color: COLOR.verdeHondo, background: COLOR.fondo,
                              padding: "10px 26px", borderRadius: 999 }}>
                  {recortar(linea, 48)}
                </div>
              </div>
            )}
          </div>

          <div style={{ display: "flex", fontSize: 26, color: COLOR.cielo }}>uruku.bo</div>
        </div>

        {foto && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", width: FOTO_W + 72, paddingRight: 72 }}>
            {/* eslint-disable-next-line @next/next/no-img-element, jsx-a11y/alt-text */}
            <img src={foto} width={FOTO_W} height={FOTO_H}
                 style={{ width: FOTO_W, height: FOTO_H, objectFit: "cover", borderRadius: 28, border: `6px solid ${COLOR.fondo}` }} />
          </div>
        )}
      </div>
    ),
    { ...size },
  );
  // `next/og` pone `immutable, max-age=1 año` y la URL de la imagen NO cambia cuando
  // el comercio cambia el nombre o la portada: sin esto la vista previa vieja
  // quedaría en el caché de Cloudflare y del navegador un año. (Pasarlo en
  // `headers` no sirve: se SUMA al de `next/og` y quedan los dos.)
  return new Response(imagen.body, {
    headers: { "Content-Type": contentType, "Cache-Control": "public, max-age=0, s-maxage=3600, stale-while-revalidate=86400" },
  });
}
