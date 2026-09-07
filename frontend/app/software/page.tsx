import Link from "next/link";
import { ciudadActual } from "@/lib/ciudad-server";
import { Nav } from "@/components/nav";
import { WhatsApp, Store, Pin, Search, Send, Play, Verified, TikTok, Arrow, Check } from "@/components/icons";

export const metadata = {
  title: "El software comercial de Bermejo — planes y funciones",
  description: "La plataforma que pone a tu comercio en el mapa de Bermejo: ofertas en vivo, WhatsApp directo, videos y más. Conocé los planes.",
};

const FEATURES = [
  { Icon: Pin, t: "En el mapa", d: "Tu comercio aparece en el mapa con foto, ubicación y cómo llegar." },
  { Icon: WhatsApp, t: "Contacto directo", d: "El comprador te escribe por WhatsApp con un toque — sin intermediarios ni comisiones." },
  { Icon: Send, t: "Ofertas en vivo", d: "Publicás tu oferta y en el momento la ve toda la ciudad." },
  { Icon: Search, t: "Buscador por rubro", d: "Te encuentran buscando lo que vendés: mayorista, minorista, rubro, zona y precio." },
  { Icon: Play, t: "Videos", d: "Mostrá tu local y tus productos con videos estilo TikTok." },
  { Icon: Verified, t: "Verificado", d: "Fuimos, lo vimos y lo confirmamos. No se compra: se verifica en el lugar." },
];

/** El WhatsApp al que escribe un comerciante desde esta página.
 *
 *  Estaba `59170000000` —un placeholder— en los tres botones. No daba error:
 *  abría WhatsApp con un número que no existe, así que cada comerciante que
 *  tocó "Sumar mi negocio" en los últimos meses se topó con la nada y nadie se
 *  enteró. Va el operativo hasta que exista el número de marca. */
const WA_VENTAS = "59164610187";
const waLink = (texto: string) => `https://wa.me/${WA_VENTAS}?text=${encodeURIComponent(texto)}`;

/** Los planes, en el orden en que se sube.
 *
 *  Cada escalón agrega OTRA COSA, no más de lo mismo: existís · publicás vos ·
 *  te mostramos nosotros · te atendemos nosotros. Es lo que hace que el
 *  comerciante entienda por qué sube sin que se lo expliquen.
 *
 *  Los precios están en bolivianos y por mes. El tope de publicaciones es el
 *  eje del primer salto: con 15 incluidas y Bs 5 la extra, el que necesita 29
 *  ya paga lo mismo que Destacado —que le da 100—, así que la cuenta la hace
 *  solo y nadie tiene que empujarlo. */
const PLANES = [
  {
    nombre: "Básico", precio: "Gratis", sub: " el primer mes", destacado: false,
    pie: "Después elegís Publica o Destacado",
    items: [
      "Aparecés en el mapa y en el buscador",
      "Te encuentran buscando lo que vendés",
      "Ficha con WhatsApp, cómo llegar y horario",
      "Tus redes y tus fotos",
    ],
  },
  {
    nombre: "Publica", precio: "Bs 70", sub: "/mes", destacado: false,
    pie: "Publicaciones extra: Bs 5 cada una",
    items: [
      "Todo lo de Básico",
      "15 publicaciones por mes",
      "Publicás mandando un WhatsApp",
      "Ofertas y novedades en tu ficha",
    ],
  },
  {
    nombre: "Destacado", precio: "Bs 140", sub: "/mes", destacado: true,
    pie: "Desde 29 publicaciones ya te conviene éste",
    items: [
      "Todo lo de Publica",
      "50 publicaciones por mes",
      "Destacado en el mapa y en el buscador",
      "Tu oferta en el canal de WhatsApp de URUKU",
    ],
  },
  {
    nombre: "Pro", precio: "Consultá", destacado: false,
    pie: "Escribinos y te contamos cómo funciona",
    items: [
      "Todo lo de Destacado",
      "Atención 24/7 de tu WhatsApp",
      "Contestamos cuando el local está cerrado",
      "No perdés la consulta de la noche ni la del domingo",
    ],
  },
];

