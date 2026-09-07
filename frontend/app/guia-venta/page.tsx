"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getAgenteToken } from "@/lib/campo";

/**
 * El guion de venta, para quien está parado en la vereda.
 *
 * POR QUÉ UNA PÁGINA Y NO UN DOCUMENTO
 * ====================================
 * Un archivo en el repo no se lee en la puerta de una ferretería. Esto se abre
 * en el celular, con una mano, mientras el comerciante termina de atender a
 * otro cliente. Por eso está partido en bloques cortos y lo primero que aparece
 * son los treinta segundos, que es lo único que se usa de verdad.
 *
 * POR QUÉ DETRÁS DEL LOGIN DEL AGENTE
 * ===================================
 * Dice cómo responder las objeciones del comerciante. Eso, leído por el
 * comerciante, no es una ayuda: es una lista de trucos usados con él. Va detrás
 * del mismo token que ya usa la app de campo, así que quien sale a la calle ya
 * está logueado y no tiene que acordarse de otra clave.
 */
export default function GuiaVentaPage() {
  const [ok, setOk] = useState<boolean | null>(null);
  useEffect(() => { setOk(Boolean(getAgenteToken())); }, []);

  if (ok === null) return null;
  if (!ok) {
    return (
      <div className="campo-wrap">
        <h1 style={{ fontSize: 22 }}>Guía de venta</h1>
        <p style={{ color: "var(--txt-2)", fontSize: 14 }}>
          Es para el equipo. Entrá desde la app de campo y volvé acá.
        </p>
        <Link className="btn btn-primary" href="/publicar">Ir a la app de campo</Link>
      </div>
    );
  }

  return (
    <div className="campo-wrap" style={{ paddingBottom: 60 }}>
      <span className="eyebrow"><span className="dot-live" /> Interno · equipo URUKU</span>
      <h1 style={{ fontSize: 24, margin: "8px 0 4px" }}>Cómo se ofrece URUKU</h1>
      <p style={{ color: "var(--txt-3)", fontSize: 13, marginTop: 0 }}>
        Abrilo en la vereda. Lo de arriba es lo que se usa; lo de abajo, cuando preguntan.
      </p>

      <Bloque titulo="Los primeros 30 segundos" abierto>
        <p>
          No se abre con quiénes somos. Se abre con <b>lo que le pasa a él todos los días</b>:
        </p>
        <Cita>
          &ldquo;¿Le pasa que la gente entra preguntando si tiene algo, y usted lo tiene pero
          no sabían? Nosotros hacemos que lo encuentren buscando <b>lo que vende</b>, no el
          nombre del local.&rdquo;
        </Cita>
        <p>
          Y ahí <b>le mostrás su propia ficha en el celular</b>, con su foto. No una
          demostración: la suya, que ya está cargada. Ese es el momento que convierte —
          pasa de escuchar una propuesta a mirar algo que ya existe con su cara.
        </p>
        <p className="chico">
          Si todavía no está cargado, cargalo ahí mismo con la app de campo y mostráselo. Son
          dos minutos y cambia la conversación entera.
        </p>
      </Bloque>

      <Bloque titulo="Lo que nadie más le ofrece">
        <ul>
          <li><b>Lo encuentran por lo que vende.</b> Su cartel dice &ldquo;Comercial
            Velásquez&rdquo;; la gente busca &ldquo;zapatillas&rdquo;.</li>
          <li><b>El cliente le escribe a su WhatsApp.</b> Directo, sin intermediarios.</li>
          <li><b>No cobramos comisión por venta.</b> La venta es suya, entera. Es la
            diferencia con todo lo que le van a ofrecer después.</li>
          <li><b>Está en el mapa</b>, con cómo llegar. El que cruza de Aguas Blancas lo
            encuentra sin conocer la ciudad.</li>
        </ul>
      </Bloque>

      <Bloque titulo="Los precios, de memoria">
        <table className="guia-tabla">
          <tbody>
            <tr><td><b>Básico</b></td><td>Gratis</td><td>Mapa, buscador y ficha</td></tr>
            <tr><td><b>Publica</b></td><td>Bs 70</td><td>15 publicaciones/mes · extra Bs 5</td></tr>
            <tr><td><b>Destacado</b></td><td>Bs 140</td><td>100 publicaciones + destacado + canal</td></tr>
            <tr><td><b>Pro</b></td><td>Pronto</td><td>Atención automática — todavía no se vende</td></tr>
          </tbody>
        </table>
        <p><b>Promoción de lanzamiento: paga un mes y tiene dos.</b></p>
        <p className="chico">
          La cuenta que cierra sola: 15 incluidas y Bs 5 la extra. A las 29 publicaciones
          ya paga Bs 140 — el precio de Destacado, que le da 100. No hay que empujarlo,
          hay que mostrarle la cuenta.
        </p>
      </Bloque>

      <Bloque titulo="Las objeciones, y qué contestar">
        <Obj q="&ldquo;Ya tengo Facebook / Instagram.&rdquo;">
          Perfecto, y no compite. En Facebook lo encuentran los que <b>ya</b> lo conocen.
          Acá lo encuentra el que busca zapatillas y no sabe que usted existe. Además su
          Facebook va en la ficha — se suma, no se reemplaza.
        </Obj>
        <Obj q="&ldquo;No tengo tiempo para andar publicando.&rdquo;">
          No hay que entrar a ningún lado: <b>manda la foto por WhatsApp al grupo</b> y
          nosotros la publicamos. Lo mismo que ya hace cuando le manda una foto a un
          cliente.
        </Obj>
        <Obj q="&ldquo;¿Y cuánta gente lo ve?&rdquo;">
          <b>Decir el número real, no inventar.</b> Si es chico, decirlo así: &ldquo;estamos
          arrancando, por eso está gratis y por eso la promoción&rdquo;. El que promete miles
          y no cumple no vuelve a entrar al local.
        </Obj>
        <Obj q="&ldquo;¿Me van a cobrar comisión?&rdquo;">
          No. Nunca. El cliente le escribe directo y usted cobra como siempre. Nosotros no
          nos metemos en la venta.
        </Obj>
        <Obj q="&ldquo;Déjeme pensarlo.&rdquo;">
          Listo — <b>queda cargado gratis igual</b>, no hay que decidir nada hoy. Y ahí se
          deja la ficha andando. El que la ve funcionando una semana vuelve solo; el que
          se siente apurado, no.
        </Obj>
      </Bloque>

      <Bloque titulo="Lo que NO se promete">
        <ul>
          <li><b>No prometer ventas.</b> Prometemos que lo encuentren. Lo que pase después
            depende de su precio y su atención.</li>
          <li><b>No prometer &ldquo;toda Argentina&rdquo;.</b> Lo cierto es Bermejo y los que
            cruzan de Aguas Blancas y Orán. Alcanza, y se puede sostener.</li>
          <li><b>No vender el sello Verificado.</b> Significa que fuimos y lo vimos. Si se
            compra, deja de servirle a nadie.</li>
          <li><b>No prometer el plan Pro.</b> Todavía no existe. Se anota el interés y se
            avisa cuando esté.</li>
        </ul>
      </Bloque>

      <Bloque titulo="Antes de irte del local">
        <ul>
          <li>La ficha cargada, con <b>foto de la vidriera</b>.</li>
          <li>El <b>horario</b>. Es el dato que más falta y el que decide si alguien camina
            hasta ahí. Dos toques en la app.</li>
          <li>El <b>WhatsApp</b> al que quiere que le escriban.</li>
          <li><b>Qué vende</b>, en palabras suyas. De ahí sale que lo encuentren.</li>
          <li>Si va a publicar: <b>armarle el grupo</b> desde el panel, ahí mismo.</li>
        </ul>
      </Bloque>

      <style>{`
        .guia-b { border: 1px solid var(--stroke); border-radius: 14px; margin-top: 12px; overflow: hidden; }
        .guia-b > button { width: 100%; text-align: left; padding: 14px 16px; background: none;
          border: 0; color: var(--txt); font-size: 15px; font-weight: 700; cursor: pointer;
          display: flex; justify-content: space-between; gap: 10px; }
        .guia-b .cuerpo { padding: 0 16px 16px; font-size: 14px; line-height: 1.55; color: var(--txt-2); }
        .guia-b .cuerpo p { margin: 0 0 10px; }
        .guia-b .cuerpo ul { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 7px; }
        .guia-b .chico { font-size: 12.5px; color: var(--txt-3); }
        .guia-cita { border-left: 3px solid var(--neon); padding: 8px 0 8px 12px; margin: 0 0 12px;
          color: var(--txt); font-size: 15px; }
        .guia-obj { margin-bottom: 12px; }
        .guia-obj b.q { display: block; color: var(--txt); margin-bottom: 3px; }
        .guia-tabla { width: 100%; border-collapse: collapse; font-size: 13.5px; margin-bottom: 10px; }
        .guia-tabla td { padding: 6px 4px; border-bottom: 1px solid var(--stroke); vertical-align: top; }
      `}</style>
    </div>
  );
}

function Bloque({ titulo, children, abierto = false }: {
  titulo: string; children: React.ReactNode; abierto?: boolean;
}) {
  // Plegables y cerrados salvo el primero: en la vereda se busca UNA cosa —la
  // objeción que acaban de hacerte— y una página larga obliga a scrollear
  // mientras el otro espera.
  const [ab, setAb] = useState(abierto);
  return (
    <div className="guia-b">
      <button type="button" onClick={() => setAb((v) => !v)}>
        {titulo}<span style={{ color: "var(--txt-3)" }}>{ab ? "−" : "+"}</span>
      </button>
      {ab && <div className="cuerpo">{children}</div>}
    </div>
  );
}

const Cita = ({ children }: { children: React.ReactNode }) => <p className="guia-cita">{children}</p>;

const Obj = ({ q, children }: { q: string; children: React.ReactNode }) => (
  <div className="guia-obj">
    <b className="q" dangerouslySetInnerHTML={{ __html: q }} />
    <span>{children}</span>
  </div>
);
