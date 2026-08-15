// Parser heurístico de horarios en texto libre (ej. "Lun a Sáb 9–19", "Lun-Sáb 9-20 · Dom 10-14").
// El horario del comercio NO tiene formato garantizado, así que somos CONSERVADORES:
// solo decimos "abierto" o "cerrado" cuando pudimos interpretar días + horas con confianza;
// ante cualquier ambigüedad devolvemos "desconocido" y el caller muestra el texto crudo.

export type EstadoHorario = {
  estado: "abierto" | "cerrado" | "desconocido";
  // minutos hasta el próximo cambio (cierre si está abierto, apertura si está cerrado); null si no aplica
  cierraEn?: number | null;
  abreEn?: number | null;
};

// Lunes=1 … Domingo=7 (así los rangos "vie a lun" se expanden bien); JS getDay: Dom=0.
const DIAS: Record<string, number> = {
  lun: 1, lunes: 1,
  mar: 2, martes: 2,
  mie: 3, miercoles: 3,
  jue: 4, jueves: 4,
  vie: 5, viernes: 5,
  sab: 6, sabado: 6,
  dom: 7, domingo: 7,
};

function norm(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFD").replace(/[̀-ͯ]/g, "") // saca acentos
    .replace(/[–—]/g, "-")                    // en/em dash → guion
    .replace(/\bhs?\b|\bhoras?\b/g, "")               // "hs", "h", "horas"
    .replace(/\s+/g, " ")
    .trim();
}

// "9", "9:30", "09.30" → minutos desde medianoche
function aMinutos(h: string, m?: string): number | null {
  const hh = parseInt(h, 10);
  const mm = m ? parseInt(m, 10) : 0;
  if (isNaN(hh) || hh > 24 || mm > 59) return null;
  return hh * 60 + mm;
}

type Rango = { dias: Set<number>; desde: number; hasta: number };

function diasDeTexto(txt: string): Set<number> | null {
  if (/todos|diario|lun a dom|lunes a domingo/.test(txt)) {
    return new Set([1, 2, 3, 4, 5, 6, 7]);
  }
  const tokens = txt.match(/[a-z]+/g) || [];
  const ordinales: number[] = [];
  for (const t of tokens) if (DIAS[t] != null) ordinales.push(DIAS[t]);
  if (ordinales.length === 0) return null; // sin día explícito
  const esRango = ordinales.length >= 2 && /\ba\b|-/.test(txt);
  if (esRango) {
    const a = ordinales[0];
    let b = ordinales[ordinales.length - 1];
    if (b < a) b += 7; // wrap (ej. "sab a mar")
    const set = new Set<number>();
    for (let d = a; d <= b; d++) set.add(((d - 1) % 7) + 1);
    return set;
  }
  return new Set(ordinales); // días sueltos ("lun, mie, vie")
}

// Extrae todos los rangos horarios de un segmento ya normalizado.
function rangosHorarios(seg: string): Array<{ desde: number; hasta: number }> {
  // "9 a 13" → "9-13" para unificar; pero cuidado de no tocar "lun a vie".
  const s = seg.replace(/(\d{1,2}(?::\d{2})?)\s*a\s*(\d{1,2}(?::\d{2})?)/g, "$1-$2");
  const re = /(\d{1,2})(?:[:.](\d{2}))?\s*-\s*(\d{1,2})(?:[:.](\d{2}))?/g;
  const out: Array<{ desde: number; hasta: number }> = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(s)) !== null) {
    const desde = aMinutos(m[1], m[2]);
    let hasta = aMinutos(m[3], m[4]);
    if (desde == null || hasta == null) continue;
    if (hasta === 0) hasta = 24 * 60;                 // "22-0" → medianoche
    out.push({ desde, hasta });
  }
  return out;
}

/** Interpreta el horario libre y decide si está abierto AHORA. `now` inyectable para tests. */
export function abiertoAhora(horario: string | null | undefined, now: Date = new Date()): EstadoHorario {
  if (!horario || !horario.trim()) return { estado: "desconocido" };
  const texto = norm(horario);

  // Segmentos por · , ; | / salto de línea (cada uno con sus días+horas).
  const segmentos = texto.split(/[·;|\n]+|,(?=\s*[a-z]{3})/).map((x) => x.trim()).filter(Boolean);

  const rangos: Rango[] = [];
  for (const seg of segmentos) {
    const horas = rangosHorarios(seg);
    if (horas.length === 0) continue;
    // Los días se toman del texto sin las horas.
    const soloDias = seg.replace(/\d{1,2}(?:[:.]\d{2})?/g, " ");
    const dias = diasDeTexto(soloDias) ?? new Set([1, 2, 3, 4, 5, 6, 7]); // sin día → asumimos todos
    for (const h of horas) rangos.push({ dias, desde: h.desde, hasta: h.hasta });
  }

  if (rangos.length === 0) return { estado: "desconocido" };

  const ordHoy = now.getDay() === 0 ? 7 : now.getDay();
  const ahora = now.getHours() * 60 + now.getMinutes();

  let cierraEn: number | null = null;
  for (const r of rangos) {
    if (r.dias.has(ordHoy) && ahora >= r.desde && ahora < r.hasta) {
      const falta = r.hasta - ahora;
      cierraEn = cierraEn == null ? falta : Math.min(cierraEn, falta);
    }
  }
  if (cierraEn != null) return { estado: "abierto", cierraEn };

  // Cerrado ahora: buscamos la próxima apertura (hoy más tarde o próximos días).
  let abreEn: number | null = null;
  for (let adelanto = 0; adelanto < 7; adelanto++) {
    const dia = ((ordHoy - 1 + adelanto) % 7) + 1;
    for (const r of rangos) {
      if (!r.dias.has(dia)) continue;
      const base = adelanto * 24 * 60 - ahora;
      const falta = base + r.desde;
      if (falta > 0) abreEn = abreEn == null ? falta : Math.min(abreEn, falta);
    }
  }
  return { estado: "cerrado", abreEn };
}

/** Texto corto para el badge, ej. "Abierto · cierra 19:00" / "Cerrado · abre 9:00". */
export function etiquetaHorario(e: EstadoHorario, now: Date = new Date()): string | null {
  if (e.estado === "desconocido") return null;
  const fmt = (min: number) => {
    const t = new Date(now.getTime() + min * 60000);
    return `${t.getHours()}:${String(t.getMinutes()).padStart(2, "0")}`;
  };
  if (e.estado === "abierto") {
    return e.cierraEn != null && e.cierraEn <= 120 ? `Abierto · cierra ${fmt(e.cierraEn)}` : "Abierto ahora";
  }
  return e.abreEn != null && e.abreEn <= 24 * 60 ? `Cerrado · abre ${fmt(e.abreEn)}` : "Cerrado";
}
