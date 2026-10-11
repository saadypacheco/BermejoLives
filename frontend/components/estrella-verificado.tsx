import { Ic } from "@/components/ic";

/** La estrella dorada «Verificado por URUKU»: el comercio tiene un plan pago al
 *  día (o de cortesía). Va junto al nombre. Se identifica por texto —`title` y
 *  `aria-label`— y no sólo por el color. Es la única marca de confianza que se
 *  ve en público: la tilde `verificado` es interna (la pone el admin). */
export const TEXTO_ESTRELLA = "Verificado por URUKU";

export function EstrellaVerificado({ s = 15 }: { s?: number }) {
  return (
    <span className="uk-estrella" role="img" aria-label={TEXTO_ESTRELLA} title={TEXTO_ESTRELLA}>
      <Ic n="estrella" s={s} peso="fill" />
    </span>
  );
}
