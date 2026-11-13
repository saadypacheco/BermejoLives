// «Comparar y completar» (docs/turismo-home-y-repetidos.md §1): la parte pura de la pantalla, sin red ni
// navegador, para poder probarla con `npm test`.
//
// Un importado (tarjeta o turismo) que se repite con un comercio ya cargado no se promueve como nuevo: se miran los
// dos lado a lado y se COMPLETA el existente. Acá viven: qué le toca a cada campo, el body de `completar`, el rubro
// sugerido, el texto del resultado y los mensajes de error del comparador.

export type Punto = { lat: number; lng: number };
export type ValorCampo = string | Punto | null;
export type SugeridoCampo = "completar" | "conservar" | "igual";

/** Un campo comparado, como lo devuelve `GET /admin/importados/{id}/comparar`. */
export type CampoComparado = {
  campo: string;
  actual: ValorCampo;
  nuevo: ValorCampo;
  sugerido: SugeridoCampo;
};

export type ComercioComparado = {
  id: string; nombre: string; slug: string | null;
  direccion: string | null; telefono: string | null; whatsapp: string | null; sitio_web: string | null;
  email: string | null; horario: string | null; lat: number | null; lng: number | null;
  tiene_foto: boolean; fuente_url: string | null; subcategoria: string | null; verificado: boolean;
};

export type Comparacion = {
  comercio: ComercioComparado;
  campos: CampoComparado[];
  rubro_sugerido: string | null;
  rubros_actuales: string[];
};

/** Lo que se le muestra a quien revisa por cada campo:
 *  - `completa`: el existente está vacío y el importado trae dato: se llena solo, sin elegir.
 *  - `conserva`: los dos tienen dato distinto: queda el actual, salvo que se active «usar el nuevo» (`elegible`).
 *  - `punto-fijo`: el punto del existente no se pisa nunca (lo marcó alguien parado ahí).
 *  - `igual`: los dos dicen lo mismo.
 *  - `sin-dato`: el importado no trae nada para ese campo: el existente queda como está. */
export type AccionCampo = "completa" | "conserva" | "punto-fijo" | "igual" | "sin-dato";

export const ETIQUETAS_CAMPO: Record<string, string> = {
  nombre: "Nombre",
  direccion: "Dirección",
  telefono: "Teléfono",
  whatsapp: "WhatsApp",
  sitio_web: "Web",
  email: "Email",
  horario: "Horario",
  fuente_url: "Página de origen",
  subcategoria: "Tipo",
  punto: "Punto en el mapa",
};

export function etiquetaCampo(campo: string): string {
  return ETIQUETAS_CAMPO[campo] ?? campo;
}

export function esPunto(v: ValorCampo | undefined): v is Punto {
  return !!v && typeof v === "object" && Number.isFinite(v.lat) && Number.isFinite(v.lng);
}

/** ¿El campo trae algo? (texto con contenido, o un punto válido). */
export function tieneValor(v: ValorCampo | undefined): boolean {
  if (v == null) return false;
  if (typeof v === "string") return v.trim() !== "";
  return esPunto(v);
}

/** Qué le toca a un campo. Se apoya en `sugerido` del servidor, pero no confía ciegamente: el punto existente nunca
 *  se pisa y un campo sin dato nuevo no ofrece elección. */
export function accionCampo(c: CampoComparado): AccionCampo {
  const hayActual = tieneValor(c.actual);
  const hayNuevo = tieneValor(c.nuevo);
  if (c.campo === "punto") {
    if (hayActual) return hayNuevo && c.sugerido === "igual" ? "igual" : "punto-fijo";
    return hayNuevo ? "completa" : "sin-dato";
  }
  if (!hayNuevo) return "sin-dato";
  if (!hayActual) return "completa";
  if (c.sugerido === "igual") return "igual";
  return "conserva";
}

/** Sólo los campos con los dos datos distintos dejan elegir «usar el nuevo». El punto nunca. */
export function esElegible(c: CampoComparado): boolean {
  return c.campo !== "punto" && accionCampo(c) === "conserva";
}

/** Los campos que se muestran: los que tienen dato en algún lado. */
export function camposVisibles(campos: readonly CampoComparado[]): CampoComparado[] {
  return campos.filter((c) => tieneValor(c.actual) || tieneValor(c.nuevo));
}

/** El valor para mostrar: texto, o «lat, lng» a 5 decimales; `null` si está vacío. */
export function textoValor(v: ValorCampo | undefined): string | null {
  if (!tieneValor(v)) return null;
  if (typeof v === "string") return v.trim();
  return esPunto(v) ? `${v.lat.toFixed(5)}, ${v.lng.toFixed(5)}` : null;
}

/** La frase corta de cada acción, para la insignia de la fila. */
export function textoAccion(a: AccionCampo, usarNuevo = false): string {
  switch (a) {
    case "completa": return "Se completa";
    case "igual": return "Igual";
    case "punto-fijo": return "Se conserva: el punto actual no se pisa";
    case "sin-dato": return "Se conserva: no hay dato nuevo";
    case "conserva": return usarNuevo ? "Se reemplaza por el nuevo" : "Se conserva el actual";
  }
}

