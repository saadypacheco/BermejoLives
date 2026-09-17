// El WhatsApp de URUKU para el público: el Anfitrión (75314737, Tigo, el
// Samsung), que es la cara de URUKU con comerciantes y compradores. Está
// decidido en docs/numeros-whatsapp-uruku.md; si algún día cambia, cambia acá
// y en el volante. Nunca el 67991916 (va a la API oficial de Meta) ni el
// 64610187 (el Registrador: sólo lee).
export const WA_URUKU = "59175314737";
export const waUruku = (texto: string) => `https://wa.me/${WA_URUKU}?text=${encodeURIComponent(texto)}`;