/** Lo que se cobra por trabajo hecho y no por mes.
 *
 *  Es la diferencia que sostiene los precios de arriba: un plan compromete algo
 *  todos los meses; esto se cobra una vez, cuando se hizo. Por eso puede tener
 *  precio sin arriesgar nada.
 *
 *  El sello Verificado NO está acá a propósito: hoy significa "fuimos y lo
 *  vimos". El día que signifique "pagó", deja de servirle al comprador — y es
 *  lo único que distingue esto de una lista de Facebook. */
const ADDONS = [
  { Icon: Play, t: "Video de tu local", d: "Vamos, grabamos y editamos. Queda en tu ficha y en las redes de URUKU." },
  { Icon: TikTok, t: "En las redes de URUKU", d: "Tu oferta en el TikTok e Instagram de URUKU. Cupo por semana." },
  { Icon: Store, t: "Te cargamos el catálogo", d: "Nos pasás las fotos y los precios, y lo dejamos publicado." },
  { Icon: Send, t: "Fotos mejoradas", d: "Recortamos, mejoramos y encuadramos las fotos de tu vidriera." },
];

export default async function SoftwarePage() {
  // Esta página le habla a un comerciante de una ciudad concreta: "el mapa de
  // Santa Cruz" convence donde "el mapa de Bermejo" desconcierta. El título de
  // metadata queda fijo porque se resuelve antes de conocer la cookie.
  const { ciudad } = await ciudadActual();
  const nombre = ciudad?.nombre ?? "tu ciudad";
  return (
    <>
      <Nav />
      <section className="hero" style={{ paddingBottom: 20 }}>
        <div className="wrap" style={{ display: "block", textAlign: "center", maxWidth: 820, margin: "0 auto" }}>
          <span className="eyebrow" style={{ justifyContent: "center" }}><span className="dot-live" /> Para comercios de {nombre}</span>
          <h1 className="hero-title" style={{ fontSize: "clamp(40px,6vw,72px)" }}>
            Poné tu comercio<br /><span className="green">en el mapa</span>
          </h1>
          <p className="hero-sub" style={{ margin: "22px auto 30px" }}>
            El que busca algo en {nombre} lo busca acá. Te encuentran por lo que vendés, te
            escriben al WhatsApp y saben cómo llegar, porque tu local está en el mapa.
          </p>
          <div className="hero-cta" style={{ justifyContent: "center" }}>
            <a href={waLink(`Hola URUKU, quiero sumar mi negocio a ${nombre}`)} target="_blank" rel="noopener" className="btn btn-primary">
              <WhatsApp style={{ width: 18, height: 18 }} /> Sumar mi negocio
            </a>
            <a href="#planes" className="btn btn-ghost">Ver planes <Arrow /></a>
          </div>
        </div>
      </section>

      {/* Qué hace */}
      <section className="section" style={{ paddingTop: 40 }}>
        <div className="wrap">
          <div className="section-head"><div><span className="eyebrow">Qué hace</span><h2>Todo lo que tu comercio necesita</h2></div></div>
          <div className="biz-grid" style={{ gridTemplateColumns: "repeat(3,1fr)" }}>
            {FEATURES.map((f) => (
              <div className="glass" key={f.t} style={{ padding: 22, borderRadius: "var(--radius)" }}>
                <span className="ic g" style={{ width: 44, height: 44, borderRadius: 12, display: "grid", placeItems: "center", background: "rgba(57,255,158,.12)", color: "var(--neon)" }}>
                  <f.Icon style={{ width: 22, height: 22 }} />
                </span>
                <h4 style={{ margin: "14px 0 6px", fontSize: 16 }}>{f.t}</h4>
                <p style={{ color: "var(--txt-2)", fontSize: 14, margin: 0 }}>{f.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Cómo funciona */}
      <section className="section" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="explore" style={{ gridTemplateColumns: "1fr" }}>
            <div>
              <span className="eyebrow">Cómo funciona</span>
              <h2>Publicar es mandar un WhatsApp</h2>
              <div className="zone-chips" style={{ gridTemplateColumns: "repeat(3,1fr)", marginTop: 18 }}>
                <div className="zchip"><b>1. Te sumás</b><small>Cargamos tu comercio con tus fotos</small></div>
                <div className="zchip"><b>2. Publicás</b><small>Mandás tu oferta por WhatsApp</small></div>
                <div className="zchip"><b>3. Te encuentran</b><small>Aparecés en el mapa, en las ofertas y en el buscador</small></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Planes */}
      <section className="section" id="planes" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="section-head"><div><span className="eyebrow">Planes</span><h2>Elegí cómo querés aparecer</h2><p>Pago mensual por QR. <b>Sin comisiones por venta</b> — el cliente te escribe a vos y la venta es tuya.</p></div></div>
          <div className="planes-grid">
            {PLANES.map((p) => (
              <div className={`plan-card glass ${p.destacado ? "dest" : ""}`} key={p.nombre}>
                {p.destacado && <span className="plan-badge">Más elegido</span>}
                <h3>{p.nombre}</h3>
                <div className="plan-precio">{p.precio}{p.sub && <small>{p.sub}</small>}</div>
                <ul>
                  {p.items.map((it) => (<li key={it}><Check style={{ width: 15, height: 15, color: "var(--neon)", flexShrink: 0 }} /> {it}</li>))}
                </ul>
                {p.pie && <p style={{ color: "var(--txt-3)", fontSize: 12, margin: "0 0 12px" }}>{p.pie}</p>}
                <a href={waLink(`Hola URUKU, me interesa el plan ${p.nombre}`)} target="_blank" rel="noopener" className={`btn ${p.destacado ? "btn-primary" : "btn-ghost"} btn-sm`} style={{ width: "100%", marginTop: "auto" }}>Elegir</a>
              </div>
            ))}
          </div>
          {/* La promoción va con el nombre puesto. Un 2x1 sin fecha de fin no es
              una promoción: es el precio, y volver al de lista después se lee
              como un aumento. */}
          <div className="glass" style={{ padding: "14px 18px", borderRadius: 14, marginTop: 18, textAlign: "center" }}>
            <b style={{ color: "var(--neon)" }}>Promoción de lanzamiento:</b>{" "}
            pagás un mes y tenés dos.
          </div>
          <p style={{ color: "var(--txt-3)", fontSize: 12.5, marginTop: 14, textAlign: "center" }}>
            Precios en bolivianos, por mes. El pago se hace por QR. Podés cambiar de plan o dar de
            baja cuando quieras.
          </p>
        </div>
      </section>

      {/* Add-ons */}
      <section className="section" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="section-head"><div><span className="eyebrow">Servicios adicionales</span><h2>Lo que no sabés hacer, lo hacemos por vos</h2></div></div>
          <div className="biz-grid" style={{ gridTemplateColumns: "repeat(4,1fr)" }}>
            {ADDONS.map((a) => (
              <div className="glass" key={a.t} style={{ padding: 20, borderRadius: "var(--radius)" }}>
                <a.Icon style={{ width: 26, height: 26, color: "var(--blue-soft)" }} />
                <h4 style={{ margin: "12px 0 6px", fontSize: 15 }}>{a.t}</h4>
                <p style={{ color: "var(--txt-2)", fontSize: 13.5, margin: 0 }}>{a.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="section" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="cta">
            <div><h2>¿Sumamos tu comercio?</h2><p>Escribinos y en minutos estás en el mapa de {nombre}.</p></div>
            <a className="btn btn-primary" href={waLink(`Hola URUKU, quiero sumar mi negocio a ${nombre}`)} target="_blank" rel="noopener">
              <WhatsApp style={{ width: 18, height: 18 }} /> Hablar por WhatsApp
            </a>
          </div>
        </div>
      </section>

      <footer className="footer">
        <div className="wrap">
          <div className="copy">
            <span>© 2026 URUKU</span>
            <Link href="/bermejo" style={{ color: "var(--txt-3)" }}>Acceso equipo</Link>
          </div>
        </div>
      </footer>
    </>
  );
}
