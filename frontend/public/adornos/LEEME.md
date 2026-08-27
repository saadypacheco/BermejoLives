# Fotos de los adornos del mapa

Acá van las fotos recortadas de los lapachos. Se referencian desde
`lib/adornos.ts` → `LAPACHOS[<variedad>].foto`.

**Mientras un archivo no esté, el mapa dibuja el lapacho vectorial.** No hay
ícono roto ni hueco: la foto es una mejora, no un requisito.

Nombres esperados:

    lapacho-rosa.webp
    lapacho-amarillo.webp
    lapacho-magenta.webp
    lapacho-blanco.webp

Requisitos (ver la conversación de 2026-08-26):

- **Fondo transparente.** Una foto con cielo azul recortado en rectángulo se ve
  como un sticker pegado sobre el mapa.
- **El tronco tocando el borde inferior.** El adorno se ancla en la base, así
  que si sobra piso el árbol queda flotando sobre la calle.
- **Lado mayor 384 px.** Se muestra a 48 px de ancho; 384 cubre pantallas
  retina al triple y pesa poco.
- **Derechos claros.** Fotos propias o con licencia que permita usarlas. El
  mapa es público.
