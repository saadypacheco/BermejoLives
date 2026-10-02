/**
 * Los íconos que el sitio ya usaba, ahora dibujados con Phosphor.
 *
 * Este archivo tenía un juego de íconos de línea dibujados a mano: una flecha,
 * una lupa, un pin, un marcador. Funcionaban —son SVG, se ven igual en todos
 * los teléfonos— pero eran un SEGUNDO juego de íconos, con otro trazo y otro
 * aire que el de Phosphor duotono que fija el manual. Dos juegos de íconos en
 * la misma pantalla es justamente lo que hace que un sitio no se vea de una
 * sola marca.
 *
 * Así que lo que cambió es el dibujo, no la forma de usarlos: siguen siendo
 * `<Pin style={{ width: 17, height: 17 }} />` en las dieciséis pantallas que
 * ya los llamaban. Para algo nuevo conviene `<Ic n="..." />` de
 * `components/ic.tsx`, que es la puerta del catálogo; esto es el puente para
 * lo que ya estaba escrito.
 *
 * El peso de cada uno está elegido por tamaño, no por gusto: `fill` en lo que
 * se dibuja de 14 px para abajo o adentro de un botón chico, duotono en lo que
 * se ve grande.
 */
import type { SVGProps } from "react";
import { DUOTONO, RELLENO, POR_CLAVE, POR_CLAVE_RELLENO } from "@/lib/iconos-dibujos";

/** Arma un componente a partir de una clave del catálogo.
 *
 *  No pone `width` ni `height`: las pantallas los vienen dando por `style` o
 *  por CSS desde siempre, y ponerle un tamaño acá pisaría ese CSS en los
 *  lugares que no pasan medida. */
function icono(clave: string, peso: "duotone" | "fill" = "duotone") {
  const r = peso === "fill" ? POR_CLAVE_RELLENO[clave] : undefined;
  const d = r !== undefined ? RELLENO[r] : DUOTONO[POR_CLAVE[clave] ?? POR_CLAVE.otros];
  const Cmp = (p: SVGProps<SVGSVGElement>) => (
    <svg viewBox="0 0 256 256" fill="currentColor" aria-hidden {...p}
         dangerouslySetInnerHTML={{ __html: d }} />
  );
  Cmp.displayName = clave;
  return Cmp;
}

export const WhatsApp = icono("whatsapp", "fill");
export const Pin = icono("ubicacion");
export const Verified = icono("verificado", "fill");
export const Play = icono("video_play", "fill");
export const Search = icono("buscar");
export const Send = icono("enviar");
export const Store = icono("comercios");
export const Arrow = icono("seguir");
export const Globe = icono("web");
export const Instagram = icono("instagram", "fill");
export const Facebook = icono("facebook", "fill");
export const TikTok = icono("tiktok", "fill");
export const Phone = icono("telefono");
export const Check = icono("si");
export const X = icono("cerrar");
export const Edit = icono("editar");
export const User = icono("usuario");

/** El marcador de «guardado». Es el único con estado: relleno cuando el
 *  comercio está guardado, duotono cuando no. */
const GuardadoLleno = icono("guardado", "fill");
const GuardadoVacio = icono("guardado");
export const Bookmark = ({ filled, ...p }: SVGProps<SVGSVGElement> & { filled?: boolean }) =>
  filled ? <GuardadoLleno {...p} /> : <GuardadoVacio {...p} />;
