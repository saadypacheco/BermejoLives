// Mapa isométrico conceptual (NO calles reales). CSS hace la animación.
const HEIGHTS = ["low","mid","tall","mid","low","mid","tall","low","mid","tall","mid","low",
  "mid","tall","low","mid","tall","mid","low","mid","tall","mid","low","tall",
  "tall","low","mid","tall","low","mid","mid","tall","low","mid","tall","low"];
const ACCENTS: Record<number, string> = { 2: "neon", 8: "purple", 14: "pink", 21: "neon", 27: "purple", 33: "pink", 6: "neon", 19: "purple" };

export function IsoCity() {
  return (
    <div className="city" id="mapa">
      <div className="glow-floor" />
      <div className="iso">
        <div className="iso-grid">
          {HEIGHTS.map((h, i) => (
            <div className="tile" key={i}>
              <div className={`bld ${h}${ACCENTS[i] ? " " + ACCENTS[i] : ""}`} />
            </div>
          ))}
        </div>
      </div>
      <button className="tag t-purple" style={{ left: "46%", top: "18%" }}>ZONA IMPORTADORAS<small>23 ofertas activas</small></button>
      <button className="tag t-blue" style={{ left: "74%", top: "30%" }}>ZONA MODA<small>35 ofertas activas</small></button>
      <button className="tag t-orange" style={{ left: "86%", top: "50%" }}>CENTRO COMERCIAL<small>18 ofertas activas</small></button>
      <button className="tag t-neon" style={{ left: "40%", top: "55%" }}>MERCADO CAMPESINO<small>12 ofertas activas</small></button>
      <button className="tag t-pink" style={{ left: "48%", top: "74%" }}>GALERÍAS<small>42 ofertas activas</small></button>
    </div>
  );
}