// ── Elecciones y body ────────────────────────────────────────────────────────

/** Los campos con «usar el nuevo» activado (`campo → true`). */
export type Elecciones = Readonly<Record<string, boolean>>;

/** Prende o apaga «usar el nuevo» de un campo (devuelve una copia). */
export function alternarEleccion(e: Elecciones, campo: string): Elecciones {
  return { ...e, [campo]: !e[campo] };
}

export type BodyCompletar = {
  comercio_id: string;
  usar: Record<string, "nuevo">;
  sumar_rubro: boolean;
};

/** El body de `POST /admin/importados/{id}/completar`. Sólo van en `usar` los campos elegibles que la persona
 *  prendió: lo vacío se completa solo en el servidor y el punto no se pisa, así que no viajan. */
export function armarBodyCompletar(
  comercioId: string, campos: readonly CampoComparado[], elecciones: Elecciones, sumarRubro: boolean,
): BodyCompletar {
  const usar: Record<string, "nuevo"> = {};
  for (const c of campos) {
    if (esElegible(c) && elecciones[c.campo]) usar[c.campo] = "nuevo";
  }
  return { comercio_id: comercioId, usar, sumar_rubro: sumarRubro };
}

/** El rubro sugerido sólo se ofrece si hay uno y el comercio todavía no lo tiene. */
export function puedeSumarRubro(sugerido: string | null | undefined, actuales: readonly string[] | null | undefined): boolean {
  const s = (sugerido ?? "").trim();
  return s !== "" && !(actuales ?? []).includes(s);
}

/** La casilla «Sumar el rubro» arranca marcada si el comercio no lo tiene. */
export function sumarRubroPorDefecto(sugerido: string | null | undefined, actuales: readonly string[] | null | undefined): boolean {
  return puedeSumarRubro(sugerido, actuales);
}

/** El resumen de lo que va a pasar, antes de apretar «Completar el existente». */
export function resumenAcciones(
  campos: readonly CampoComparado[], elecciones: Elecciones,
): { completa: string[]; reemplaza: string[] } {
  const completa: string[] = [];
  const reemplaza: string[] = [];
  for (const c of campos) {
    const a = accionCampo(c);
    if (a === "completa") completa.push(etiquetaCampo(c.campo).toLowerCase());
    else if (esElegible(c) && elecciones[c.campo]) reemplaza.push(etiquetaCampo(c.campo).toLowerCase());
  }
  return { completa, reemplaza };
}

export function textoResumen(r: { completa: readonly string[]; reemplaza: readonly string[] }, sumaRubro: boolean): string {
  const partes: string[] = [];
  if (r.completa.length) partes.push(`Se completa: ${r.completa.join(", ")}.`);
  if (r.reemplaza.length) partes.push(`Se reemplaza por el nuevo: ${r.reemplaza.join(", ")}.`);
  if (sumaRubro) partes.push("Se suma el rubro.");
  return partes.length ? partes.join(" ") : "No hay nada para cambiar en el comercio: sólo se cierra este importado.";
}

// ── Resultado ────────────────────────────────────────────────────────────────

/** «Se completó Hotel Plaza: dirección, teléfono». `cambiados` son las claves de campo que devolvió el servidor. */
export function textoCompletado(nombre: string | null | undefined, cambiados: readonly string[] | null | undefined): string {
  const quien = (nombre ?? "").trim() || "el comercio";
  const lista = (cambiados ?? []).map((c) => etiquetaCampo(c).toLowerCase());
  return lista.length ? `Se completó ${quien}: ${lista.join(", ")}.` : `Se completó ${quien}: no había nada para cambiar.`;
}

// ── Repetido: textos y estado ────────────────────────────────────────────────

/** ¿El importado tiene un repetido sin resolver? (sólo se resuelve estando «nuevo»). */
export function repetidoPendiente(i: { estado: string; duplicado_de: string | null | undefined }): boolean {
  return i.estado === "nuevo" && !!i.duplicado_de;
}

/** El título de la columna de lo importado. */
export function tituloColumnaNuevo(fuente: string): string {
  return fuente === "turismo" ? "Lo que trae turismo" : "Lo que trae la tarjeta";
}

export const TITULO_COLUMNA_ACTUAL = "Ya está en URUKU";

/** El nombre del repetido para el aviso: nunca el código. Sin nombre, un texto neutro. */
export function nombreRepetido(i: { duplicado_nombre?: string | null }): string {
  return (i.duplicado_nombre ?? "").trim() || "un comercio ya cargado";
}

export const AVISO_PROMOVER_REPETIDO =
  "Si lo promovés así se crea un segundo comercio con los mismos datos. Mejor completá el existente, o marcá «No es el mismo».";

/** Qué pasó con una llamada del comparador, en texto para quien revisa. */
export function mensajeComparador(e: unknown, porDefecto: string): string {
  const st = (e as { status?: number } | null)?.status;
  if (st === 404) return "No se encontró el comercio (puede estar desactivado) o este servidor todavía no tiene el comparador.";
  if (st === 409) return "Este importado ya no está pendiente. Actualizá la lista.";
  if (e instanceof Error && e.message) return e.message;
  return porDefecto;
}
