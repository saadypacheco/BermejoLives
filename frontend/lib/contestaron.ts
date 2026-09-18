// «¿Te contestó?»: los contactos por WhatsApp que el comprador hizo desde
// este navegador, para preguntarle un rato después si le contestaron.
//
// Se guardan acá (localStorage) con el id del lead que devolvió /lead. La
// pregunta la hace <PreguntaContesto/>: cuando la persona vuelve a la
// pestaña o abre otra página, tres minutos o más después del clic. Una
// pregunta por vez, y cada contacto se pregunta una sola vez.
export type ContactoPendiente = { id: string; comercioId: string; nombre: string; en: number; pospuesto?: number };

const CLAVE = "uk-contactos-pendientes";
const ESPERA_MS = 3 * 60 * 1000;         // no antes de 3 minutos: todavía está escribiendo
const VENCE_MS = 3 * 24 * 60 * 60 * 1000; // después de 3 días ya no vale la pena preguntar

export function leerPendientes(): ContactoPendiente[] {
  try {
    const raw = localStorage.getItem(CLAVE);
    const lista = raw ? (JSON.parse(raw) as ContactoPendiente[]) : [];
    return lista.filter((c) => c && c.id && Date.now() - c.en < VENCE_MS);
  } catch { return []; }
}

function guardar(lista: ContactoPendiente[]) {
  try { localStorage.setItem(CLAVE, JSON.stringify(lista.slice(-20))); } catch { /* modo privado */ }
}

export function anotarContacto(id: string, comercioId: string, nombre: string) {
  const lista = leerPendientes().filter((c) => c.id !== id);
  lista.push({ id, comercioId, nombre, en: Date.now() });
  guardar(lista);
}

/** El contacto que toca preguntar ahora, si hay uno. */
export function proximoParaPreguntar(): ContactoPendiente | null {
  const ahora = Date.now();
  return leerPendientes().find((c) => ahora - c.en >= ESPERA_MS && (!c.pospuesto || ahora >= c.pospuesto)) ?? null;
}

export function quitarContacto(id: string) {
  guardar(leerPendientes().filter((c) => c.id !== id));
}

export function posponerContacto(id: string, minutos = 30) {
  guardar(leerPendientes().map((c) => (c.id === id ? { ...c, pospuesto: Date.now() + minutos * 60 * 1000 } : c)));
}
