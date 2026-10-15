import Link from "next/link";
import { Ic } from "@/components/ic";
import { listaNombres, nombreCorto, type TurnoFarmacia } from "@/lib/turnos-farmacia";

/**
 * «Farmacias de turno hoy: Ángeles y San Miguel → Ver». Para el inicio y la
 * guía. Quien la usa ya sabe si la ciudad tiene turnos: sin farmacias de turno
 * ahora no dibuja nada (una tarjeta que dice «hoy: » y nada más es peor que no
 * tenerla).
 */
export function TarjetaTurnoHoy({ turnos, contenedor = false }: { turnos: TurnoFarmacia[] | null; contenedor?: boolean }) {
  const nombres = (turnos ?? []).map((t) => t.comercios?.nombre).filter((n): n is string => Boolean(n)).map(nombreCorto);
  if (nombres.length === 0) return null;
  const tarjeta = (
    <Link href="/farmacias-de-turno" className="uk-turno-hoy" aria-label={`Farmacias de turno hoy: ${listaNombres(nombres)}. Ver`}>
      <Ic n="turno_farmacia" s={28} />
      <span><b>Farmacias de turno hoy:</b> {listaNombres(nombres)}</span>
      <em>Ver →</em>
    </Link>
  );
  return contenedor ? <div className="uk-container uk-turno-hoy-wrap">{tarjeta}</div> : tarjeta;
}
