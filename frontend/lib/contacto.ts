// El WhatsApp de URUKU para el público: la cara de URUKU con comerciantes y
// compradores. Desde el 7/10/2026 es el 67671888 (el del lanzamiento con la
// prensa); antes era el Anfitrión, 75314737, que sigue impreso en los
// volantes viejos. Si cambia, cambia acá y en ningún otro lado: el home, el
// pie y el volante leen de esta constante. Nunca el 67991916 (va a la API
// oficial de Meta) ni el 64610187 (el Registrador: sólo lee).
export const WA_URUKU = "59167671888";
/** El número como se lee en voz alta y se escribe en pantalla: «67 671 888». */
export const WA_URUKU_TEXTO = `${WA_URUKU.slice(3, 5)} ${WA_URUKU.slice(5, 8)} ${WA_URUKU.slice(8)}`;
export const waUruku = (texto: string) => `https://wa.me/${WA_URUKU}?text=${encodeURIComponent(texto)}`;

/** La tarjeta de contacto de URUKU (vCard 3.0), para el QR de /contacto y el
 *  archivo /contacto/uruku.vcf. Corta a propósito: cuanto más texto lleva, más
 *  denso es el QR y peor se escanea desde la pantalla de otro celular. */
export function vcardUruku(): string {
  return [
    "BEGIN:VCARD",
    "VERSION:3.0",
    "N:;URUKU;;;",
    "FN:URUKU",
    "ORG:URUKU",
    `TEL;TYPE=CELL:+${WA_URUKU}`,
    "URL:https://uruku.bo",
    "END:VCARD",
  ].join("\r\n");
}
