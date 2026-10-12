"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  listPendientes, listPublicadas, moderar, revisarConIA, type VeredictoIA, login, getToken, clearToken, type PendingPub,
  listTodosComercios, verificarComercio, rechazarComercio,
  editarComercio, type ComercioPorVerificar,
  listSuscripciones, registrarPago, suspenderComercio, activarComercio,
  setConfiable as setConfiable_, listarNumeros, agregarNumero, type NumeroComercio,
  listarGrupos, atarGrupo, soltarGrupo, crearGrupoComercio, type GrupoComercio,
  altasPorDia, type AltasDia,
  rubrosDeComercio, editarRubrosComercio,
  adminListarFotos, adminSubirFoto, adminBorrarFoto, type FotoComercio,
  adminSubirCatalogo, adminQuitarCatalogo,
  adminSubirPortada, adminUsarComoPortada, adminListarDadosDeBaja, adminReactivarComercio, type ComercioDadoDeBaja,
  analizarComercio, type AnalisisIA, type PropuestaIA,
  pendientesAnalisis, analizarTanda, type ResultadoTanda,
  type ComercioSuscripcion, type EstadoSuscripcion,
  listPagosPendientes, confirmarPago, type PagoPendiente,
  asignarPlanComercio, getPlanesAdmin, type PlanAdmin,
  enviarMensajeComercio,
  getEstadisticas, type EstadisticasAdmin,
  getKpis, type Kpis,
  getPesoFotos, optimizarFotos, type PesoFotos, type ResultadoOptimizar,
  ofertasPendientesAnalisis, analizarTandaOfertas, type ResultadoOferta,
  listReclamos, responderReclamo, type Reclamo,
  getReservaloResumen, type ReservaloResumen,
  getReservaloConsultas, responderReservaloConsulta, type ConsultaReservalo,
  listSolicitudesCambioNumero, aprobarSolicitudCambioNumero, rechazarSolicitudCambioNumero, type SolicitudCambioNumero,
  getResumenAdmin, type ResumenAdmin,
} from "@/lib/api";
import { getRubros } from "@/lib/data";
import { datosTope, type TopeFotos } from "@/lib/upload";
import { TopeFotosDialogo, type DecisionTope } from "@/components/tope-fotos-dialogo";
import { AdminMap } from "@/components/admin-map";
import { AdminCalles } from "@/components/admin-calles";
import { PanelVisitas } from "@/components/panel-visitas";
import { LugaresEditor } from "@/components/lugares-editor";
import { AdornosEditor } from "@/components/adornos-editor";
import { ImportadosPanel } from "@/components/importados-panel";
import { AdminCiudadProvider, useAdminCiudad } from "@/components/admin-ciudad";
import { VencimientosPanel } from "@/components/vencimientos-panel";
import { RubrosPanel } from "@/components/rubros-panel";
import { RevisionRubros } from "@/components/revision-rubros";
import { BandejaWhatsApp } from "@/components/bandeja-whatsapp";
import { DifusionPanel } from "@/components/difusion-panel";
import { DemandaPanel } from "@/components/demanda-panel";
import { AsistentePanel } from "@/components/asistente-panel";
import { PlanesPanel } from "@/components/planes-panel";
import { ContactosPanel } from "@/components/contactos-panel";
import { EquipoPanel } from "@/components/equipo-panel";
import { ManualesPanel } from "@/components/admin/manuales-panel";
import { puedo } from "@/lib/api";
import { GenerarClaveComercio } from "@/components/admin/generar-clave";
import { RubroRecalcular } from "@/components/rubro-recalcular";
import { CatalogoPanel } from "@/components/catalogo-panel";
import { ImageLightbox } from "@/components/image-lightbox";
import { FotoPrincipal } from "@/components/foto-principal";
import { CatalogoPdf } from "@/components/catalogo-pdf";
import { TildesSuma, CLAVES_TILDES, type Tildes } from "@/components/tildes-suma";
import { esCatalogoSubido, normalizarEnlace } from "@/lib/catalogo";
import type { Ciudad, Rubro } from "@/lib/types";
import { precioFmt, MODALIDAD_LABEL, comoLlegarHref } from "@/lib/types";
import { EditorHorario, recordarUltimoHorario } from "@/components/editor-horario";
import { Check, X, Edit, Pin, WhatsApp, Verified } from "@/components/icons";
import { Ic } from "@/components/ic";
import { CargasPanel } from "@/components/cargas-panel";
import { AdminShell } from "@/components/admin/admin-shell";
import { Dashboard } from "@/components/admin/dashboard";
import { defSeccion, seccionDeUrl, type SeccionAdmin } from "@/components/admin/secciones";
import { BarraDatos, Carga, CargandoSeccion, ErrorSeccion, mensajeDeError, useCarga } from "@/components/admin/estado-seccion";

/** Los comercios de la ciudad elegida (slug), o todos si no hay ninguna. */
function deCiudad(lista: ComercioPorVerificar[], slug: string | null): ComercioPorVerificar[] {
  return slug ? lista.filter((c) => (c.ciudades?.slug ?? "") === slug) : lista;
}

// El proveedor de la ciudad envuelve al panel entero: la barra de arriba, la
// sección activa y los números del menú leen la misma elección. `useSearchParams`
// (la sección va en la URL: `/admin?s=negocios`) obliga a un límite de Suspense.
export default function AdminPage() {
  return (
    <AdminCiudadProvider>
      <Suspense fallback={<PanelCargando />}>
        <AdminPanel />
      </Suspense>
    </AdminCiudadProvider>
  );
}

function PanelCargando() {
  return (
    <div className="wrap" style={{ maxWidth: 420, paddingTop: 100 }}>
      <CargandoSeccion texto="Abriendo el panel…" />
    </div>
  );
}

function AdminPanel() {
  const { slug: slugCiudad, ciudad, listo: ciudadLista, arrancar: arrancarCiudad } = useAdminCiudad();
  // La sección activa vive en la URL. Cambiarla es `irA`: empuja una entrada al
  // historial (para que Atrás funcione) y `useSearchParams` se entera solo.
  const seccion = seccionDeUrl(useSearchParams().get("s"));
  // Se sabe si hay sesión recién después de leer el token (en el navegador). Sin
  // este paso la pantalla de ingreso aparecía un instante aunque hubiera sesión.
  const [sesionVerificada, setSesionVerificada] = useState(false);
  const [authed, setAuthed] = useState(false);
  // Vacío a propósito: un correo precargado que no es el tuyo se manda igual
  // y da «credenciales incorrectas» sin que nadie mire el campo.
  const [email, setEmail] = useState("");
  const [pass, setPass] = useState("");
  const [err, setErr] = useState("");

  // ── El resumen: lo ÚNICO que se baja al entrar ────────────────────────────
  // Alimenta el Inicio y los números del menú (docs/admin-rediseno.md §4).
  const [resumen, setResumen] = useState<ResumenAdmin | null>(null);
  const [cargandoResumen, setCargandoResumen] = useState(false);
  const [errResumen, setErrResumen] = useState<string | null>(null);
  const pedidoResumen = useRef(0);
  const hayResumen = useRef(false);
  // Si ya se pidió (en camino o bien bajada) la lista de comercios y los rubros:
  // volver a abrir la sección no los vuelve a bajar.
  const comerciosPedidos = useRef(false);
  const rubrosPedidos = useRef(false);
  const vezComercios = useRef(0);

  // ── Los datos de cada sección: se piden cuando se abre, no al entrar ──────
  // Un `useCarga` por recurso (cargando / error / ya llegó) para que cada
  // sección pueda decir «Cargando…» y «No se pudo, Reintentar».
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [items, setItems] = useState<PendingPub[]>([]);
  // La lista COMPLETA de comercios (1.300+ filas): sólo Negocios, Calles y
  // Monitoreo la usan. Se baja la primera vez que se abre una de ellas y queda;
  // volver a bajarla es un pedido explícito («Actualizar»).
  const [comercios, setComercios] = useState<{ items: ComercioPorVerificar[]; truncado: boolean } | null>(null);
  const [rubros, setRubros] = useState<Rubro[]>([]);
  const [suscripciones, setSuscripciones] = useState<ComercioSuscripcion[]>([]);
  const [pagosPendientes, setPagosPendientes] = useState<PagoPendiente[]>([]);
  const [estadisticas, setEstadisticas] = useState<EstadisticasAdmin | null>(null);
  const [reservaloResumen, setReservaloResumen] = useState<ReservaloResumen | null>(null);
  const [reclamos, setReclamos] = useState<Reclamo[]>([]);
  const [consultasReservalo, setConsultasReservalo] = useState<ConsultaReservalo[]>([]);
  const [solicitudesCambioNumero, setSolicitudesCambioNumero] = useState<SolicitudCambioNumero[]>([]);
  // Publicaciones: la cola por aprobar o lo que ya está publicado (para bajarlo).
  const [vistaPub, setVistaPub] = useState<"pendientes" | "publicadas">("pendientes");
  const [cPub, correrPub] = useCarga("No se pudieron cargar las publicaciones");
  const [cComercios, correrComercios] = useCarga("No se pudieron cargar los negocios");
  const [cSusc, correrSusc] = useCarga("No se pudieron cargar las suscripciones");
  const [cPagos, correrPagos] = useCarga("No se pudieron cargar los pagos");
  const [cEstad, correrEstad] = useCarga("No se pudo cargar el monitoreo");
  const [cKpis, correrKpis] = useCarga("No se pudieron cargar los KPIs");
  const [cReclamos, correrReclamos] = useCarga("No se pudieron cargar los reclamos");
  const [cCambio, correrCambio] = useCarga("No se pudieron cargar los cambios de número");
  const [veredictos, setVeredictos] = useState<Record<string, VeredictoIA | "cargando">>({});
  // El tipo corregido a mano, por publicación. El clasificador acierta el
  // caso común; acá se arregla el que no, en el mismo clic que aprueba.
  const [tipos, setTipos] = useState<Record<string, string>>({});
  // El período de los KPIs. 30 días por defecto: es lo que se mira para
  // decidir qué cargar la semana que viene.
  const [diasKpis, setDiasKpis] = useState(30);
  const diasKpisRef = useRef(30);
  diasKpisRef.current = diasKpis;

  const todosLosComercios = comercios?.items ?? [];

  const pedirResumen = useCallback(async (silencioso: boolean) => {
    const n = ++pedidoResumen.current;
    if (!silencioso) { setCargandoResumen(true); setErrResumen(null); }
    try {
      const r = await getResumenAdmin(slugCiudad);
      if (n !== pedidoResumen.current) return;   // llegó uno más nuevo: éste ya no vale
      hayResumen.current = true;
      setResumen(r);
      setErrResumen(null);
    } catch (e) {
      if (n !== pedidoResumen.current) return;
      setErrResumen(mensajeDeError(e, "No se pudo cargar el tablero"));
    } finally {
      if (n === pedidoResumen.current) setCargandoResumen(false);
    }
  }, [slugCiudad]);

  /** Después de una acción que cambia un número del menú (moderar, verificar,
   *  confirmar un pago…): se vuelve a pedir el resumen sin tapar nada. */
  //  Con una pausa: moderar treinta publicaciones seguidas eran treinta
  //  resúmenes completos (la consulta entera más Reservalo); así es uno, cuando
  //  el moderador para.
  const timerNumeros = useRef<ReturnType<typeof setTimeout> | null>(null);
  const refrescarNumeros = useCallback(() => {
    if (timerNumeros.current) clearTimeout(timerNumeros.current);
    timerNumeros.current = setTimeout(() => { timerNumeros.current = null; void pedirResumen(true); }, 1500);
  }, [pedirResumen]);
  useEffect(() => () => { if (timerNumeros.current) clearTimeout(timerNumeros.current); }, []);

  // La sesión se venció en medio de la pantalla: se vuelve al ingreso con el
  // aviso, en vez de dejar el panel dibujado con todo fallando.
  useEffect(() => {
    const vencida = () => {
      // Recarga completa, igual que «Salir»: pagos, reclamos, suscripciones…
      // quedaban en memoria, y en una computadora compartida el que entraba
      // después en la misma pestaña los veía debajo de su propio error.
      clearToken();
      // Con la sección en la que estaba: al volver a entrar sigue ahí.
      const s = new URLSearchParams(window.location.search).get("s");
      window.location.assign(`/admin?sesion=vencida${s ? `&s=${encodeURIComponent(s)}` : ""}`);
    };
    window.addEventListener("uk-sesion-vencida", vencida);
    return () => window.removeEventListener("uk-sesion-vencida", vencida);
  }, []);

  // El valor inicial del selector de ciudad depende del token (la ciudad del
  // usuario): se resuelve cuando hay sesión, ya sea al abrir o tras el login.
  useEffect(() => { if (authed) arrancarCiudad(); }, [authed, arrancarCiudad]);

  useEffect(() => {
    if (getToken()) setAuthed(true);
    else if (new URLSearchParams(window.location.search).get("sesion") === "vencida") {
      setErr("Se venció la sesión. Entrá de nuevo.");
    }
    setSesionVerificada(true);
  }, []);

  // Al entrar se pide el resumen y NADA MÁS. Se repite cuando cambia la ciudad
  // (`pedirResumen` cambia con ella) y, con `ciudadLista`, no se pide con «todas»
  // provisorio antes de saber la ciudad real.
  useEffect(() => {
    if (!authed || !ciudadLista) return;
    void pedirResumen(false);
  }, [authed, ciudadLista, pedirResumen]);

  // Al cambiar de sección se actualizan los números: pudo haber cambiado todo
  // mientras se trabajaba en la anterior. Varios paneles cambian un contador
  // por dentro sin avisar (Vencimientos al guardar una fecha, Recepción al
  // asignar un comercio, el análisis de ofertas, el editor de Negocios), y
  // salir de ellos es el momento natural de ponerlos al día. En el Inicio se
  // pide ya; en las demás, con la pausa de `refrescarNumeros`. Si ya había un
  // resumen se deja a la vista y se cambia por el nuevo cuando llega.
  const seccionPrevia = useRef(seccion);
  useEffect(() => {
    if (seccionPrevia.current === seccion) return;
    seccionPrevia.current = seccion;
    if (!authed || !ciudadLista) return;
    if (seccion === "inicio") void pedirResumen(hayResumen.current);
    else refrescarNumeros();
  }, [seccion, authed, ciudadLista, pedirResumen, refrescarNumeros]);

  // ── Loaders: uno por recurso. Cada uno corre al abrir su sección ──────────

  /** La lista completa de comercios. Sin `forzar`, si ya se bajó no vuelve a
   *  bajarse: es la lista más pesada del panel. */
  const cargarComercios = useCallback((forzar = false) => {
    if (comerciosPedidos.current && !forzar) return;
    comerciosPedidos.current = true;
    const vez = ++vezComercios.current;
    return correrComercios(async () => {
      try {
        const r = await listTodosComercios();
        // Si mientras tanto se pidió otra, vale la última (no una vieja que llegó tarde).
        if (vez === vezComercios.current) setComercios({ items: r.items, truncado: r.truncado });
      } catch (e) {
        // No se bajó: la próxima vez que se abra la sección se vuelve a intentar.
        // Lo que había se queda: vaciarlo borraría la lista por un fallo de red.
        if (vez === vezComercios.current) comerciosPedidos.current = false;
        throw e;
      }
    });
  }, [correrComercios]);

  const cargarRubros = useCallback(() => {
    if (rubrosPedidos.current) return;
    rubrosPedidos.current = true;
    getRubros().then(setRubros).catch(() => { rubrosPedidos.current = false; });
  }, []);

  const cargarPendientes = useCallback(() => correrPub(async () => {
    setItems(await listPendientes("pendiente"));
  }), [correrPub]);

  const cargarSuscripciones = useCallback(() => correrSusc(async () => {
    setSuscripciones(await listSuscripciones());
  }), [correrSusc]);

  const cargarPagos = useCallback(() => correrPagos(async () => {
    setPagosPendientes(await listPagosPendientes());
  }), [correrPagos]);

  const cargarEstadisticas = useCallback(() => correrEstad(async () => {
    // El resumen de Reservalo es un extra: si no contesta, el resto se muestra igual.
    getReservaloResumen().then(setReservaloResumen).catch(() => setReservaloResumen(null));
    setEstadisticas(await getEstadisticas());
  }), [correrEstad]);

  const cargarKpis = useCallback((dias: number) => correrKpis(async () => {
    setKpis(await getKpis(dias));
  }), [correrKpis]);

  const cargarReclamos = useCallback(() => correrReclamos(async () => {
    // Las consultas de Reservalo son de otro servicio: si no contesta, quedan vacías.
    getReservaloConsultas().then(setConsultasReservalo).catch(() => setConsultasReservalo([]));
    setReclamos(await listReclamos());
  }), [correrReclamos]);

  const cargarSolicitudes = useCallback(() => correrCambio(async () => {
    setSolicitudesCambioNumero(await listSolicitudesCambioNumero());
  }), [correrCambio]);

  // Cada sección pide lo SUYO cuando se abre. Las colas de trabajo (publicaciones,
  // pagos, reclamos…) se piden de nuevo cada vez que se abren —tienen que estar
  // al día—; la lista de comercios, no (ver `cargarComercios`).
  useEffect(() => {
    if (!authed) return;
    switch (seccion) {
      case "negocios": cargarComercios(); cargarRubros(); break;
      case "calles": cargarComercios(); break;
      // Los nombres de «Reservas por negocio» salen de la lista de comercios: se
      // baja en segundo plano y los nombres aparecen cuando llega.
      case "monitoreo": cargarEstadisticas(); cargarComercios(); break;
      case "importados": cargarRubros(); break;
      case "publicaciones": cargarPendientes(); break;
      case "suscripciones": cargarSuscripciones(); break;
      case "pagos": cargarPagos(); break;
      case "kpis": cargarKpis(diasKpisRef.current); break;
      case "reclamos": cargarReclamos(); break;
      case "cambio-numero": cargarSolicitudes(); break;
      default: break;   // el resto de las secciones se arma y pide lo suyo adentro
    }
  }, [authed, seccion, cargarComercios, cargarRubros, cargarPendientes, cargarSuscripciones,
      cargarPagos, cargarEstadisticas, cargarKpis, cargarReclamos, cargarSolicitudes]);

  /** Va a otra sección: empuja la URL (`/admin?s=<id>`) al historial. Next 14.1+
   *  integra `history.pushState` con `useSearchParams`, así que no recarga ni
   *  pide nada al servidor. Si ya estás en el Inicio, vuelve a pedir el resumen. */
  const irA = useCallback((s: SeccionAdmin) => {
    if (s === seccion) {
      if (s === "inicio") void pedirResumen(hayResumen.current);
      return;
    }
    window.history.pushState(null, "", s === "inicio" ? "/admin" : `/admin?s=${s}`);
    window.scrollTo({ top: 0 });
  }, [seccion, pedirResumen]);

  function salir() {
    clearToken();
    // Recarga completa: así no queda en memoria nada de la sesión que se cierra.
    window.location.assign("/admin");
  }

  async function doConfirmarPago(pagoId: string, meses: number, plan?: string) {
    setPagosPendientes((prev) => prev.filter((p) => p.id !== pagoId)); // optimista
    try { await confirmarPago(pagoId, meses, plan); void cargarSuscripciones(); }
    catch (e) {
      // Volvía a aparecer el pago sin decir por qué (p. ej. «El plan «x» no existe»).
      void cargarPagos();
      alert(e instanceof Error && e.message ? `No se pudo confirmar el pago: ${e.message}` : "No se pudo confirmar el pago.");
    }
    refrescarNumeros();
  }

  async function doResponderReclamo(id: string, respuesta: string) {
    try { await responderReclamo(id, respuesta); void cargarReclamos(); refrescarNumeros(); } catch { alert("No se pudo responder"); }
  }

  async function doAprobarSolicitud(id: string) {
    try { await aprobarSolicitudCambioNumero(id); void cargarSolicitudes(); refrescarNumeros(); } catch { alert("No se pudo aprobar"); }
  }

  async function doRechazarSolicitud(id: string) {
    try { await rechazarSolicitudCambioNumero(id); void cargarSolicitudes(); refrescarNumeros(); } catch { alert("No se pudo rechazar"); }
  }

  async function doResponderConsultaReservalo(id: number, respuesta: string) {
    try { await responderReservaloConsulta(id, respuesta); void cargarReclamos(); refrescarNumeros(); } catch { alert("No se pudo responder"); }
  }

  async function actComercio(id: string, accion: "verificar" | "rechazar") {
    // La lista y el contador salen de `comercios`: es la única fuente. (Hubo una
    // segunda lista, sólo de pendientes, y actualizar una sola era el bug: el
    // backend guardaba el cambio pero la tarjeta seguía ahí, así que el botón
    // parecía no hacer nada.)
    setComercios((prev) => prev && { ...prev, items: accion === "rechazar"
      // rechazar = activo:false en la BD, y el listado trae sólo activos → desaparece
      ? prev.items.filter((c) => c.id !== id)
      // verificar = el negocio sigue en la lista, cambia de estado (mueve los chips)
      : prev.items.map((c) => (c.id === id ? { ...c, verificado: true } : c)) });
    try {
      accion === "verificar" ? await verificarComercio(id) : await rechazarComercio(id);
    } catch (e) {
      void cargarComercios(true);   // falló el server: volvemos a la verdad de la BD
      // Sin permiso (403) o sin red: se dice, no se deja la tarjeta volviendo sola.
      alert(mensajeDeError(e, accion === "rechazar" ? "No se pudo dar de baja el negocio" : "No se pudo verificar el negocio"));
    }
    refrescarNumeros();
  }

  async function doSuspender(id: string) {
    setSuscripciones((prev) => prev.map((c) => c.id === id ? { ...c, suspendido: true, suscripcion_estado: "suspendido" } : c));
    try { await suspenderComercio(id); } catch { void cargarSuscripciones(); }
    refrescarNumeros();
  }

  async function doActivar(id: string) {
    setSuscripciones((prev) => prev.map((c) => c.id === id ? { ...c, suspendido: false, suscripcion_estado: c.plan_cortesia ? "cortesia" : "activo" } : c));
    try { await activarComercio(id); } catch { void cargarSuscripciones(); }
    refrescarNumeros();
  }

  async function doLogin(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      await login(email, pass);
      // El aviso de «sesión vencida» ya cumplió: fuera de la URL, sin perder la sección.
      const q = new URLSearchParams(window.location.search);
      if (q.has("sesion")) { q.delete("sesion"); window.history.replaceState(null, "", `/admin${q.toString() ? `?${q}` : ""}`); }
      // Sin cargar nada acá: al haber sesión, el efecto de arriba pide el resumen.
      setAuthed(true);
    } catch {
      setErr("Credenciales incorrectas. ¿Está corriendo el backend?");
    }
  }

  async function act(id: string, estado: string) {
    const motivo = estado === "rechazado" || estado === "cambios" ? prompt("Motivo (opcional):") ?? undefined : undefined;
    const tipo = tipos[id];                       // lo que corrigió el moderador, si tocó algo
    setItems((prev) => prev.filter((p) => p.id !== id)); // optimista
    try {
      await moderar(id, estado, motivo, tipo);
      refrescarNumeros();
    } catch {
      void cargarPendientes(); // revertir si falla
    }
  }

  // La IA sugiere; el moderador confirma con los botones. Nunca aprueba sola.
  async function revisarIA(p: PendingPub) {
    setVeredictos((v) => ({ ...v, [p.id]: "cargando" }));
    try {
      const r = await revisarConIA(p.id, p.titulo ?? "", p.descripcion);
      setVeredictos((v) => ({ ...v, [p.id]: r }));
    } catch {
      setVeredictos((v) => ({ ...v, [p.id]: { veredicto: "dudoso", motivo: "No se pudo consultar la IA.", confianza: 0 } }));
    }
  }

  // Revisa con IA toda la cola y aprueba automáticamente solo lo que la IA marca
  // "aprobar" con confianza alta; el resto queda para revisión humana.
  async function revisarTodoIA() {
    const pendientes = [...items];
    for (const p of pendientes) {
      const r = await revisarConIA(p.id, p.titulo ?? "", p.descripcion).catch(() => null);
      if (r) setVeredictos((v) => ({ ...v, [p.id]: r }));
      if (r && r.veredicto === "aprobar" && r.confianza >= 0.8) {
        setItems((prev) => prev.filter((x) => x.id !== p.id));
        await moderar(p.id, "aprobado").catch(() => {});
      }
    }
    refrescarNumeros();
  }

  if (!sesionVerificada) return <PanelCargando />;

  if (!authed) {
    return (
      <div className="wrap" style={{ maxWidth: 420, paddingTop: 100 }}>
        <Link className="brand" href="/" style={{ marginBottom: 30, display: "inline-flex" }}>
          <b style={{ fontSize: 22, letterSpacing: ".02em" }}>URU<i style={{ color: "var(--neon)", fontStyle: "normal" }}>KU</i></b>
        </Link>
        <h1 style={{ fontSize: 26, marginBottom: 6 }}>Panel de URUKU</h1>
        <p style={{ color: "var(--txt-3)", marginBottom: 24 }}>Comercios, publicaciones y contenido del sitio.</p>
        <form onSubmit={doLogin} className="glass" style={{ padding: 22, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <input className="adm-input" type="email" inputMode="email" autoCapitalize="none"
                 autoCorrect="off" spellCheck={false} autoComplete="username"
                 value={email} onChange={(e) => setEmail(e.target.value)} placeholder="tunombre@uruku.bo" />
          <input className="adm-input" type="password" value={pass} onChange={(e) => setPass(e.target.value)} placeholder="Contraseña" />
          {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
          <button className="btn btn-primary" type="submit">Entrar</button>
        </form>
      </div>
    );
  }

  // El permiso de la sección que dice la URL. El menú ya no la muestra sin
  // permiso, pero alguien puede llegar con el enlace: sin esto vería un panel
  // que sólo da 403.
  const defActual = defSeccion(seccion);
  const permitida = !defActual.permiso || puedo(defActual.permiso);
  const datosComercios = deCiudad(todosLosComercios, slugCiudad);

  return (
    <AdminShell seccion={seccion} onIr={irA} pendientes={resumen?.pendientes ?? null} onSalir={salir}>
      {!permitida && (
        <div className="panel-card glass ash-estado" role="alert">
          <span className="ash-estado-txt"><Ic n="seguridad" s={20} /> No tenés permiso para entrar a esta sección.</span>
          <button type="button" className="btn btn-primary btn-sm ash-btn-grande" onClick={() => irA("inicio")}>Ir al Inicio</button>
        </div>
      )}

      {permitida && seccion === "inicio" && (
        <Dashboard resumen={resumen} cargando={cargandoResumen || !ciudadLista} error={errResumen}
                   onIr={irA} onRecargar={() => { void pedirResumen(false); }}
                   ciudadNombre={ciudad?.nombre ?? null} />
      )}

      {/* Con `ciudadLista`: antes de resolver la ciudad inicial, «todas» es sólo
          un valor provisorio y no hay que consultar nada con él. */}
      {permitida && seccion === "lugares" && ciudadLista && <LugaresEditor ciudad={ciudad} />}
      {permitida && seccion === "adornos" && ciudadLista && <AdornosEditor ciudad={ciudad} />}
      {permitida && seccion === "catalogo" && <CatalogoPanel />}
      {permitida && seccion === "rubros" && <RubrosPanel />}
      {permitida && seccion === "revision-rubros" && <RevisionRubros />}
      {permitida && seccion === "whatsapp" && <BandejaWhatsApp />}
      {permitida && seccion === "difusion" && <DifusionPanel />}
      {permitida && seccion === "demanda" && <DemandaPanel />}
      {permitida && seccion === "ayuda" && <AsistentePanel />}
      {permitida && seccion === "planes" && <PlanesPanel />}
      {permitida && seccion === "compradores" && <ContactosPanel />}
      {permitida && seccion === "equipo" && <EquipoPanel />}
      {permitida && seccion === "manuales" && <ManualesPanel />}
      {permitida && seccion === "cargas" && ciudadLista && <CargasPanel />}
      {permitida && seccion === "importados" && ciudadLista && <ImportadosPanel rubros={rubros} ciudad={ciudad} />}
      {permitida && seccion === "vencimientos" && <VencimientosPanel />}

      {permitida && seccion === "negocios" && (
        ciudadLista ? (
          <Carga estado={cComercios} onReintentar={() => { void cargarComercios(true); }} que="los negocios">
            <BarraDatos texto={`${todosLosComercios.length.toLocaleString("es-BO")} negocios bajados`}
                        cargando={cComercios.cargando} onActualizar={() => { void cargarComercios(true); }} />
            <TabComercios
              todos={todosLosComercios}
              truncado={comercios?.truncado ?? false}
              rubros={rubros}
              onVerificar={(id) => actComercio(id, "verificar")}
              onRechazar={(id) => actComercio(id, "rechazar")}
              onEdited={() => { void cargarComercios(true); }}
              onIrCalles={() => irA("calles")}
            />
          </Carga>
        ) : <CargandoSeccion texto="Cargando la ciudad…" />
      )}

      {/* «Calles y horarios»: antes un botón escondido dentro de Negocios. Recibe
          los comercios de la ciudad y no los filtrados: el buscador y los chips
          de Negocios sirven para encontrar UN comercio, y acá importa la calle
          entera. */}
      {permitida && seccion === "calles" && (
        ciudadLista ? (
          <Carga estado={cComercios} onReintentar={() => { void cargarComercios(true); }} que="los negocios">
            <BarraDatos texto={`${datosComercios.length.toLocaleString("es-BO")} negocios${slugCiudad ? " de la ciudad" : ""}`}
                        cargando={cComercios.cargando} onActualizar={() => { void cargarComercios(true); }}
                        aviso={comercios?.truncado ? `El panel trajo ${todosLosComercios.length} negocios y hay más: faltan calles y comercios en esta vista.` : null} />
            <div className="panel-card glass">
              <AdminCalles comercios={datosComercios} onCambio={() => { void cargarComercios(true); }} />
            </div>
          </Carga>
        ) : <CargandoSeccion texto="Cargando la ciudad…" />
      )}

      {permitida && seccion === "suscripciones" && (
        <Carga estado={cSusc} onReintentar={() => { void cargarSuscripciones(); }} que="las suscripciones">
          <TabSuscripciones
            items={suscripciones}
            onSuspender={doSuspender}
            onActivar={doActivar}
            onPago={() => { void cargarSuscripciones(); refrescarNumeros(); }}
          />
        </Carga>
      )}

      {permitida && seccion === "pagos" && (
        <Carga estado={cPagos} onReintentar={() => { void cargarPagos(); }} que="los pagos">
          <TabPagos items={pagosPendientes} onConfirmar={doConfirmarPago} />
        </Carga>
      )}

      {permitida && seccion === "monitoreo" && (
        <Carga estado={cEstad} onReintentar={() => { void cargarEstadisticas(); }} que="el monitoreo">
          <TabMonitoreo data={estadisticas} reservalo={reservaloResumen} comercios={todosLosComercios}
                        comerciosListos={cComercios.listo} />
        </Carga>
      )}

      {permitida && seccion === "kpis" && (
        <Carga estado={cKpis} onReintentar={() => { void cargarKpis(diasKpis); }} que="los KPIs">
          <TabKpis data={kpis} dias={diasKpis}
                   onDias={(d) => { setDiasKpis(d); setKpis(null); void cargarKpis(d); }} />
        </Carga>
      )}

      {permitida && seccion === "reclamos" && (
        <Carga estado={cReclamos} onReintentar={() => { void cargarReclamos(); }} que="los reclamos">
          <TabReclamos
            reclamos={reclamos}
            consultasReservalo={consultasReservalo}
            onResponderReclamo={doResponderReclamo}
            onResponderConsulta={doResponderConsultaReservalo}
          />
        </Carga>
      )}

      {permitida && seccion === "cambio-numero" && (
        <Carga estado={cCambio} onReintentar={() => { void cargarSolicitudes(); }} que="los cambios de número">
          <TabCambioNumero items={solicitudesCambioNumero} onAprobar={doAprobarSolicitud} onRechazar={doRechazarSolicitud} />
        </Carga>
      )}

      {permitida && seccion === "publicaciones" && <AnalisisOfertas />}
      {permitida && seccion === "publicaciones" && (
        <div role="group" aria-label="Qué publicaciones ver" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          {([["pendientes", `Pendientes (${items.length})`], ["publicadas", "Publicadas"]] as const).map(([k, label]) => (
            <button key={k} type="button" aria-pressed={vistaPub === k} onClick={() => setVistaPub(k)}
              style={{ padding: "5px 16px", minHeight: 44, borderRadius: 20, border: "1px solid", cursor: "pointer", fontSize: 13.5,
                borderColor: vistaPub === k ? "var(--neon)" : "var(--border)",
                background: vistaPub === k ? "var(--neon)22" : "transparent",
                color: vistaPub === k ? "var(--neon)" : "var(--txt-2)", fontWeight: vistaPub === k ? 600 : 400 }}>
              {label}
            </button>
          ))}
        </div>
      )}
      {permitida && seccion === "publicaciones" && vistaPub === "publicadas" && (
        <PublicadasPanel onBajada={refrescarNumeros} />
      )}
      {permitida && seccion === "publicaciones" && vistaPub === "pendientes" && (
      <Carga estado={cPub} onReintentar={() => { void cargarPendientes(); }} que="las publicaciones">
      <div className="panel-card glass">
        <div className="ph" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
          <div><h3>Cola de aprobación</h3><span style={{ color: "var(--txt-3)", fontSize: 13 }}>Aprobá, rechazá o pedí cambios</span></div>
          {items.length > 0 && (
            <button className="btn btn-ghost btn-sm" onClick={revisarTodoIA} title="La IA revisa todas y aprueba automáticamente solo las de alta confianza; el resto queda para vos.">
              <Ic n="destacado" s={15} /> Revisar todas con IA
            </button>
          )}
        </div>
        {items.length === 0 && (
          <div className="mod-item" style={{ justifyContent: "center", color: "var(--txt-3)" }}>
            No hay publicaciones pendientes.
          </div>
        )}
        {items.map((p) => (
          <div className="mod-item" key={p.id}>
            <img src={p.imagen_url ?? "https://picsum.photos/seed/ph/240/168"} alt="" />
            <div>
              <h4>{p.comercios?.nombre ?? "Comercio"} · <span style={{ textTransform: "capitalize", color: "var(--blue-soft)" }}>{p.tipo}</span></h4>
              <p>{p.descripcion ?? p.titulo}</p>
              <div className="mm">
                {p.precio != null && <span style={{ color: "var(--neon)", fontWeight: 700 }}>{precioFmt(p.precio, p.moneda)}</span>}
                {p.tiktok_url && <span><Ic n="videos" s={13} /> TikTok adjunto</span>}
                <span><Ic n="reloj" s={13} /> {new Date(p.created_at).toLocaleString("es-BO")}</span>
                <IdentidadBadge pub={p} />
              </div>
              {(() => {
                // El veredicto vivo (recién pedido a mano) manda; si no hay,
                // el guardado en la fila. Antes sólo existía el primero y se
                // perdía al recargar: la IA opinaba después de que ya había
                // mirado una persona.
                const v = veredictos[p.id]
                  ?? (p.ia_veredicto
                        ? { veredicto: p.ia_veredicto, motivo: p.ia_motivo ?? "", confianza: p.ia_confianza ?? 0 }
                        : undefined);
                if (!v) return null;
                if (v === "cargando") return <div style={{ marginTop: 8, fontSize: 12, color: "var(--txt-3)" }}><Ic n="destacado" s={13} /> Consultando IA…</div>;
                const color = v.veredicto === "aprobar" ? "var(--neon)" : v.veredicto === "rechazar" ? "var(--pink)" : "var(--amber)";
                const label = v.veredicto === "aprobar" ? "IA sugiere aprobar" : v.veredicto === "rechazar" ? "IA sugiere rechazar" : "IA: revisión humana";
                return (
                  <div style={{ marginTop: 8, fontSize: 12, color, border: `1px solid ${color}`, borderRadius: 8, padding: "4px 8px", display: "inline-block" }}>
                    <b>{label}</b>{v.confianza > 0 && <span style={{ opacity: 0.7 }}> · {Math.round(v.confianza * 100)}%</span>}
                    {v.motivo && <span style={{ display: "block", color: "var(--txt-3)", marginTop: 2 }}>{v.motivo}</span>}
                  </div>
                );
              })()}
            </div>
            <div className="mod-actions">
              {/* Lo que decide el clasificador es lo que el comprador ve: una
                  novedad entre las ofertas ensucia la pantalla de Ofertas.
                  Acá se corrige antes de aprobar. */}
              <select className="adm-input" style={{ width: "auto", fontSize: 12, padding: "4px 6px" }}
                      title="Qué es esto: oferta, novedad o video"
                      value={tipos[p.id] ?? p.tipo ?? "oferta"}
                      onChange={(e) => setTipos((t) => ({ ...t, [p.id]: e.target.value }))}>
                <option value="oferta">Oferta</option>
                <option value="novedad">Novedad</option>
                <option value="video">Video</option>
              </select>
              <button className="mbtn" title="Revisar con IA" onClick={() => revisarIA(p)} disabled={veredictos[p.id] === "cargando"}><Ic n="destacado" s={16} /></button>
              <button className="mbtn approve" title="Aprobar" onClick={() => act(p.id, "aprobado")}><Check style={{ width: 18, height: 18 }} /></button>
              <button className="mbtn edit" title="Solicitar cambios" onClick={() => act(p.id, "cambios")}><Edit style={{ width: 18, height: 18 }} /></button>
              <button className="mbtn reject" title="Rechazar" onClick={() => act(p.id, "rechazado")}><X style={{ width: 18, height: 18 }} /></button>
            </div>
          </div>
        ))}
      </div>
      </Carga>
      )}
    </AdminShell>
  );
}

/** Las ofertas, videos y novedades que YA están publicadas (estado «aprobado»),
 *  para poder bajar una que no tendría que verse. «Bajar» pide el motivo y la pasa
 *  a «rechazado»: sale del feed, de la ficha y de /ofertas. */
function PublicadasPanel({ onBajada }: { onBajada: () => void }) {
  const [lista, setLista] = useState<PendingPub[] | null>(null);
  const [total, setTotal] = useState(0);
  const [err, setErr] = useState("");
  const [busqueda, setBusqueda] = useState("");     // lo que escribe la persona
  const [q, setQ] = useState("");                   // lo que se pide (con debounce)
  const [masCargando, setMasCargando] = useState(false);
  const [errMas, setErrMas] = useState("");
  const [bajando, setBajando] = useState<string | null>(null);   // la que tiene el motivo abierto
  const [motivo, setMotivo] = useState("");
  const [enCurso, setEnCurso] = useState(false);
  const [errBaja, setErrBaja] = useState("");
  // Descarta respuestas viejas: si se escribe rápido, sólo vale la última búsqueda.
  const pedido = useRef(0);

  // Espera a que la persona deje de escribir antes de pedir.
  useEffect(() => {
    const t = setTimeout(() => setQ(busqueda.trim()), 350);
    return () => clearTimeout(t);
  }, [busqueda]);

  const cargar = useCallback(() => {
    const mio = ++pedido.current;
    setErr(""); setErrMas("");
    listPublicadas(q, 0)
      .then((r) => { if (mio === pedido.current) { setLista(r.items); setTotal(r.total); } })
      .catch((e) => { if (mio === pedido.current) setErr(mensajeDeError(e, "No se pudieron cargar las publicadas")); });
  }, [q]);
  useEffect(() => { cargar(); }, [cargar]);

  async function verMas() {
    if (!lista || masCargando) return;
    const mio = pedido.current;
    setMasCargando(true); setErrMas("");
    try {
      const r = await listPublicadas(q, lista.length);
      if (mio !== pedido.current) return;
      setLista((prev) => {
        const vistos = new Set((prev ?? []).map((x) => x.id));
        return [...(prev ?? []), ...r.items.filter((x) => !vistos.has(x.id))];
      });
      setTotal(r.total);
    } catch (e) {
      setErrMas(mensajeDeError(e, "No se pudieron cargar más"));
    } finally { setMasCargando(false); }
  }

  async function bajar(p: PendingPub) {
    if (!motivo.trim()) { setErrBaja("Escribí el motivo: queda registrado."); return; }
    setErrBaja(""); setEnCurso(true);
    try {
      await moderar(p.id, "rechazado", motivo.trim());
      setLista((prev) => prev?.filter((x) => x.id !== p.id) ?? prev);
      setTotal((t) => Math.max(0, t - 1));
      setBajando(null); setMotivo("");
      onBajada();
    } catch (e) {
      // Queda abierta, con lo escrito: no se pierde el motivo por un corte de red.
      setErrBaja(mensajeDeError(e, "No se pudo bajar la publicación"));
    } finally { setEnCurso(false); }
  }

  if (err) return <ErrorSeccion mensaje={err} onReintentar={cargar} />;
  if (!lista) return <CargandoSeccion texto="Cargando las publicadas…" />;

  return (
    <div className="panel-card glass">
      <div className="ph">
        <h3>Publicadas</h3>
        <span style={{ color: "var(--txt-3)", fontSize: 13 }}>Lo que ya se ve en el feed y en las fichas. «Bajar» la saca.</span>
      </div>
      <div style={{ padding: "0 16px 12px" }}>
        <label className="campo-lbl" htmlFor="pub-buscar">Buscar por título o por comercio</label>
        <input id="pub-buscar" type="search" className="adm-input" value={busqueda} maxLength={80}
          onChange={(e) => setBusqueda(e.target.value)} placeholder="Ej: pizza, Farmacia Central…" />
        <div aria-live="polite" style={{ marginTop: 6, fontSize: 12.5, color: "var(--txt-3)" }}>
          {lista.length} de {total} {total === 1 ? "publicada" : "publicadas"}{q ? ` para «${q}»` : ""}
        </div>
      </div>
      {lista.length === 0 && (
        <div className="mod-item" style={{ justifyContent: "center", color: "var(--txt-3)" }}>
          {q ? `No hay publicadas que coincidan con «${q}».` : "No hay publicaciones publicadas."}
        </div>
      )}
      {lista.map((p) => (
        <div className="mod-item" key={p.id}>
          <img src={p.imagen_url ?? "https://picsum.photos/seed/ph/240/168"} alt="" />
          <div style={{ minWidth: 0 }}>
            <h4>{p.comercios?.nombre ?? "Comercio"} · <span style={{ textTransform: "capitalize", color: "var(--blue-soft)" }}>{p.tipo}</span></h4>
            <p>{p.descripcion ?? p.titulo}</p>
            <div className="mm">
              {p.precio != null && <span style={{ color: "var(--neon)", fontWeight: 700 }}>{precioFmt(p.precio, p.moneda)}</span>}
              {p.tiktok_url && <span><Ic n="videos" s={13} /> TikTok adjunto</span>}
              <span><Ic n="reloj" s={13} /> {new Date(p.created_at).toLocaleString("es-BO")}</span>
              <span style={{ color: "var(--neon)" }}><Ic n="listo" s={13} /> publicada</span>
            </div>
          </div>
          {bajando !== p.id && (
            <div className="mod-actions">
              <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44, color: "var(--pink)", borderColor: "var(--pink)" }}
                onClick={() => { setBajando(p.id); setMotivo(""); setErrBaja(""); }}>
                <Ic n="cerrar" s={14} /> Bajar
              </button>
            </div>
          )}
          {bajando === p.id && (
            <div style={{ gridColumn: "1 / -1", display: "grid", gap: 8 }}>
              <label style={{ fontSize: 12.5, color: "var(--txt-3)" }}>Motivo de la baja (obligatorio)
                <input className="adm-input" style={{ marginTop: 4 }} value={motivo} autoFocus maxLength={300}
                  onChange={(e) => setMotivo(e.target.value)} placeholder="Ej: la oferta ya venció, el precio estaba mal" />
              </label>
              {errBaja && <span role="alert" style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={13} /> {errBaja}</span>}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} disabled={enCurso}
                  onClick={() => { setBajando(null); setErrBaja(""); }}>Cancelar</button>
                <button type="button" className="btn btn-primary btn-sm" style={{ minHeight: 44, background: "var(--pink)", borderColor: "var(--pink)" }}
                  disabled={enCurso} onClick={() => bajar(p)}>
                  {enCurso ? "Bajando…" : "Bajar esta publicación"}
                </button>
              </div>
            </div>
          )}
        </div>
      ))}
      {lista.length < total && (
        <div style={{ padding: 16, textAlign: "center" }}>
          {errMas && <div role="alert" style={{ color: "var(--pink)", fontSize: 13, marginBottom: 8 }}><Ic n="aviso" s={13} /> {errMas}</div>}
          <button type="button" className="btn btn-ghost" style={{ minHeight: 44 }} disabled={masCargando} onClick={verMas}>
            {masCargando ? "Cargando…" : `Ver más (${lista.length} de ${total})`}
          </button>
        </div>
      )}
    </div>
  );
}

/** De dónde salió la atribución de una publicación entrante.
 *
 * Importa al aprobar: si vino por código, el mensaje llegó de un número que no
 * estaba asociado al comercio y se identificó con el papel que quedó en el
 * local. Cualquiera que vea ese papel puede publicar, así que conviene mirarlo
 * antes de aprobar — el backend además revalida el código y devuelve 409 si dejó
 * de coincidir. */
function IdentidadBadge({ pub }: { pub: PendingPub }) {
  if (pub.identidad_origen === "codigo") {
    return (
      <span style={{ color: "var(--amber)" }} title="El número no estaba asociado: se identificó con el código del local">
        <Ic n="cerrajeria" s={13} /> por código {pub.codigo_recibido ? `URUKU-${pub.codigo_recibido}` : ""}
      </span>
    );
  }
  if (pub.identidad_origen === "numero_por_codigo") {
    return (
      <span style={{ color: "var(--amber)" }} title="Este número quedó autorizado al mandar el código del local, no por alguien del equipo. Para que publique directo, autorizalo en el negocio.">
        <Ic n="cerrajeria" s={13} /> número sin confirmar
      </span>
    );
  }
  if (pub.identidad_origen === "desconocido") {
    return <span style={{ color: "var(--pink)" }} title="Ni número conocido ni código: no se sabe de qué comercio es"><Ic n="aviso" s={13} /> sin identificar</span>;
  }
  return null;  // 'numero' es el caso normal, no merece ruido visual
}

// ── Tab Reclamos ──────────────────────────────────────────────────────────────

function ReclamoRow({ nombre, contacto, sub, mensaje, estado, respuesta, onResponder }: {
  nombre: string; contacto: string | null; sub?: string; mensaje: string;
  estado: string; respuesta: string | null; onResponder: (respuesta: string) => void;
}) {
  const [respondiendo, setRespondiendo] = useState(false);
  const [texto, setTexto] = useState("");

  return (
    <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--border)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
        <div>
          <b>{nombre}</b>{sub && <span style={{ color: "var(--txt-3)", fontSize: 12 }}> · {sub}</span>}
          {contacto && <div style={{ fontSize: 12, color: "var(--txt-3)" }}>{contacto}</div>}
        </div>
        <span style={{ fontSize: 11, color: estado === "pendiente" ? "var(--amber)" : "var(--neon)" }}>
          {estado === "respondido" || estado === "respondida" ? "respondido" : "pendiente"}
        </span>
      </div>
      <p style={{ marginTop: 6, fontSize: 14 }}>{mensaje}</p>
      {respuesta && (
        <div style={{ marginTop: 8, padding: 10, background: "var(--panel)", borderRadius: 8, fontSize: 13 }}>
          <b style={{ color: "var(--neon)" }}>Respuesta:</b> {respuesta}
        </div>
      )}
      {!respuesta && (
        respondiendo ? (
          <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
            <input className="adm-input" style={{ flex: 1 }} value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Tu respuesta…" />
            <button className="btn btn-primary btn-sm" onClick={() => { if (texto.trim()) { onResponder(texto.trim()); setRespondiendo(false); setTexto(""); } }}>Enviar</button>
            <button className="btn btn-ghost btn-sm" onClick={() => setRespondiendo(false)}>Cancelar</button>
          </div>
        ) : (
          <button className="btn btn-ghost btn-sm" style={{ marginTop: 8 }} onClick={() => setRespondiendo(true)}>Responder</button>
        )
      )}
    </div>
  );
}

function TabReclamos({
  reclamos, consultasReservalo, onResponderReclamo, onResponderConsulta,
}: {
  reclamos: Reclamo[];
  consultasReservalo: ConsultaReservalo[];
  onResponderReclamo: (id: string, respuesta: string) => void;
  onResponderConsulta: (id: number, respuesta: string) => void;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="panel-card glass">
        <div className="ph"><h3>Reclamos (URUKU)</h3><span style={{ color: "var(--txt-3)", fontSize: 13 }}>Sobre negocios o la plataforma</span></div>
        {reclamos.length === 0 && <div style={{ padding: 20, textAlign: "center", color: "var(--txt-3)" }}>Sin reclamos.</div>}
        {reclamos.map((r) => (
          <ReclamoRow
            key={r.id}
            nombre={r.nombre ?? "Anónimo"}
            contacto={r.contacto}
            sub={r.comercios?.nombre}
            mensaje={r.mensaje}
            estado={r.estado}
            respuesta={r.respuesta}
            onResponder={(resp) => onResponderReclamo(r.id, resp)}
          />
        ))}
      </div>

      <div className="panel-card glass">
        <div className="ph"><h3>Consultas y reclamos (Reservalo)</h3><span style={{ color: "var(--txt-3)", fontSize: 13 }}>Formulario de contacto de la tienda</span></div>
        {consultasReservalo.length === 0 && <div style={{ padding: 20, textAlign: "center", color: "var(--txt-3)" }}>Sin consultas.</div>}
        {consultasReservalo.map((c) => (
          <ReclamoRow
            key={c.id}
            nombre={c.nombre ?? "Anónimo"}
            contacto={c.email}
            sub={c.tipo}
            mensaje={c.mensaje}
            estado={c.estado}
            respuesta={c.respuesta}
            onResponder={(resp) => onResponderConsulta(c.id, resp)}
          />
        ))}
      </div>
    </div>
  );
}

// ── Tab Cambio de número ──────────────────────────────────────────────────────

function TabCambioNumero({
  items, onAprobar, onRechazar,
}: {
  items: SolicitudCambioNumero[];
  onAprobar: (id: string) => void;
  onRechazar: (id: string) => void;
}) {
  return (
    <div className="panel-card glass">
      <div className="ph">
        <h3>Cambios de número</h3>
        <span style={{ color: "var(--txt-3)", fontSize: 13 }}>El dueño perdió su celu viejo — nunca se aprueba solo, siempre revisá vos</span>
      </div>
      {items.length === 0 && <div style={{ padding: 20, textAlign: "center", color: "var(--txt-3)" }}>Sin solicitudes pendientes.</div>}
      {items.map((s) => {
        return (
          <div key={s.id} style={{ padding: 16, borderBottom: "1px solid var(--border)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10 }}>
              <div>
                <b>{s.comercios?.nombre ?? "Comercio"}</b>
                <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 2 }}>
                  Número actual: +{s.comercios?.whatsapp} → nuevo: +{s.whatsapp_nuevo}
                </div>
                {s.lat != null && s.lng != null && (
                  <a href={`https://www.google.com/maps/search/?api=1&query=${s.lat},${s.lng}`} target="_blank" rel="noopener" style={{ fontSize: 12, color: "var(--blue-soft)" }}>
                    <Ic n="ubicacion" s={14} /> Ver ubicación enviada
                  </a>
                )}
                {s.mensaje && <p style={{ fontSize: 13, color: "var(--txt-2)", marginTop: 6 }}>{s.mensaje}</p>}
              </div>
            </div>

            <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: "var(--txt-3)", marginBottom: 4 }}>Foto registrada</div>
                {s.comercios?.portada_url
                  ? <img src={s.comercios.portada_url} alt="" style={{ width: "100%", height: 120, objectFit: "cover", borderRadius: 8 }} />
                  : <div style={{ height: 120, background: "var(--panel)", borderRadius: 8, display: "grid", placeItems: "center", color: "var(--txt-3)", fontSize: 12 }}>sin foto</div>}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: "var(--txt-3)", marginBottom: 4 }}>Foto nueva</div>
                {s.foto_url
                  ? <img src={s.foto_url} alt="" style={{ width: "100%", height: 120, objectFit: "cover", borderRadius: 8 }} />
                  : <div style={{ height: 120, background: "var(--panel)", borderRadius: 8, display: "grid", placeItems: "center", color: "var(--txt-3)", fontSize: 12 }}>sin foto</div>}
              </div>
            </div>

            {s.estado === "pendiente" ? (
              <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
                <button className="btn btn-primary btn-sm" onClick={() => onAprobar(s.id)}>Aprobar</button>
                <button className="btn btn-ghost btn-sm" onClick={() => onRechazar(s.id)}>Rechazar</button>
              </div>
            ) : (
              <div style={{ marginTop: 10, fontSize: 12, color: s.estado === "aprobada" ? "var(--neon)" : "var(--pink)" }}>
                {s.estado === "aprobada" ? "Aprobada" : "Rechazada"}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Tab Suscripciones ─────────────────────────────────────────────────────────

const ESTADO_CFG: Record<EstadoSuscripcion, { label: string; color: string }> = {
  activo:     { label: "Activo",       color: "var(--neon)" },
  por_vencer: { label: "Por vencer",   color: "var(--amber)" },
  vencido:    { label: "Vencido",      color: "var(--pink)" },
  suspendido: { label: "Suspendido",   color: "#888" },
  sin_plan:   { label: "Sin plan",     color: "var(--txt-3)" },
  // De cortesía: tiene el plan sin pagar y sin vencimiento. Va aparte de
  // «Activo» para que no se confunda con alguien que paga, y nunca alerta.
  cortesia:   { label: "De cortesía",  color: "var(--blue-soft)" },
};

/** Las opciones de un selector de planes: los activos por orden, y el plan
 *  actual aunque ya no esté en la lista (uno desactivado o inexistente), para
 *  que el selector no mienta mostrando otro. */
function opcionesDePlanes(planes: PlanAdmin[], actual?: string | null) {
  const lista = planes.filter((p) => p.activo).sort((a, b) => a.orden - b.orden)
    .map((p) => ({ slug: p.slug, nombre: p.nombre, precio_mes: p.precio_mes }));
  const falta = actual && !lista.some((p) => p.slug === actual);
  return falta ? [...lista, { slug: actual, nombre: actual, precio_mes: 0 }] : lista;
}

function TabPagos({
  items, onConfirmar,
}: {
  items: PagoPendiente[];
  onConfirmar: (pagoId: string, meses: number, plan?: string) => void;
}) {
  // El plan al que pasa el comercio al confirmar es opcional: sin elegir, sólo
  // se extiende la fecha, como hasta ahora. Si la lista de planes no carga, el
  // selector no aparece y confirmar sigue andando.
  const [planes, setPlanes] = useState<PlanAdmin[]>([]);
  const [planDe, setPlanDe] = useState<Record<string, string>>({});
  useEffect(() => { getPlanesAdmin().then(setPlanes).catch(() => {}); }, []);
  const opciones = opcionesDePlanes(planes);
  const METODO_LABEL: Record<string, string> = {
    "qr-bolivia": "QR Bolivia", "qr-argentina": "QR Argentina",
    transferencia: "Transferencia", efectivo: "Efectivo",
  };
  return (
    <div className="panel-card glass">
      <div className="ph"><h3>Pagos por confirmar</h3><span style={{ color: "var(--txt-3)", fontSize: 13 }}>Comprobantes que subieron los comercios</span></div>
      {items.length === 0 && (
        <div className="mod-item" style={{ justifyContent: "center", color: "var(--txt-3)" }}>
          No hay pagos pendientes de confirmación.
        </div>
      )}
      {items.map((p) => (
        <div className="mod-item" key={p.id}>
          {p.comprobante_url
            ? <a href={p.comprobante_url} target="_blank" rel="noopener"><img src={p.comprobante_url} alt="comprobante" /></a>
            : <div style={{ width: 120, minWidth: 120, height: 84, display: "grid", placeItems: "center", background: "var(--panel)", borderRadius: 8, color: "var(--txt-3)", fontSize: 12 }}>sin foto</div>}
          <div>
            <h4>{p.comercios?.nombre ?? "Comercio"}</h4>
            <p>
              <b style={{ color: "var(--neon)" }}>{p.moneda} {Number(p.monto).toLocaleString("es-AR")}</b>
              {" · "}{METODO_LABEL[p.metodo] ?? p.metodo}
              {p.referencia && <> · ref: {p.referencia}</>}
            </p>
            <div className="mm"><span><Ic n="reloj" s={13} /> {new Date(p.created_at).toLocaleString("es-AR")}</span></div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginLeft: "auto" }}>
            {opciones.length > 0 && (
              <label style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 12, color: "var(--txt-3)" }}>
                Plan (opcional)
                <select className="adm-input" value={planDe[p.id] ?? ""}
                        onChange={(e) => setPlanDe((prev) => ({ ...prev, [p.id]: e.target.value }))}>
                  <option value="">Sin cambiar el plan</option>
                  {opciones.map((o) => <option key={o.slug} value={o.slug}>{o.nombre}</option>)}
                </select>
              </label>
            )}
            <button className="btn btn-primary btn-sm" onClick={() => onConfirmar(p.id, 1, planDe[p.id] || undefined)}>Confirmar 1 mes</button>
            <button className="btn btn-ghost btn-sm" onClick={() => onConfirmar(p.id, 2, planDe[p.id] || undefined)}>Confirmar 2 meses</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function TabKpis({ data, dias, onDias }: { data: Kpis | null; dias: number; onDias: (d: number) => void }) {
  const selector = (
    <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
      <select className="adm-input" style={{ width: "auto" }} value={dias}
              onChange={(e) => onDias(Number(e.target.value))}>
        <option value={1}>Hoy</option>
        <option value={7}>Últimos 7 días</option>
        <option value={30}>Últimos 30 días</option>
        <option value={90}>Últimos 90 días</option>
        <option value={365}>Último año</option>
      </select>
      {data?.desde && (
        <span style={{ fontSize: 12, color: "var(--txt-3)" }}>
          Desde el {data.desde} · {data.busquedas_total ?? 0} búsquedas, {data.eventos_total ?? 0} eventos
        </span>
      )}
    </div>
  );
  if (!data) return <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>{selector}<p style={{ color: "var(--txt-3)" }}>Cargando KPIs…</p></div>;
  const m = data.monetizacion;
  const card: React.CSSProperties = { padding: 18, borderRadius: 14, border: "1px solid var(--stroke)", background: "var(--panel)" };
  const Lista = ({ titulo, items, empty, nota }: {
    titulo: string;
    items: { query?: string; nombre?: string; slug?: string | null; n?: number; eventos?: number; hoy?: number | null }[];
    empty: string; nota?: string;
  }) => (
    <div style={card}>
      <h3 style={{ marginTop: 0, fontSize: 15 }}>{titulo}</h3>
      {nota && <p style={{ color: "var(--txt-3)", fontSize: 11.5, marginTop: -6, marginBottom: 10 }}>{nota}</p>}
      {items.length === 0 ? <p style={{ color: "var(--txt-3)", fontSize: 13 }}>{empty}</p> : (
        <ol style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 6 }}>
          {items.map((it, i) => (
            <li key={i} style={{ fontSize: 13.5, color: "var(--txt-2)" }}>
              {it.slug ? <Link href={`/comercios/${it.slug}`} style={{ color: "var(--txt)" }}>{it.nombre}</Link> : (it.query ?? it.nombre)}
              <b style={{ color: "var(--neon)", marginLeft: 6 }}>{it.n ?? it.eventos}</b>
              {/* Cuántos da HOY. Sin esto, «rústico 59» parecía una buena
                  noticia; con el 2 al lado se ve que es el hueco más grande
                  que tiene URUKU. En ámbar cuando la demanda le gana a la
                  oferta: mucha gente buscando y poco cargado. */}
              {it.hoy != null && (
                <span style={{ marginLeft: 8, fontSize: 11.5,
                               color: it.hoy === 0 ? "var(--pink)"
                                    : (it.n ?? 0) > it.hoy ? "var(--amber)" : "var(--txt-3)" }}>
                  {it.hoy === 0 ? "sin resultados hoy" : `→ ${it.hoy} resultados hoy`}
                </span>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {selector}
      {/* Monetización (para el creador del sitio) */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {[["Comercios activos", m.comercios_activos, "var(--txt)"], ["Pagando", m.pagando, "var(--neon)"], ["Gratis", m.gratis, "var(--txt-3)"]].map(([lbl, val, col]) => (
          <div key={lbl as string} style={{ ...card, flex: 1, minWidth: 130 }}>
            <div style={{ fontSize: 12, color: "var(--txt-3)" }}>{lbl as string}</div>
            <div style={{ fontSize: 28, fontWeight: 900, color: col as string }}>{val as number}</div>
          </div>
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 12 }}>
        <Lista titulo="Más buscado" items={data.top_busquedas}
               nota={`Veces buscado en el período → cuántos encuentra HOY. En ámbar, donde hay más demanda que oferta.`}
               empty="Sin búsquedas en este período." />
        <Lista titulo="Sigue sin resultado" items={data.sin_resultado}
               nota="Verificado contra el catálogo de hoy, no contra el día que se buscó."
               empty="Nada sin resultado" />
        <Lista titulo="Locales más visitados" items={data.top_comercios}
               nota="Fichas abiertas y contactos, en el período elegido."
               empty="Sin visitas en este período." />
      </div>
      {/* Lo que ya no es un problema, aparte. Estaba mezclado con lo de
          arriba bajo el cartel de «oportunidades», y mandaba a salir a buscar
          comercios que ya existen: «celulares» figuraba sin resultado y hoy
          da 65. Eran búsquedas de cuando el catálogo estaba a medio cargar. */}
      {(data.ya_resueltas?.length ?? 0) > 0 && (
        <div style={{ ...card, borderColor: "var(--stroke)" }}>
          <h3 style={{ marginTop: 0, fontSize: 15 }}><Ic n="listo" s={15} /> Ya no son un hueco</h3>
          <p style={{ color: "var(--txt-3)", fontSize: 11.5, marginTop: -6 }}>
            No daban nada el día que se buscaron y hoy sí. No hay nada que salir a hacer con estos.
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {data.ya_resueltas!.map((t) => (
              <span key={t.query} style={{ fontSize: 12.5, color: "var(--txt-3)", border: "1px solid var(--stroke)",
                                           borderRadius: 999, padding: "3px 9px" }}>
                {t.query} <b style={{ color: "var(--neon)" }}>{t.hoy}</b>
              </span>
            ))}
          </div>
        </div>
      )}
      <p style={{ color: "var(--txt-3)", fontSize: 12 }}>"Sigue sin resultado" = oportunidades de verdad: lo que la gente busca y hoy no está → a quién salir a sumar.</p>
    </div>
  );
}

function TabMonitoreo({
  data, reservalo, comercios, comerciosListos,
}: {
  data: EstadisticasAdmin | null;
  reservalo: ReservaloResumen | null;
  comercios: ComercioPorVerificar[];
  /** La lista de comercios se baja en segundo plano al abrir Monitoreo (sólo
   *  sirve para poner el nombre en «Reservas por negocio»): hasta que llega no
   *  se muestra «?» sino puntos suspensivos. */
  comerciosListos: boolean;
}) {
  const [altas, setAltas] = useState<AltasDia[]>([]);
  useEffect(() => { altasPorDia(60).then((r) => setAltas(r.items ?? [])).catch(() => {}); }, []);

  if (!data) return <div className="panel-card glass" style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>Cargando…</div>;

  const totalAlertas = data.alertas.vencido + data.alertas.suspendido;
  const nombrePorId = (id: string) => comercios.find((c) => c.id === id)?.nombre ?? (comerciosListos ? "?" : "…");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Lo primero: cuánta gente entra y cuántos escriben. Todo lo demás de
          esta pantalla —altas, ofertas, alertas— es lo que hacemos nosotros;
          esto es lo que hace la gente. */}
      <PanelVisitas />

      {/* Altas por día. Las columnas se leen de a pares: `altas` contra `con
          WhatsApp` es la diferencia entre un punto en el mapa y un local al que
          se le puede escribir; contra `analizados`, lo que falta pasar por la
          IA. Un total suelto no muestra ninguna de las dos. */}
      {altas.length > 0 && (
        <div className="panel-card glass" style={{ padding: 16 }}>
          <h3 style={{ marginBottom: 4 }}>Altas por día</h3>
          <p style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 12 }}>
            Últimos 60 días · {altas.reduce((a, d) => a + d.altas, 0)} comercios
          </p>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ color: "var(--txt-3)", fontSize: 11, textAlign: "right" }}>
                  <th style={{ textAlign: "left", padding: "4px 8px" }}>Día</th>
                  <th style={{ padding: "4px 8px" }}>Altas</th>
                  <th style={{ padding: "4px 8px" }}>Con nombre</th>
                  <th style={{ padding: "4px 8px" }}>Con foto</th>
                  <th style={{ padding: "4px 8px" }}>Con WhatsApp</th>
                  <th style={{ padding: "4px 8px" }}>Analizados</th>
                  <th style={{ padding: "4px 8px" }}>Agentes</th>
                </tr>
              </thead>
              <tbody>
                {altas.map((d) => {
                  const falta = d.altas - d.con_whatsapp;
                  return (
                    <tr key={d.dia} style={{ borderTop: "1px solid var(--border)", textAlign: "right" }}>
                      <td style={{ textAlign: "left", padding: "6px 8px", whiteSpace: "nowrap" }}>{d.dia}</td>
                      <td style={{ padding: "6px 8px", fontWeight: 700 }}>{d.altas}</td>
                      <td style={{ padding: "6px 8px" }}>{d.con_nombre}</td>
                      <td style={{ padding: "6px 8px" }}>{d.con_foto}</td>
                      {/* Lo que falta se resalta: es el número que decide si la
                          ficha lleva a algún lado o es sólo un punto. */}
                      <td style={{ padding: "6px 8px", color: falta > 0 ? "var(--amber)" : undefined }}>
                        {d.con_whatsapp}{falta > 0 && <span style={{ fontSize: 11 }}> (−{falta})</span>}
                      </td>
                      <td style={{ padding: "6px 8px" }}>{d.analizados}</td>
                      <td style={{ padding: "6px 8px", color: "var(--txt-3)" }}>{d.agentes}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
        <div className="panel-card glass" style={{ padding: 16, borderLeft: "3px solid var(--neon)" }}>
          <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Negocios nuevos (7d)</div>
          <div style={{ fontSize: 26, fontWeight: 700 }}>{data.comercios_nuevos_7d}</div>
          <div style={{ fontSize: 11, color: "var(--txt-3)" }}>{data.comercios_nuevos_30d} en 30 días</div>
        </div>
        <div className="panel-card glass" style={{ padding: 16, borderLeft: "3px solid var(--amber)" }}>
          <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Ofertas activas</div>
          <div style={{ fontSize: 26, fontWeight: 700 }}>{data.ofertas_total}</div>
        </div>
        {/* Lo que la plataforma le lleva al comercio: no las visitas a la
            ficha —que se cuentan solas— sino las veces que alguien salió de
            URUKU hacia el local. Es el número que hay que poder mostrarle al
            comerciante cuando pregunte para qué paga. */}
        <div className="panel-card glass" style={{ padding: 16, borderLeft: "3px solid var(--blue-soft)" }}>
          <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Contactos (30d)</div>
          <div style={{ fontSize: 26, fontWeight: 700 }}>{data.contactos_30d}</div>
          <div style={{ fontSize: 11, color: "var(--txt-3)", marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
            <span title="Abrieron el WhatsApp del comercio"><Ic n="whatsapp" s={13} /> {data.contactos_por_tipo?.whatsapp ?? 0}</span>
            <span title="Tocaron &quot;Cómo llegar&quot;"><Ic n="ubicacion" s={13} /> {data.contactos_por_tipo?.mapa ?? 0}</span>
            {/* La reserva vale distinto que un WhatsApp suelto: no preguntó,
                pidió algo concreto. Es el número que justifica un plan pago. */}
            <span title="Mandaron una reserva" style={{ color: (data.contactos_por_tipo?.reserva ?? 0) > 0 ? "var(--neon)" : undefined }}>
              <Ic n="alimentos" s={13} /> {data.contactos_por_tipo?.reserva ?? 0}
            </span>
            {(data.contactos_por_tipo?.telefono ?? 0) > 0 && <span title="Llamaron"><Ic n="telefono" s={13} /> {data.contactos_por_tipo.telefono}</span>}
          </div>
          <div style={{ fontSize: 11, color: "var(--txt-3)", marginTop: 2 }}>
            {data.vistas_30d ?? 0} fichas vistas
          </div>
        </div>
        {/* Llegadas por QR o enlace marcado (?ref=): la única forma de saber
            si los volantes y las tarjetas de mesa trajeron a alguien. */}
        <div className="panel-card glass" style={{ padding: 16, borderLeft: "3px solid var(--neon)" }}>
          <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Llegadas por QR (30d)</div>
          <div style={{ fontSize: 26, fontWeight: 700 }}>{data.llegadas_30d ?? 0}</div>
          <div style={{ fontSize: 11, color: "var(--txt-3)", marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
            <span title="Tarjetas de mesa"><Ic n="restaurantes" s={13} /> {data.llegadas_por_clase?.mesa ?? 0}</span>
            <span title="Volantes"><Ic n="documento" s={13} /> {data.llegadas_por_clase?.volante ?? 0}</span>
            <span title="El QR de la ficha en el sitio"><Ic n="web" s={13} /> {data.llegadas_por_clase?.ficha ?? 0}</span>
            {(data.llegadas_por_clase?.fb ?? 0) + (data.llegadas_por_clase?.ig ?? 0) > 0 && (
              <span title="Facebook e Instagram"><Ic n="novedades" s={13} /> {(data.llegadas_por_clase?.fb ?? 0) + (data.llegadas_por_clase?.ig ?? 0)}</span>
            )}
          </div>
          {(data.llegadas_top?.length ?? 0) > 0 && (
            <div style={{ fontSize: 11, color: "var(--txt-3)", marginTop: 2 }} title={data.llegadas_top!.map((l) => `${l.origen}: ${l.count}`).join(" · ")}>
              Más escaneado: {data.llegadas_top![0].origen} ({data.llegadas_top![0].count})
            </div>
          )}
          <div style={{ fontSize: 11, color: "var(--txt-3)", marginTop: 6, borderTop: "1px solid var(--stroke)", paddingTop: 6 }}
            title={(data.contactos_origen_top ?? []).map((l) => `${l.origen}: ${l.count}`).join(" · ")}>
            <Ic n="whatsapp" s={13} /> {data.contactos_con_origen_30d ?? 0} contactaron a un negocio
            {Object.entries(data.contactos_por_clase ?? {}).length > 0 && (
              <> · {Object.entries(data.contactos_por_clase ?? {}).map(([k, n]) => `${k} ${n}`).join(" · ")}</>
            )}
            {(data.contactos_origen_top?.length ?? 0) > 0 && (
              <div>Más contactos: {data.contactos_origen_top![0].origen} ({data.contactos_origen_top![0].count})</div>
            )}
          </div>
        </div>
        <div className="panel-card glass" style={{ padding: 16, borderLeft: `3px solid ${totalAlertas > 0 ? "var(--pink)" : "var(--neon)"}` }}>
          <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Bajas / vencidos</div>
          <div style={{ fontSize: 26, fontWeight: 700, color: totalAlertas > 0 ? "var(--pink)" : undefined }}>{totalAlertas}</div>
          <div style={{ fontSize: 11, color: "var(--txt-3)" }}>{data.alertas.por_vencer} por vencer en 5 días</div>
        </div>
      </div>

      {(data.no_contestan?.length ?? 0) > 0 && (
        <div className="panel-card glass" style={{ padding: "12px 16px", border: "1px solid var(--amber)", fontSize: 13 }}>
          <b style={{ color: "var(--amber)" }}><Ic n="aviso" s={14} /> No contestan el WhatsApp</b>
          <span style={{ opacity: .7 }}> — lo dijeron los compradores («¿te contestó?»). Casi siempre es un número viejo o un teléfono apagado: llamarlos.</span>
          <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
            {data.no_contestan!.map((c) => (
              <li key={c.id}>
                {c.slug ? <a href={`/comercios/${c.slug}`} target="_blank" rel="noopener">{c.nombre}</a> : c.nombre}
                {" "}· {c.contacto_no} no / {c.contacto_ok} sí{c.whatsapp ? ` · ${c.whatsapp}` : " · sin WhatsApp cargado"}
              </li>
            ))}
          </ul>
        </div>
      )}

      {totalAlertas > 0 && (
        <div className="panel-card glass" style={{ padding: "12px 16px", border: "1px solid var(--pink)", color: "var(--pink)", fontSize: 13 }}>
          <Ic n="aviso" s={14} /> {data.alertas.vencido} comercio(s) vencido(s) y {data.alertas.suspendido} suspendido(s). Revisá la sección «Suscripciones».
        </div>
      )}

      <PanelPesoFotos />

      {/* Top ofertas */}
      <div className="panel-card glass">
        <div className="ph"><h3>Comercios con más ofertas</h3></div>
        {data.ofertas_top_comercios.length === 0 && (
          <div style={{ padding: 20, textAlign: "center", color: "var(--txt-3)" }}>Sin ofertas cargadas todavía.</div>
        )}
        {data.ofertas_top_comercios.map((c) => (
          <div key={c.comercio_id} style={{ display: "flex", justifyContent: "space-between", padding: "10px 16px", borderBottom: "1px solid var(--border)" }}>
            <span>{c.nombre}</span>
            <b style={{ color: "var(--neon)" }}>{c.count}</b>
          </div>
        ))}
      </div>

      {/* Top contactos */}
      <div className="panel-card glass">
        <div className="ph"><h3>Comercios más contactados</h3><span style={{ color: "var(--txt-3)", fontSize: 13 }}>Últimos 30 días</span></div>
        {data.contactos_top_comercios.length === 0 && (
          <div style={{ padding: 20, textAlign: "center", color: "var(--txt-3)" }}>Todavía no hay contactos registrados.</div>
        )}
        {data.contactos_top_comercios.map((c) => (
          <div key={c.comercio_id} style={{ display: "flex", justifyContent: "space-between", padding: "10px 16px", borderBottom: "1px solid var(--border)" }}>
            <span>{c.nombre}</span>
            <b style={{ color: "var(--blue-soft)" }}>{c.count}</b>
          </div>
        ))}
      </div>

      {/* Reservalo */}
      {reservalo && (reservalo.reservas_30d_total != null) && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
            <div className="panel-card glass" style={{ padding: 16, borderLeft: "3px solid var(--neon)" }}>
              <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Clientes nuevos (Reservalo, 7d)</div>
              <div style={{ fontSize: 26, fontWeight: 700 }}>{reservalo.clientes_nuevos_7d ?? 0}</div>
              <div style={{ fontSize: 11, color: "var(--txt-3)" }}>{reservalo.clientes_nuevos_30d ?? 0} en 30 días</div>
            </div>
            <div className="panel-card glass" style={{ padding: 16, borderLeft: "3px solid var(--blue-soft)" }}>
              <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Reservas (30d)</div>
              <div style={{ fontSize: 26, fontWeight: 700 }}>{reservalo.reservas_30d_total ?? 0}</div>
            </div>
          </div>

          <div className="panel-card glass">
            <div className="ph"><h3>Reservas por negocio</h3><span style={{ color: "var(--txt-3)", fontSize: 13 }}>Últimos 30 días · Reservalo</span></div>
            {(reservalo.reservas_30d_por_vendedor ?? []).length === 0 && (
              <div style={{ padding: 20, textAlign: "center", color: "var(--txt-3)" }}>Sin reservas todavía.</div>
            )}
            {(reservalo.reservas_30d_por_vendedor ?? []).map((v) => (
              <div key={v.vendedor_id} style={{ display: "flex", justifyContent: "space-between", padding: "10px 16px", borderBottom: "1px solid var(--border)" }}>
                <span>{nombrePorId(v.vendedor_id)}</span>
                <b style={{ color: "var(--neon)" }}>{v.count}</b>
              </div>
            ))}
          </div>

          <div className="panel-card glass">
            <div className="ph"><h3>Productos más consultados</h3><span style={{ color: "var(--txt-3)", fontSize: 13 }}>Por cantidad de chats · Reservalo</span></div>
            {(reservalo.top_productos_consultados ?? []).length === 0 && (
              <div style={{ padding: 20, textAlign: "center", color: "var(--txt-3)" }}>Sin consultas todavía.</div>
            )}
            {(reservalo.top_productos_consultados ?? []).map((p) => (
              <div key={p.producto_id} style={{ display: "flex", justifyContent: "space-between", padding: "10px 16px", borderBottom: "1px solid var(--border)" }}>
                <span>{p.nombre}</span>
                <b style={{ color: "var(--blue-soft)" }}>{p.count}</b>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function TabSuscripciones({
  items, onSuspender, onActivar, onPago,
}: {
  items: ComercioSuscripcion[];
  onSuspender: (id: string) => void;
  onActivar: (id: string) => void;
  onPago: () => void;
}) {
  const [filtro, setFiltro] = useState<EstadoSuscripcion | "todos">("todos");
  const [pagandoId, setPagandoId] = useState<string | null>(null);
  const [gestionandoId, setGestionandoId] = useState<string | null>(null);
  // Confiable, números autorizados, grupos y «mensaje al comercio» son llaves de la cuenta.
  const puedeCuenta = puedo("comercios.cuenta");
  const [planDeId, setPlanDeId] = useState<string | null>(null);
  // Para escribir el NOMBRE del plan en cada fila y llenar el selector del modal.
  const [planes, setPlanes] = useState<PlanAdmin[]>([]);
  // Si la lista no llegó, el modal no deja guardar: con la lista vacía mostraba
  // sólo el plan actual como gratis y, al guardar, le sacaba la cortesía al
  // comercio sin avisar.
  const [planesListos, setPlanesListos] = useState(false);
  const [errPlanes, setErrPlanes] = useState("");
  useEffect(() => {
    getPlanesAdmin()
      .then((ps) => { setPlanes(ps); setPlanesListos(true); })
      .catch((e) => setErrPlanes(e instanceof Error && e.message ? e.message : "No se pudo leer la lista de planes."));
  }, []);
  const nombrePlan = (slug?: string) => planes.find((p) => p.slug === slug)?.nombre ?? slug ?? "gratis";

  const conteo = (e: EstadoSuscripcion) => items.filter((c) => c.suscripcion_estado === e).length;
  const visibles = filtro === "todos" ? items : items.filter((c) => c.suscripcion_estado === filtro);

  return (
    <div className="panel-card glass">
      <div className="ph">
        <h3>Suscripciones</h3>
        <span style={{ color: "var(--txt-3)", fontSize: 13 }}>Gestión de pagos y estado de cada negocio</span>
      </div>

      {/* Contadores */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
        {(["todos", "activo", "cortesia", "por_vencer", "vencido", "suspendido", "sin_plan"] as const).map((e) => {
          const n = e === "todos" ? items.length : conteo(e as EstadoSuscripcion);
          const cfg = e === "todos" ? { label: "Todos", color: "var(--txt-2)" } : ESTADO_CFG[e as EstadoSuscripcion];
          return (
            <button key={e} onClick={() => setFiltro(e)}
              style={{ padding: "6px 14px", borderRadius: 20, border: "1px solid", cursor: "pointer",
                borderColor: filtro === e ? cfg.color : "var(--border)",
                background: filtro === e ? `${cfg.color}22` : "transparent",
                color: cfg.color, fontSize: 13, fontWeight: filtro === e ? 600 : 400 }}>
              {cfg.label} <span style={{ opacity: 0.7 }}>({n})</span>
            </button>
          );
        })}
      </div>

      {/* Lista */}
      {visibles.length === 0 && (
        <div style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>Sin resultados.</div>
      )}
      {visibles.map((c) => {
        const cfg = ESTADO_CFG[c.suscripcion_estado];
        return (
          <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 16px", borderBottom: "1px solid var(--border)" }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: 15 }}>{c.nombre}</div>
              <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 2 }}>
                +{c.whatsapp} · {c.verificado ? "verificado" : "sin verificar"}
              </div>
              <div style={{ fontSize: 12, marginTop: 4 }}>
                <span style={{ color: cfg.color, fontWeight: 600 }}>
                  {c.plan_cortesia && <><Ic n="estrella" s={13} peso="fill" />{" "}</>}{cfg.label}
                </span>
                <span style={{ color: "var(--txt-2)", marginLeft: 8 }}>· Plan {nombrePlan(c.plan)}</span>
                {/* Un plan de cortesía no vence: ni la fecha ni «por vencer». */}
                {c.paga_hasta && !c.plan_cortesia && (
                  <span style={{ color: "var(--txt-3)", marginLeft: 8 }}>
                    · vence {new Date(c.paga_hasta + "T12:00:00").toLocaleDateString("es-BO")}
                  </span>
                )}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
              {/* La cuenta (confiable, números, grupos, mensajes) es de admin y moderador: el publicador no la ve. */}
              {puedeCuenta && (<>
              <button className="btn btn-ghost btn-sm" title="Enviar mensaje al comercio" onClick={async () => {
                const cuerpo = prompt(`Mensaje para ${c.nombre}:`);
                if (cuerpo && cuerpo.trim()) { try { await enviarMensajeComercio(c.id, cuerpo.trim()); alert("Mensaje enviado"); } catch { alert("No se pudo enviar"); } }
              }}><Ic n="enviar" s={15} /></button>
              <button className="btn btn-ghost btn-sm" title="Confiable y números autorizados" onClick={() => setGestionandoId(c.id)}>
                <Ic n="mas_opciones" s={15} />
              </button>
              </>)}
              <button className="btn btn-ghost btn-sm" title="Elegir el plan o ponerlo de cortesía" onClick={() => setPlanDeId(c.id)}>
                Plan
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => setPagandoId(c.id)}>
                + Pago
              </button>
              {c.suspendido ? (
                <button className="mbtn approve" title="Reactivar" onClick={() => onActivar(c.id)}>
                  <Check style={{ width: 16, height: 16 }} />
                </button>
              ) : (
                <button className="mbtn reject" title="Suspender" onClick={() => onSuspender(c.id)}>
                  <X style={{ width: 16, height: 16 }} />
                </button>
              )}
            </div>
          </div>
        );
      })}

      {/* Modal de gestión: confiable + números autorizados */}
      {gestionandoId && (
        <ModalGestionComercio
          comercio={items.find((c) => c.id === gestionandoId)!}
          onClose={() => setGestionandoId(null)}
        />
      )}

      {/* Modal del plan: elegir plan y marcarlo de cortesía */}
      {planDeId && (
        <ModalPlanComercio
          comercio={items.find((c) => c.id === planDeId)!}
          planes={planes}
          planesListos={planesListos}
          errPlanes={errPlanes}
          onClose={() => setPlanDeId(null)}
          onDone={() => { setPlanDeId(null); onPago(); }}
        />
      )}

      {/* Modal registro de pago */}
      {pagandoId && (
        <ModalPago
          comercio={items.find((c) => c.id === pagandoId)!}
          onClose={() => setPagandoId(null)}
          onDone={() => { setPagandoId(null); onPago(); }}
        />
      )}
    </div>
  );
}

// ── Tab Comercios ─────────────────────────────────────────────────────────────

type FiltroComercio = "todos" | "pendientes" | "verificados" | "incompletos" | "sin-horario";
type OrdenComercio = "recientes" | "alfabetico" | "estado";
type VistaComercio = "lista" | "mapa";

function normTxt(s: string): string {
  return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

// Motivos por los que un comercio está "incompleto" (para completarlo en tanda).
//
// `noComerciales` son los slugs de rubros marcados `comercial = false` en la
// base: baños, taxis, trámites. A un baño público no se le reclama WhatsApp ni
// productos — está completo así. Sin esta excepción, cada punto de la ciudad
// que se cargue queda para siempre en la cola de "incompletos", y una cola que
// nunca baja se deja de mirar.
function incompletoDe(c: ComercioPorVerificar, noComerciales?: Set<string>): string[] {
  const r: string[] = [];
  const nombre = (c.nombre ?? "").trim();
  const rubroNombre = (c.rubros?.nombre ?? "").trim();
  // "sin nombre" = vacío, el default 'Comercio', o quedó con el nombre del rubro.
  //
  // Salvo que esté marcado SIN CARTEL, que no es lo mismo: ahí el local no
  // tiene nombre porque no lo tiene, la base le arma uno con lo que vende y
  // dónde está, y no hay nada que corregir. Eran 555 defectos que nadie iba a
  // poder arreglar nunca, y con ellos adentro el contador no bajaba.
  if (!c.sin_cartel
      && (!nombre || nombre.toLowerCase() === "comercio" || (!!rubroNombre && nombre.toLowerCase() === rubroNombre.toLowerCase()))) r.push("sin nombre");
  if (!c.portada_url) r.push("sin foto");
  // La foto sí se le pide a todo: un baño sin foto en el mapa no se distingue
  // de un pin cualquiera, y la foto es lo que hace que alguien lo reconozca al
  // llegar.
  const esPunto = !!noComerciales?.has(c.rubros?.slug ?? "");
  if (esPunto) return r;
  if (!c.whatsapp && !c.telefono) r.push("sin contacto");
  // "otros" NO es un rubro: es el descarte. Un comercio ahí no aparece en
  // ninguna búsqueda por categoría, así que cuenta como sin clasificar. Antes
  // esto no se detectaba y los 92 comercios en "otros" figuraban como completos.
  if (!c.rubros?.slug || c.rubros.slug === "otros") r.push("sin clasificar");
  if (!c.prod_obs_human?.trim() && !c.prod_det_ia?.trim()) r.push("sin productos");
  return r;
}

/** Los rubros de un comercio en una línea: el principal en negrita y primero,
 *  los demás detrás. Sin esto la fila mostraba sólo el principal y no había
 *  forma de saber, desde la lista, si el rubro correcto ya estaba puesto. */
function RubrosDeFila({ c }: { c: ComercioPorVerificar }) {
  const principal = c.rubros?.nombre;
  const otros = (c.comercio_rubros ?? [])
    .map((x) => x.rubros?.nombre)
    .filter((n): n is string => !!n && n !== principal);

  if (!principal && otros.length === 0) return <>Sin rubro</>;
  return (
    <>
      <b>{principal ?? "Sin rubro"}</b>
      {otros.length > 0 && <span style={{ opacity: .75 }}> + {otros.join(" + ")}</span>}
    </>
  );
}

/** «Sin horario»: el chip de Negocios y la columna del resumen por ciudad usan
 *  ESTA función, así las dos cuentas no pueden separarse. */
function sinHorarioDe(c: ComercioPorVerificar): boolean {
  return !((c as Record<string, unknown>).horario as string ?? "").trim();
}

/** Con foto y sin clasificar por la IA: lo que «Clasificar por fotos» procesa. */
function sinClasificarDe(c: ComercioPorVerificar): boolean {
  return !!c.portada_url && !c.ia_analizado_at;
}

type FilaResumen = {
  slug: string; nombre: string; elegible: boolean;
  total: number; sinClasificar: number; incompletos: number; sinHorario: number; sinVerificar: number;
};

/** Una fila por ciudad con al menos un comercio, y una última «Todas» con la
 *  suma. Se calcula de la MISMA lista `todos` y con las MISMAS reglas que los
 *  chips (`incompletoDe`, `sinHorarioDe`): si no, la tabla diría una cosa y el
 *  chip otra. Por eso la suma de las filas da el total de Negocios. */
function ResumenPorCiudad({ todos, noComerciales, truncado }: {
  todos: ComercioPorVerificar[]; noComerciales: Set<string>; truncado: boolean;
}) {
  const { ciudades, slug: elegida, elegir } = useAdminCiudad();

  const filas = new Map<string, FilaResumen>();
  for (const c of todos) {
    const slug = c.ciudades?.slug ?? "";
    let f = filas.get(slug);
    if (!f) {
      f = { slug, nombre: c.ciudades?.nombre ?? "Sin ciudad", elegible: !!slug && ciudades.some((x) => x.slug === slug),
            total: 0, sinClasificar: 0, incompletos: 0, sinHorario: 0, sinVerificar: 0 };
      filas.set(slug, f);
    }
    f.total++;
    if (sinClasificarDe(c)) f.sinClasificar++;
    if (incompletoDe(c, noComerciales).length > 0) f.incompletos++;
    if (sinHorarioDe(c)) f.sinHorario++;
    if (!c.verificado) f.sinVerificar++;
  }
  if (filas.size === 0) return null;

  // Más comercios primero; «Sin ciudad» siempre al final.
  const lista = [...filas.values()].sort((a, b) =>
    (a.slug === "" ? 1 : 0) - (b.slug === "" ? 1 : 0) || b.total - a.total);
  const suma = lista.reduce((s, f) => ({
    total: s.total + f.total, sinClasificar: s.sinClasificar + f.sinClasificar,
    incompletos: s.incompletos + f.incompletos, sinHorario: s.sinHorario + f.sinHorario,
    sinVerificar: s.sinVerificar + f.sinVerificar,
  }), { total: 0, sinClasificar: 0, incompletos: 0, sinHorario: 0, sinVerificar: 0 });

  const th: React.CSSProperties = { textAlign: "right", padding: "6px 10px", fontWeight: 600, fontSize: 12, color: "var(--txt-3)", verticalAlign: "bottom" };
  const td: React.CSSProperties = { textAlign: "right", padding: "7px 10px", fontVariantNumeric: "tabular-nums" };
  // Botón sin aspecto de botón pero con foco visible (no `all: unset`, que lo borra).
  const btnFila: React.CSSProperties = {
    background: "none", border: "none", padding: 0, margin: 0, cursor: "pointer",
    color: "inherit", font: "inherit", display: "inline-flex", alignItems: "center", gap: 6,
  };
  const celdas = (f: { total: number; sinClasificar: number; incompletos: number; sinHorario: number; sinVerificar: number }) => (
    <>
      <td style={td}>{f.total}</td>
      <td style={td}>{f.sinClasificar}</td>
      <td style={td}>{f.incompletos}</td>
      <td style={td}>{f.sinHorario}</td>
      <td style={td}>{f.sinVerificar}</td>
    </>
  );

  return (
    // La caja se desplaza sola: en el teléfono la tabla no entra y la página
    // no puede tener scroll horizontal.
    <div style={{ overflowX: "auto", padding: "12px 16px 0" }}>
      {truncado && (
        <p role="alert" style={{ color: "var(--pink)", fontSize: 13, marginBottom: 8 }}>
          <Ic n="aviso" s={14} /> El panel trajo {todos.length} comercios y hay más: estos totales y el
          contador de la pestaña están incompletos.
        </p>
      )}
      <table style={{ width: "100%", minWidth: 480, borderCollapse: "collapse", fontSize: 13 }}>
        <caption style={{ captionSide: "top", textAlign: "left", fontSize: 12, color: "var(--txt-3)", paddingBottom: 6 }}>
          Resumen por ciudad · tocá una fila para elegirla
        </caption>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border)" }}>
            <th scope="col" style={{ ...th, textAlign: "left" }}>Ciudad</th>
            <th scope="col" style={th}>Total</th>
            <th scope="col" style={th}>Con foto sin clasificar</th>
            <th scope="col" style={th}>Incompletos</th>
            <th scope="col" style={th}>Sin horario</th>
            <th scope="col" style={th}>Sin verificar</th>
          </tr>
        </thead>
        <tbody>
          {lista.map((f) => {
            const sel = f.elegible && elegida === f.slug;
            return (
              <tr key={f.slug || "sin-ciudad"}
                  onClick={f.elegible ? () => elegir(f.slug) : undefined}
                  style={{ borderBottom: "1px solid var(--border)", cursor: f.elegible ? "pointer" : "default",
                           background: sel ? "rgba(57,255,158,.10)" : "transparent", fontWeight: sel ? 700 : 400 }}>
                <th scope="row" style={{ textAlign: "left", padding: "7px 10px", fontWeight: "inherit" }}>
                  {f.elegible ? (
                    // El botón es para teclado y lector de pantalla; la fila entera también responde al clic.
                    <button type="button" aria-pressed={sel} onClick={(e) => { e.stopPropagation(); elegir(f.slug); }}
                            style={btnFila}>
                      {sel ? <Ic n="si" s={14} tono="marca" /> : <Ic n="ubicacion" s={14} />} {f.nombre}
                    </button>
                  ) : (
                    <span style={{ color: "var(--txt-3)" }} title="Estos comercios no tienen ciudad: no se pueden elegir en el selector">
                      {f.nombre}
                    </span>
                  )}
                </th>
                {celdas(f)}
              </tr>
            );
          })}
          <tr onClick={() => elegir(null)}
              style={{ cursor: "pointer", background: elegida === null ? "rgba(57,255,158,.10)" : "transparent", fontWeight: 700 }}>
            <th scope="row" style={{ textAlign: "left", padding: "7px 10px", fontWeight: "inherit" }}>
              <button type="button" aria-pressed={elegida === null} onClick={(e) => { e.stopPropagation(); elegir(null); }}
                      style={btnFila}>
                {elegida === null ? <Ic n="si" s={14} tono="marca" /> : <Ic n="ciudad" s={14} />} Todas
              </button>
            </th>
            {celdas(suma)}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function TabComercios({
  todos, truncado, rubros, onVerificar, onRechazar, onEdited, onIrCalles,
}: {
  todos: ComercioPorVerificar[];
  truncado: boolean;
  rubros: Rubro[];
  onVerificar: (id: string) => void;
  onRechazar: (id: string) => void;
  onEdited: () => void;
  /** «Calles y horarios» es su propia sección del menú; el botón de acá lleva a ella. */
  onIrCalles: () => void;
}) {
  const [filtro, setFiltro] = useState<FiltroComercio>("todos");
  // Dar de baja y reactivar piden `comercios.editar` (lo mismo que editar la ficha).
  const puedeEditar = puedo("comercios.editar");
  const [modo, setModo] = useState<"activos" | "baja">("activos");
  const [q, setQ] = useState("");
  const [orden, setOrden] = useState<OrdenComercio>("recientes");
  // Foto ampliada. Vive acá y no en cada tarjeta: el overlay va a pantalla
  // completa, así que sólo puede haber uno abierto a la vez.
  const [fotoGrande, setFotoGrande] = useState<{ src: string; alt: string } | null>(null);
  const [vista, setVista] = useState<VistaComercio>("lista");
  const [limitVis, setLimitVis] = useState(50);
  const [editandoId, setEditandoId] = useState<string | null>(null);
  // Qué fila tiene abierto el recálculo, y los rubros que se corrigieron sin
  // recargar. Recargar los 1080 después de cada corrección hace perder el lugar
  // donde ibas, que es lo que vuelve inusable una revisión larga.
  const [recalcId, setRecalcId] = useState<string | null>(null);
  const [rubroLocal, setRubroLocal] = useState<Record<string, string>>({});
  // La ciudad es la GLOBAL del panel (selector de la cabecera), no una propia de
  // esta pestaña: así Negocios, Lugares, Adornos e Importados hablan de la misma.
  const { slug: ciudad, ciudad: ciudadObj, listo: ciudadLista } = useAdminCiudad();

  const noComerciales = new Set(rubros.filter((r) => r.comercial === false).map((r) => r.slug));
  // 0) filtro por ciudad. Va PRIMERO para que los números de los chips sean
  //    los de esa ciudad: si dijeran el total, el chip diría 200 pendientes y
  //    la lista mostraría 12.
  const deLaCiudad = deCiudad(todos, ciudad);

  const nIncompletos = deLaCiudad.filter((c) => incompletoDe(c, noComerciales).length > 0).length;
  const nVerificados = deLaCiudad.filter((c) => c.verificado).length;
  const nSinHorario = deLaCiudad.filter(sinHorarioDe).length;

  // 1) filtro por estado (B incluye "incompletos")
  const porEstado = filtro === "todos" ? deLaCiudad
    : filtro === "pendientes" ? deLaCiudad.filter((c) => !c.verificado)
    : filtro === "verificados" ? deLaCiudad.filter((c) => c.verificado)
    : filtro === "sin-horario" ? deLaCiudad.filter(sinHorarioDe)
    : deLaCiudad.filter((c) => incompletoDe(c, noComerciales).length > 0);

  // 2) buscador multi-campo (A): nombre + qué vende + dirección + contacto + rubro + ciudad
  const nq = normTxt(q.trim());
  // Se busca por PALABRAS y todas tienen que estar, no la frase entera.
  //
  // Antes era `includes(nq)` sobre el texto pegado: "coca hoja" no encontraba a
  // "hoja de coca" —está en otro orden— y "juguete niño" no encontraba a una
  // juguetería que vende juguetes para niños. Escribir dos palabras devolvía
  // menos que escribir una, que es lo contrario de lo que espera cualquiera.
  //
  // Esto NO tiene tolerancia a errores de tipeo, a diferencia del buscador
  // público: acá se viene a encontrar un comercio que se sabe que existe, y
  // adivinar sería peor. "decoca" no va a aparecer nunca porque en la base dice
  // "de coca".
  const palabras = nq.split(/\s+/).filter(Boolean);
  const buscadas = !palabras.length ? porEstado : porEstado.filter((c) => {
    // El código se busca con o sin el prefijo: en el papel dice "URUKU-K7M2"
    // pero en la base sólo está "K7M2".
    const texto = [c.nombre, c.descripcion, c.prod_obs_human, c.prod_det_ia, c.subcategoria,
                   c.direccion, c.whatsapp, c.telefono, c.rubros?.nombre, c.ciudades?.nombre,
                   c.codigo, c.codigo ? `uruku-${c.codigo}` : ""]
      .map((x) => normTxt(x ?? "")).join(" ");
    return palabras.every((p) => texto.includes(p));
  });

  // 3) orden (G)
  const filtradas = [...buscadas].sort((a, b) => {
    if (orden === "alfabetico") return (a.nombre ?? "").localeCompare(b.nombre ?? "");
    if (orden === "estado") return Number(a.verificado) - Number(b.verificado);      // pendientes primero
    return (b.created_at ?? "").localeCompare(a.created_at ?? "");                    // recientes primero
  });

  // reset de la paginación cuando cambian filtros/búsqueda/orden
  useEffect(() => { setLimitVis(50); }, [filtro, q, orden, ciudad]);

  const visibles = filtradas.slice(0, limitVis);
  const editando = editandoId ? todos.find((c) => c.id === editandoId) ?? null : null;

  const chips: { key: FiltroComercio; label: string; n: number; amber?: boolean }[] = [
    { key: "todos", label: "Todos", n: deLaCiudad.length },
    { key: "pendientes", label: "Pendientes", n: deLaCiudad.filter((c) => !c.verificado).length },
    { key: "verificados", label: "Verificados", n: nVerificados },
    { key: "incompletos", label: "Incompletos", n: nIncompletos, amber: true },
    // Su propio filtro y no un motivo más de "incompleto": cargar horarios es
    // una pasada aparte —se hace de corrido, con la foto al lado— y mezclada
    // con los sin nombre y los sin foto no se puede hacer de corrido.
    { key: "sin-horario", label: "Sin horario", n: nSinHorario, amber: true },
  ];

  return (
    <div className="panel-card glass">
      {/* Por Portal: `.glass` tiene backdrop-filter y eso vuelve al contenedor
          el marco de referencia de `position: fixed`. Sin esto el overlay se
          centraría sobre la tarjeta de la lista, no sobre la pantalla — el
          mismo bug que ya nos escondió los modales. */}
      {fotoGrande && (
        <Portal>
          <ImageLightbox src={fotoGrande.src} alt={fotoGrande.alt}
                         onClose={() => setFotoGrande(null)} />
        </Portal>
      )}

      {/* Sin encabezado: el título repetía lo que ya dice la pestaña y se comía
          un renglón entero de una pantalla donde lo que hace falta es ver
          comercios. El único dato que valía —cuántos coincidieron— se movió al
          lado del buscador, sin ocupar alto propio. */}

      {/* Resumen por ciudad: arriba de todo, porque es lo que dice dónde mirar. */}
      <ResumenPorCiudad todos={todos} noComerciales={noComerciales} truncado={truncado} />

      {/* Activos o dados de baja. Sólo con permiso: la baja y la reactivación piden `comercios.editar`. */}
      {puedeEditar && (
        <div role="group" aria-label="Qué negocios ver" style={{ display: "flex", gap: 8, flexWrap: "wrap", padding: "16px 16px 0" }}>
          {([["activos", "Activos"], ["baja", "Dados de baja"]] as const).map(([k, label]) => (
            <button key={k} type="button" aria-pressed={modo === k} onClick={() => setModo(k)}
              style={{ padding: "5px 16px", minHeight: 44, borderRadius: 20, border: "1px solid", cursor: "pointer", fontSize: 13.5,
                borderColor: modo === k ? "var(--neon)" : "var(--border)",
                background: modo === k ? "var(--neon)22" : "transparent",
                color: modo === k ? "var(--neon)" : "var(--txt-2)", fontWeight: modo === k ? 600 : 400 }}>
              {label}
            </button>
          ))}
        </div>
      )}

      {modo === "baja" && puedeEditar && (
        <DadosDeBaja ciudad={ciudad} onReactivado={onEdited} />
      )}

      {modo === "activos" && (<>

      {/* Buscador (A) + orden (G) + vista lista/mapa (D) */}
      <div style={{ display: "flex", gap: 8, padding: "16px 16px 0", flexWrap: "wrap", alignItems: "center" }}>
        <input className="adm-input" style={{ flex: 1, minWidth: 200 }} value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar por nombre, código (URUKU-K7M2), productos, dirección, teléfono…" />
        {/* Sólo cuando el número dice algo: sin búsqueda ni filtro repite el
            "Todos (886)" del chip de abajo. */}
        {(q.trim() || filtro !== "todos" || ciudad) && (
          <span style={{ color: "var(--txt-3)", fontSize: 13, whiteSpace: "nowrap" }}>
            {filtradas.length} de {deLaCiudad.length}
          </span>
        )}
        <select className="adm-input" style={{ width: "auto" }} value={orden} onChange={(e) => setOrden(e.target.value as OrdenComercio)}>
          <option value="recientes">Más recientes</option>
          <option value="alfabetico">A → Z</option>
          <option value="estado">Pendientes primero</option>
        </select>
        <div style={{ display: "flex", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden" }}>
          {(["lista", "mapa"] as VistaComercio[]).map((v) => (
            <button key={v} onClick={() => setVista(v)} aria-pressed={vista === v}
              style={{ padding: "11px 16px", fontSize: 13, cursor: "pointer", border: "none",
                background: vista === v ? "var(--neon)22" : "transparent",
                color: vista === v ? "var(--neon)" : "var(--txt-2)", fontWeight: vista === v ? 600 : 400 }}>
              {v === "lista" ? "Lista" : "Mapa"}
            </button>
          ))}
        </div>
        {/* Era la tercera vista de este selector y nadie la encontraba: ahora es
            una sección del menú («Calles y horarios») y esto es un atajo. */}
        <button type="button" className="btn btn-ghost btn-sm" onClick={onIrCalles} style={{ minHeight: 44 }}>
          <Ic n="reloj" s={15} /> Calles y horarios
        </button>
      </div>

      {/* Filtros por estado */}
      <div style={{ display: "flex", gap: 8, padding: "12px 16px", borderBottom: "1px solid var(--border)", flexWrap: "wrap" }}>
        {chips.map(({ key, label, n, amber }) => {
          const activo = filtro === key;
          const col = amber ? "var(--amber)" : "var(--neon)";
          return (
            <button key={key} onClick={() => setFiltro(key)}
              style={{ padding: "5px 14px", minHeight: 44, borderRadius: 20, border: "1px solid", cursor: "pointer", fontSize: 13,
                borderColor: activo ? col : "var(--border)",
                background: activo ? `${col}22` : "transparent",
                color: activo ? col : "var(--txt-2)", fontWeight: activo ? 600 : 400 }}>
              {label} ({n})
            </button>
          );
        })}
      </div>

      {/* Clasificación masiva: arriba de la lista, porque con 161 comercios sin
          categoría es la acción más útil de esta pantalla. */}
      {ciudadLista && <AnalisisMasivo ciudad={ciudadObj} onTerminado={onEdited} />}

      {/* Vista MAPA (D): tocar un pin abre el editor; ideal para los sin nombre */}
      {vista === "mapa" ? (
        <div style={{ padding: 12 }}>
          <AdminMap
            comercios={filtradas.map((c) => ({
              id: c.id, nombre: c.nombre, lat: c.lat, lng: c.lng,
              rubro_slug: c.rubros?.slug ?? null, incompleto: incompletoDe(c, noComerciales).length > 0,
              lugar_id: c.lugar_id, lugar_nombre: c.lugares?.nombre ?? null, lugar_lat: c.lugares?.lat ?? null, lugar_lng: c.lugares?.lng ?? null, lugar_portada_thumb: c.lugares?.portada_thumb_url ?? null,
            }))}
            onSelect={setEditandoId}
            centro={ciudadObj?.lat != null && ciudadObj?.lng != null ? [ciudadObj.lat, ciudadObj.lng] : null}
          />
        </div>
      ) : (
      <>
      {visibles.length === 0 && (
        <div style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>Sin resultados.</div>
      )}

      {visibles.map((c) => {
        const motivos = incompletoDe(c, noComerciales);
        return (
        // flexWrap + minWidth en la info: en un celular los 5 botones de acción
        // no cedían espacio (flex-shrink: 0) y aplastaban el texto hasta dejar
        // una palabra por renglón. Ahora las acciones bajan a otra línea.
        <div key={c.id} className="adm-fila" style={{ display: "flex", gap: 12, padding: "14px 16px", borderBottom: "1px solid var(--border)", alignItems: "flex-start", flexWrap: "wrap" }}>
          {/* Foto — se agranda al tocarla.
              La miniatura son 64px: alcanza para ubicar la tarjeta, no para
              ver QUÉ vende el local. Y eso es lo que hay que decidir antes de
              mandar la ficha a la IA o de corregir lo que propuso. La versión
              grande es `portada_url`; la miniatura pesa 31KB y se ve borrosa
              ampliada. */}
          <button
            type="button"
            onClick={() => setFotoGrande({
              src: c.portada_url ?? c.portada_thumb_url ?? "",
              alt: c.nombre || "Comercio",
            })}
            disabled={!c.portada_url && !c.portada_thumb_url}
            title="Ver la foto en grande"
            style={{ padding: 0, border: "none", background: "none", flexShrink: 0,
                     cursor: (c.portada_url || c.portada_thumb_url) ? "zoom-in" : "default" }}
          >
            <img
              src={c.portada_thumb_url ?? c.portada_url ?? "https://picsum.photos/seed/" + c.id + "/80/80"}
              alt=""
              style={{ width: 64, height: 64, objectFit: "cover", borderRadius: 10, display: "block" }}
            />
          </button>

          {/* Info — clickeable entera. El encabezado dice "click para editar" y
              hasta ahora sólo abría el botón del lápiz: apuntar a un ícono de
              16px, 800 veces, es el doble de trabajo que tocar el nombre. */}
          <div
            onClick={() => setEditandoId(c.id)}
            title="Editar este comercio"
            style={{ flex: "1 1 200px", minWidth: 0, cursor: "pointer" }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <span style={{ fontWeight: 600, fontSize: 15 }}>{c.nombre || "Sin nombre"}</span>
              {c.verificado
                ? <span style={{ fontSize: 11, color: "var(--neon)", background: "var(--neon)22", padding: "2px 8px", borderRadius: 10 }}>verificado</span>
                : <span style={{ fontSize: 11, color: "var(--amber)", background: "var(--amber)22", padding: "2px 8px", borderRadius: 10 }}>pendiente</span>}
              {c.suspendido && <span style={{ fontSize: 11, color: "#888", background: "#88888822", padding: "2px 8px", borderRadius: 10 }}>suspendido</span>}
              {motivos.map((m) => (
                <span key={m} style={{ fontSize: 11, color: "var(--amber)", border: "1px dashed var(--amber)", padding: "1px 7px", borderRadius: 10 }}><Ic n="aviso" s={11} /> {m}</span>
              ))}
            </div>
            <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 3 }}>
              {c.codigo && <span style={{ fontFamily: "monospace", color: "var(--neon)" }}>URUKU-{c.codigo} · </span>}
              {/* Todos los rubros, con el PRINCIPAL primero y en negrita. Antes
                  se veía uno solo y se leía como "está mal clasificado" cuando
                  el correcto ya estaba puesto, sólo que segundo — que es la
                  mitad de los casos que parecían errores. */}
              {rubroLocal[c.id] ?? <RubrosDeFila c={c} />}
              {c.lugares?.nombre ? ` · ${c.lugares.nombre}${c.puesto ? ` #${c.puesto}` : ""}` : ""}
              {c.ciudades?.nombre ? ` · ${c.ciudades.nombre}` : ""}
              {c.modalidad ? ` · ${MODALIDAD_LABEL[c.modalidad] ?? c.modalidad}` : ""}
            </div>
            {/* Productos primero: es el texto del que sale la clasificación, así
                que es lo que hay que leer para decidir si el rubro está bien. */}
            {c.prod_obs_human && (
              <div style={{ fontSize: 12, color: "var(--txt)", marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {c.prod_obs_human}
              </div>
            )}
            {c.prod_det_ia && (
              <div style={{ fontSize: 12, color: "var(--blue-soft, #7aa2f7)", marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {c.prod_det_ia}{c.subcategoria ? ` · ${c.subcategoria}` : ""}
              </div>
            )}
            {c.descripcion && (
              <div style={{ fontSize: 12, color: "var(--txt-2)", marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {c.descripcion}
              </div>
            )}
          </div>

          {/* Acciones. Pueden partirse en dos renglones: con `flexShrink: 0` y sin
              wrap, a 360 px los 7-8 botones medían más que la tarjeta y
              Verificar y Rechazar quedaban cortados, sin forma de tocarlos. */}
          <div style={{ display: "flex", gap: 8, flex: "0 1 auto", minWidth: 0, flexWrap: "wrap", justifyContent: "flex-end", alignItems: "center", marginLeft: "auto" }}>
            {c.whatsapp && (
              <a
                href={`https://wa.me/${c.whatsapp}`}
                target="_blank" rel="noopener"
                className="mbtn"
                title={`WhatsApp +${c.whatsapp}`}
                style={{ display: "flex", alignItems: "center", justifyContent: "center" }}
              >
                <WhatsApp style={{ width: 16, height: 16 }} />
              </a>
            )}
            {c.lat != null && (
              <a
                href={comoLlegarHref(c)}
                target="_blank" rel="noopener"
                className="mbtn"
                title="Ver en mapa"
                style={{ display: "flex", alignItems: "center", justifyContent: "center" }}
              >
                <Pin style={{ width: 16, height: 16 }} />
              </a>
            )}
            {/* El volante con el QR de ESTE comercio, listo para imprimir.
                Se abre en otra pestaña: el que lo usa está recorriendo la lista
                y no quiere perder dónde iba. */}
            <a className="mbtn" title="Volante para imprimir" href={`/volante/${c.slug}`}
               target="_blank" rel="noopener" style={{ fontSize: 15, display: "flex",
               alignItems: "center", justifyContent: "center" }}><Ic n="imprimir" s={15} /></a>
            {/* La tarjeta de mesa: cuatro por hoja, para dejar en las mesas
                o en el mostrador. "Escaneá y mirá la carta" en los de comida. */}
            <a className="mbtn" title="Tarjeta de mesa con el QR (4 por hoja)" href={`/volante/${c.slug}/mesa`}
               target="_blank" rel="noopener" style={{ fontSize: 15, display: "flex",
               alignItems: "center", justifyContent: "center" }}><Ic n="restaurantes" s={15} /></a>
            <button className="mbtn" title="Recalcular el rubro"
                    onClick={() => setRecalcId(recalcId === c.id ? null : c.id)}
                    ><Ic n="ofertas" s={15} /></button>
            <button className="mbtn edit" title="Editar" onClick={() => setEditandoId(c.id)}>
              <Edit style={{ width: 16, height: 16 }} />
            </button>
            {!c.verificado && (
              <button className="mbtn approve" title="Verificar" onClick={() => onVerificar(c.id)}>
                <Verified style={{ width: 16, height: 16 }} />
              </button>
            )}
            {/* Baja lógica: deja de verse, el registro no se borra y se puede
                reactivar desde «Dados de baja». Por eso confirma antes. */}
            {puedeEditar && (
              <button type="button" className="btn btn-ghost btn-sm" title="Dar de baja este negocio"
                style={{ minHeight: 44, color: "var(--pink)", borderColor: "var(--pink)" }}
                onClick={() => {
                  if (window.confirm(`¿Dar de baja "${c.nombre || "este negocio"}"?

Deja de verse en URUKU. No se borra: lo podés reactivar desde «Dados de baja».`)) onRechazar(c.id);
                }}>
                <Ic n="cerrar" s={14} /> Dar de baja
              </button>
            )}
          </div>

          {/* El recálculo se abre DENTRO de la fila, a ancho completo: mandarlo
              a un modal obligaría a cerrar y volver a encontrar dónde ibas, y
              en una cola de doscientos eso es la mitad del trabajo. */}
          {recalcId === c.id && (
            <div style={{ flexBasis: "100%" }}>
              <RubroRecalcular
                comercioId={c.id}
                nombre={c.nombre || "Comercio"}
                rubroActual={c.rubros?.slug ?? null}
                rubros={rubros.map((r) => ({ slug: r.slug, nombre: r.nombre, icono: r.icono }))}
                onListo={(resumen) => {
                  setRubroLocal((prev) => ({ ...prev, [c.id]: resumen }));
                  setRecalcId(null);
                }}
                onCerrar={() => setRecalcId(null)}
              />
            </div>
          )}
        </div>
        );
      })}

      {filtradas.length > limitVis && (
        <div style={{ padding: 16, textAlign: "center" }}>
          <button className="btn btn-ghost" onClick={() => setLimitVis((n) => n + 50)}>
            Ver más ({filtradas.length - limitVis} restantes)
          </button>
        </div>
      )}
      </>
      )}

      {editando && (() => {
        // El trabajo real es pasar comercio por comercio. Cerrar el modal,
        // buscar el renglón siguiente y volver a abrirlo son tres gestos por
        // ficha; multiplicado por 800, es lo que hace que la tarea se abandone
        // a la mitad. El modal se mueve solo por la lista YA filtrada.
        const i = filtradas.findIndex((c) => c.id === editando.id);
        const saltar = (d: number) => {
          const sig = filtradas[i + d];
          if (sig) setEditandoId(sig.id);
          else { setEditandoId(null); onEdited(); }
        };
        return (
          <ModalEditar
            key={editando.id}
            comercio={editando}
            rubros={rubros}
            posicion={i >= 0 ? { actual: i + 1, total: filtradas.length } : null}
            haySiguiente={i >= 0 && i + 1 < filtradas.length}
            hayAnterior={i > 0}
            onSaltar={saltar}
            onClose={() => setEditandoId(null)}
            onDone={() => { setEditandoId(null); onEdited(); }}
          />
        );
      })()}
      </>)}
    </div>
  );
}

/** Los negocios dados de baja de la ciudad elegida, con «Reactivar». Pide su
 *  lista al abrirse (no viene con la de activos). */
function DadosDeBaja({ ciudad, onReactivado }: { ciudad: string | null; onReactivado: () => void }) {
  const [lista, setLista] = useState<ComercioDadoDeBaja[] | null>(null);
  const [err, setErr] = useState("");
  const [reactivando, setReactivando] = useState<string | null>(null);
  const [errFila, setErrFila] = useState<{ id: string; msg: string } | null>(null);

  const cargar = useCallback(() => {
    setErr(""); setLista(null);
    adminListarDadosDeBaja(ciudad).then(setLista).catch((e) => setErr(mensajeDeError(e, "No se pudieron cargar los negocios dados de baja")));
  }, [ciudad]);
  useEffect(() => { cargar(); }, [cargar]);

  async function reactivar(c: ComercioDadoDeBaja) {
    if (!window.confirm(`¿Reactivar "${c.nombre || "este negocio"}"? Vuelve a verse en URUKU.`)) return;
    setErrFila(null); setReactivando(c.id);
    try {
      await adminReactivarComercio(c.id);
      setLista((prev) => prev?.filter((x) => x.id !== c.id) ?? prev);
      onReactivado();   // la lista de activos ya no es la misma
    } catch (e) {
      setErrFila({ id: c.id, msg: mensajeDeError(e, "No se pudo reactivar") });
    } finally { setReactivando(null); }
  }

  if (err) return <ErrorSeccion mensaje={err} onReintentar={cargar} />;
  if (!lista) return <CargandoSeccion texto="Cargando los negocios dados de baja…" />;
  if (lista.length === 0) {
    return <div style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>
      <Ic n="listo" s={16} /> No hay negocios dados de baja{ciudad ? " en esta ciudad" : ""}.
    </div>;
  }
  return (
    <div>
      <div style={{ padding: "12px 16px", color: "var(--txt-3)", fontSize: 13 }}>
        {lista.length} {lista.length === 1 ? "negocio dado de baja" : "negocios dados de baja"}. No se ven en URUKU hasta que los reactives.
      </div>
      {lista.map((c) => (
        <div key={c.id} style={{ display: "flex", gap: 12, padding: "12px 16px", borderTop: "1px solid var(--border)", alignItems: "center", flexWrap: "wrap" }}>
          {c.portada_thumb_url
            ? <img src={c.portada_thumb_url} alt="" style={{ width: 56, height: 56, objectFit: "cover", borderRadius: 10, flexShrink: 0 }} />
            : <div aria-hidden style={{ width: 56, height: 56, borderRadius: 10, background: "var(--border)", display: "grid", placeItems: "center", flexShrink: 0 }}><Ic n="comercios" s={22} /></div>}
          <div style={{ flex: "1 1 200px", minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: 15 }}>{c.nombre || "Sin nombre"}</div>
            <div style={{ fontSize: 12, color: "var(--txt-3)" }}>
              {c.rubro_nombre ?? "Sin rubro"}
              {c.updated_at ? ` · dado de baja ${new Date(c.updated_at).toLocaleDateString("es-BO")}` : ""}
            </div>
            <div style={{ fontSize: 12, color: "var(--txt-3)" }}>
              <Ic n={c.baja_motivo === "admin" ? "cerrajeria" : "aviso"} s={12} /> {c.baja_motivo === "admin" ? "Dado de baja por el admin" : "Sin motivo registrado"}
            </div>
            {errFila?.id === c.id && <div role="alert" style={{ color: "var(--pink)", fontSize: 12.5, marginTop: 4 }}><Ic n="aviso" s={12} /> {errFila.msg}</div>}
          </div>
          <button type="button" className="btn btn-primary btn-sm" style={{ minHeight: 44 }} disabled={reactivando === c.id} onClick={() => reactivar(c)}>
            <Ic n="actualizar" s={14} /> {reactivando === c.id ? "Reactivando…" : "Reactivar"}
          </button>
        </div>
      ))}
    </div>
  );
}

/** Deja el campo como una URL que `href` pueda abrir.
 *
 * Lo que se copia de un celular es "@lobito" o "instagram.com/lobito", nunca la
 * URL completa. La ficha pública pone el valor crudo en `href`, así que sin
 * esto quedaba un enlace relativo — uruku.bo/@lobito, un 404 con cara de red
 * social cargada. Devuelve undefined si está vacío para no pisar con "". */
function normalizarRed(valor: string, base: string): string | undefined {
  const v = valor.trim();
  if (!v) return undefined;
  if (/^https?:\/\//i.test(v)) return v;
  if (v.includes(".") && !v.startsWith("@")) return `https://${v.replace(/^\/+/, "")}`;
  return base + v.replace(/^@+/, "");
}

/** Un `fieldset` sin su marco: sólo sirve para deshabilitar de una vez todos los
 *  campos de adentro (sólo lectura), sin tocar uno por uno. */
const FS_MODAL: React.CSSProperties = { border: 0, margin: 0, padding: 0, minWidth: 0, display: "flex", flexDirection: "column", gap: 12 };

/** La portada vigente de un negocio, como la maneja el modal. */
type PortadaAdmin = { url: string | null; thumb: string | null };

function ModalEditar({
  comercio, rubros, onClose, onDone,
  posicion = null, haySiguiente = false, hayAnterior = false, onSaltar,
}: {
  comercio: ComercioPorVerificar;
  rubros: Rubro[];
  onClose: () => void;
  onDone: () => void;
  posicion?: { actual: number; total: number } | null;
  haySiguiente?: boolean;
  hayAnterior?: boolean;
  onSaltar?: (delta: number) => void;
}) {
  // Si no tiene cartel, el campo arranca vacío: lo que hay en `nombre` lo armó
  // la base y no es algo que se edite — se cambia poniéndole el nombre real.
  const [sinCartel, setSinCartel] = useState(!!comercio.sin_cartel);
  const [nombre, setNombre] = useState(comercio.sin_cartel ? "" : comercio.nombre);
  const [whatsapp, setWhatsapp] = useState(comercio.whatsapp ?? "");
  const [telefono, setTelefono] = useState((comercio as Record<string, unknown>).telefono as string ?? "");
  const [descripcion, setDescripcion] = useState(comercio.descripcion ?? "");
  // "mayorista" de arranque y no "local": local no es un valor válido —la base
  // acepta mayorista, minorista o ambos— y era el que el desplegable mandaba
  // cuando el comercio tenía "ambos" y no encontraba su opción.
  const [modalidad, setModalidad] = useState(comercio.modalidad ?? "mayorista");
  const [direccion, setDireccion] = useState(comercio.direccion ?? "");
  const [horario, setHorario] = useState((comercio as Record<string, unknown>).horario as string ?? "");
  // Encuadre de la portada: el % vertical que va al centro del recorte. NULL
  // significa "nadie lo tocó" y se dibuja como 50, que es lo que hace el CSS
  // por defecto — pero se guarda sólo si la persona movió la barra.
  const [portadaPos, setPortadaPos] = useState<number | null>(
    ((comercio as Record<string, unknown>).portada_pos as number | null) ?? null);
  const _campo = (k: string) => (comercio as Record<string, unknown>)[k] as string ?? "";
  const [instagram, setInstagram] = useState(_campo("instagram_url"));
  const [facebook, setFacebook] = useState(_campo("facebook_url"));
  const [tiktok, setTiktok] = useState(_campo("tiktok_url"));
  const [sitioWeb, setSitioWeb] = useState(_campo("sitio_web"));
  const [email, setEmail] = useState(_campo("email"));
  const _rubroActual = (comercio.rubros as { slug: string } | undefined)?.slug;
  // TODOS los rubros del comercio, no sólo el principal. Antes se precargaba
  // uno solo: al guardar, la lista que viajaba tenía ese uno y los demás se
  // borraban sin que nadie los hubiera tocado ni visto.
  const _todosSusRubros = [
    ...(_rubroActual ? [_rubroActual] : []),
    ...(comercio.comercio_rubros ?? []).map((x) => x.rubros?.slug).filter((s): s is string => !!s),
  ];
  const [rubroSlugs, setRubroSlugs] = useState<string[]>([...new Set(_todosSusRubros)]);
  // Cuál se ve abajo del nombre en la ficha, de qué color es el pin y por cuál
  // filtra el buscador. Es el PRIMERO de la lista que se manda, y como eso era
  // invisible —dependía del orden en que se hubiera tocado cada chip— acá se
  // elige a propósito.
  const [principal, setPrincipal] = useState<string>(_rubroActual ?? _todosSusRubros[0] ?? "");
  const [prodObsHuman, setProdObsHuman] = useState(comercio.prod_obs_human ?? "");
  // «Lo que suma» (spec docs/ficha-destacados.md). Se guarda sólo lo que cambió
  // respecto de lo que trajo el comercio: así un dato viejo que el servidor ya no
  // acepta no tumba el guardado de todo lo demás.
  const tildesIniciales = useRef<Tildes>({
    tiene_pasero: comercio.tiene_pasero === true,
    envios_internacionales: comercio.envios_internacionales === true,
    tiene_factura: comercio.tiene_factura === true,
    talles_especiales: comercio.talles_especiales === true,
  });
  const [tildes, setTildes] = useState<Tildes>(tildesIniciales.current);
  const [canalWa, setCanalWa] = useState(comercio.canal_wa_url ?? "");
  const canalBase = useRef(comercio.canal_wa_url ?? "");
  const [catalogoUrl, setCatalogoUrl] = useState(comercio.catalogo_url ?? "");
  const catalogoBase = useRef(comercio.catalogo_url ?? "");
  const [pedidoMinimo, setPedidoMinimo] = useState(comercio.pedido_minimo ?? "");
  const pedidoBase = useRef(comercio.pedido_minimo ?? "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  // Sin `comercios.editar` la ficha se abre en sólo lectura: nada de Guardar,
  // Analizar ni cambiar la portada (el servidor igual contestaría 403 después de
  // haber escrito todo). La galería usa el permiso de moderar y sigue andando.
  const puedeEditar = puedo("comercios.editar");
  // El WhatsApp es la llave de la cuenta del comercio: sólo lo cambia quien tiene `comercios.cuenta`.
  const puedeCuenta = puedo("comercios.cuenta");
  // La portada vive acá y no en `comercio`: ese viene de la lista y no se entera
  // de lo que se cambia con el modal abierto.
  const [portada, setPortada] = useState<PortadaAdmin>({ url: comercio.portada_url ?? null, thumb: comercio.portada_thumb_url ?? null });
  // Lo que la IA dejó escrito en el servidor (se muestra en «Detectado por IA»).
  const [ia, setIa] = useState({ productos: comercio.prod_det_ia ?? "", subcategoria: comercio.subcategoria ?? "" });
  // Algo ya cambió en el servidor sin pasar por «Guardar» (portada, clasificación):
  // al cerrar hay que refrescar la lista de negocios.
  const cambioEnServidor = useRef(false);
  const [codigoCopiado, setCodigoCopiado] = useState<"si" | "no" | null>(null);

  function cerrar() {
    if (cambioEnServidor.current) onDone(); else onClose();
  }

  // El formulario es largo (42 categorías) y el botón Cancelar queda muy abajo:
  // sin Escape ni cruz en el encabezado, se entra al editor y no se ve cómo salir.
  const cerrarRef = useRef(cerrar);
  cerrarRef.current = cerrar;
  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => {
      // Con la foto ampliada abierta, Escape cierra la foto y no el modal.
      if (e.key === "Escape" && !document.querySelector(".lightbox-backdrop")) cerrarRef.current();
    };
    document.addEventListener("keydown", onEsc);
    return () => document.removeEventListener("keydown", onEsc);
  }, []);

  async function copiarCodigo() {
    if (!comercio.codigo) return;
    try {
      await navigator.clipboard.writeText(`URUKU-${comercio.codigo}`);
      setCodigoCopiado("si");
    } catch { setCodigoCopiado("no"); }
    setTimeout(() => setCodigoCopiado(null), 2500);
  }

  /** «Aplicar» de la IA: el servidor ya escribió la clasificación; acá se pone al
   *  día el formulario SIN cerrar el modal y sin tocar lo que se había escrito. */
  async function aplicarIA(p: PropuestaIA) {
    cambioEnServidor.current = true;
    if (p.descripcion) setDescripcion(p.descripcion);
    setIa({ productos: p.productos, subcategoria: p.subcategoria });
    // Los rubros que quedaron son los del servidor: se piden en vez de adivinarlos.
    const slugs = await rubrosDeComercio(comercio.id).catch(() => p.rubro_slugs);
    if (slugs.length) {
      setRubroSlugs(slugs);
      setPrincipal((actual) => (slugs.includes(actual) ? actual : slugs[0]));
    }
  }

  /** El PDF del catálogo ya está (o ya no está) en el servidor: se refleja en lo
   *  guardado Y en lo tipeado, para que no cuente como cambio sin guardar, y se
   *  marca para refrescar la lista al cerrar. */
  function catalogoCambio(url: string | null) {
    const v = url ?? "";
    catalogoBase.current = v;
    setCatalogoUrl(v);
    cambioEnServidor.current = true;
  }

  /** Lo de «Lo que suma» que cambió. `""` BORRA el dato. Devuelve el texto del
   *  error si un enlace no es una dirección web (en la ficha el botón sólo sale
   *  con http/https, así que no se guarda algo que después no se ve). */
  function cambiosDeSuma(): { cambios: Record<string, unknown> } | { error: string; foco: string } {
    const cambios: Record<string, unknown> = {};
    const enlaces = [
      { k: "canal_wa_url", nombre: "El canal", id: "adm-canal", valor: canalWa, base: canalBase.current },
      // Con un PDF subido, el catálogo lo manejan los botones de subir y quitar.
      ...(esCatalogoSubido(catalogoUrl) ? [] : [
        { k: "catalogo_url", nombre: "El enlace del catálogo", id: "adm-catalogo", valor: catalogoUrl, base: catalogoBase.current },
      ]),
    ];
    for (const e of enlaces) {
      const v = e.valor.trim();
      if (v === e.base.trim()) continue;
      if (!v) { cambios[e.k] = ""; continue; }
      const url = normalizarEnlace(v);
      if (!url) return { error: `${e.nombre} tiene que ser un enlace web, como https://…`, foco: e.id };
      cambios[e.k] = url;
    }
    if (pedidoMinimo.trim() !== pedidoBase.current.trim()) cambios.pedido_minimo = pedidoMinimo.trim();
    for (const k of CLAVES_TILDES) {
      if (tildes[k] !== tildesIniciales.current[k]) cambios[k] = tildes[k];
    }
    return { cambios };
  }

  async function persistir(): Promise<boolean> {
    const suma = cambiosDeSuma();
    if ("error" in suma) {
      setErr(suma.error);
      // Si la sección estaba plegada, el campo no se puede enfocar: se abre primero.
      const det = document.getElementById("adm-suma");
      if (det instanceof HTMLDetailsElement) det.open = true;
      document.getElementById(suma.foco)?.focus();
      return false;
    }
    setSaving(true);
    setErr("");
    try {
      await editarComercio(comercio.id, {
        ...suma.cambios,
        prod_obs_human: prodObsHuman || undefined,
        // Con "sin cartel" no se manda nombre: lo arma la base. Mandarlo
        // apagaría el flag (el trigger entiende "escribieron un nombre").
        sin_cartel: sinCartel,
        nombre: sinCartel ? undefined : (nombre.trim() || undefined),
        // Sin el permiso no se manda: el servidor lo rechazaría entero con 403.
        whatsapp: puedeCuenta ? (whatsapp || undefined) : undefined,
        telefono: telefono || undefined,
        descripcion: descripcion || undefined,
        modalidad: modalidad || undefined,
        direccion: direccion || undefined,
        horario: horario || undefined,
        instagram_url: normalizarRed(instagram, "https://instagram.com/"),
        facebook_url: normalizarRed(facebook, "https://facebook.com/"),
        tiktok_url: normalizarRed(tiktok, "https://tiktok.com/@"),
        sitio_web: normalizarRed(sitioWeb, "https://"),
        email: email || undefined,
        // El principal PRIMERO: el backend usa el primero de la lista para
        // `comercios.rubro_id`, que es el que se ve en la ficha.
        rubro_slugs: rubroSlugs.length
          ? [...(rubroSlugs.includes(principal) ? [principal] : []), ...rubroSlugs.filter((x) => x !== principal)]
          : undefined,
        portada_pos: portadaPos,
      });
      // Se recuerda para el "igual que el anterior" de la ficha siguiente.
      // En localStorage y no en estado: el modal se remonta con `key` en cada
      // comercio, así que cualquier estado propio se pierde justo cuando hace
      // falta.
      recordarUltimoHorario(horario);
      return true;
    } catch (e) {
      // El mensaje del servidor y no uno genérico: «Verificá el backend» mandó
      // a mirar los logs cuando lo que decía el backend era exactamente qué
      // campo estaba mal.
      setErr(e instanceof Error && e.message ? e.message : "No se pudo guardar. Verificá el backend.");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    if (await persistir()) onDone();
  }

  /** Guarda y encadena con el siguiente sin cerrar el modal.
   *
   * Si el guardado falla NO avanza: pasar de largo dejaría el cambio perdido y
   * el cartel de error tapado por la ficha siguiente. */
  async function guardarYSeguir() {
    if (await persistir()) onSaltar?.(1);
  }

  return (
    <Portal>
      <div onClick={cerrar}
        style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
        <div className="glass" onClick={(e) => e.stopPropagation()}
          style={{ width: "100%", maxWidth: 480, borderRadius: 16, padding: 24, maxHeight: "90vh", overflowY: "auto" }}>
          {/* Encabezado pegajoso: la salida tiene que estar siempre a la vista,
              no al final de un formulario de 42 chips. */}
          <div style={{ position: "sticky", top: -24, zIndex: 1, background: "var(--panel, #12161d)",
                        margin: "-24px -24px 14px", padding: "18px 24px 12px",
                        display: "flex", alignItems: "center", justifyContent: "space-between",
                        borderBottom: "1px solid var(--border)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
              <h3 style={{ margin: 0 }}>Editar negocio</h3>
              {posicion && (
                <span style={{ fontSize: 12, color: "var(--txt-3)", whiteSpace: "nowrap" }}>
                  {posicion.actual} de {posicion.total}
                </span>
              )}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {onSaltar && (
                <>
                  <button type="button" className="mbtn" title="Anterior (sin guardar)"
                    disabled={!hayAnterior} onClick={() => onSaltar(-1)}
                    style={{ opacity: hayAnterior ? 1 : .35 }}>←</button>
                  <button type="button" className="mbtn" title="Siguiente (sin guardar)"
                    disabled={!haySiguiente} onClick={() => onSaltar(1)}
                    style={{ opacity: haySiguiente ? 1 : .35 }}>→</button>
                </>
              )}
            <button type="button" onClick={cerrar} aria-label="Cerrar"
              style={{ background: "none", border: "none", color: "var(--txt-2)", fontSize: 22, cursor: "pointer", lineHeight: 1, minWidth: 44, minHeight: 44 }}>
              <Ic n="cerrar" s={16} />
            </button>
            </div>
          </div>
          {!puedeEditar && (
            <div role="status" style={{ display: "flex", gap: 8, alignItems: "flex-start", marginTop: 4, padding: "10px 12px", borderRadius: 10,
                                        border: "1px solid var(--amber)", background: "rgba(255,176,32,.08)", fontSize: 13, lineHeight: 1.45 }}>
              <span style={{ flexShrink: 0, marginTop: 1 }}><Ic n="seguridad" s={16} /></span>
              <span>Sólo lectura: tu cuenta no tiene permiso para editar negocios. Las fotos de la galería sí las podés agregar o borrar.</span>
            </div>
          )}

          {/* ARRIBA DE TODO, la foto principal: es lo primero que ve el comprador y
              lo que más se viene a cambiar. «Subir otra» la reemplaza; el recorte
              sólo mueve qué parte se ve en la tarjeta de resultados. */}
          <div style={{ marginTop: 12 }}>
            <FotoPrincipal
              url={portada.url ?? portada.thumb}
              soloLectura={!puedeEditar}
              textoBoton="Subir otra"
              compacto
              aspecto="2 / 1"
              recorte={puedeEditar ? { valor: portadaPos, onChange: setPortadaPos } : undefined}
              confirmarCambio="La foto principal actual se reemplaza y no queda guardada. Si querés conservarla, elegí otra de la galería con «Usar como portada». ¿Subir una nueva igual?"
              onSubir={async (f) => {
                const r = await adminSubirPortada(comercio.id, f);
                setPortada({ url: r.portada_url, thumb: r.portada_thumb_url });
                setPortadaPos(null);            // el servidor reinicia el recorte con la foto nueva
                cambioEnServidor.current = true;
                return r.portada_url;
              }}
            />
          </div>

          <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 12 }}>
            <fieldset disabled={!puedeEditar} style={FS_MODAL}>
              <div style={{ fontSize: 12, color: "var(--txt-3)" }}>
                Nombre
                {sinCartel ? (
                  // Sin cartel: no hay nada que tipear. Se muestra cómo se
                  // llama ahora —lo armó la base— para que quien edita vea
                  // exactamente lo que ve el comprador.
                  <div style={{ marginTop: 4, padding: "10px 12px", borderRadius: 11,
                                border: "1px dashed var(--border)", background: "rgba(255,255,255,.02)" }}>
                    <b style={{ fontSize: 16 }}>{comercio.nombre}</b>
                    <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginTop: 3 }}>
                      Lo arma URUKU con lo que vende y dónde está. Se actualiza solo si cambia el rubro o la calle.
                    </div>
                  </div>
                ) : (
                  <input className="adm-input" style={{ marginTop: 4, fontSize: 16, fontWeight: 600 }}
                    value={nombre} onChange={(e) => setNombre(e.target.value)}
                    autoFocus={puedeEditar} placeholder="El nombre del cartel" />
                )}
                {/* En Bermejo la mayoría de los puestos no tiene cartel. Decirlo
                    es un dato, no un campo sin llenar: 555 de 1.248 figuraban
                    como "sin nombre", un defecto que nadie podía arreglar. */}
                <label style={{ display: "flex", gap: 7, alignItems: "flex-start", marginTop: 8, cursor: "pointer" }}>
                  <input type="checkbox" checked={sinCartel}
                         onChange={(e) => { setSinCartel(e.target.checked); if (!e.target.checked) setNombre(""); }} />
                  <span style={{ fontSize: 12.5, color: "var(--txt-2)" }}>
                    No tiene cartel ni nombre propio
                  </span>
                </label>
              </div>
              {/* El código dice para qué sirve: antes era un «URUKU-XXXX» suelto. */}
              {comercio.codigo && (
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", fontSize: 12.5, color: "var(--txt-2)" }}>
                  <span>Código para publicar por WhatsApp:</span>
                  <b style={{ fontFamily: "monospace", color: "var(--neon)", fontSize: 14 }}>URUKU-{comercio.codigo}</b>
                  <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} onClick={copiarCodigo}>
                    <Ic n="documento" s={14} /> Copiar
                  </button>
                  <span role="status" style={{ fontSize: 12, color: codigoCopiado === "no" ? "var(--pink)" : "var(--neon)" }}>
                    {codigoCopiado === "si" && "Copiado"}
                    {codigoCopiado === "no" && "No se pudo copiar: seleccionalo a mano"}
                  </span>
                </div>
              )}
            <label style={{ fontSize: 12, color: "var(--txt-3)" }}>WhatsApp (opcional)
              <input className="adm-input" style={{ marginTop: 4 }} value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)} placeholder="591XXXXXXXX"
                disabled={!puedeCuenta} aria-describedby={puedeCuenta ? undefined : "wa-llave"} />
              {!puedeCuenta && (
                <span id="wa-llave" style={{ display: "block", marginTop: 4, fontSize: 12, color: "var(--amber)" }}>
                  <Ic n="aviso" s={12} /> El WhatsApp es la llave de la cuenta: lo cambia un admin o moderador
                </span>
              )}
            </label>
            <label style={{ fontSize: 12, color: "var(--txt-3)" }}>Teléfono (opcional)
              <input className="adm-input" style={{ marginTop: 4 }} value={telefono} onChange={(e) => setTelefono(e.target.value)} placeholder="Fijo o celular para llamar" />
            </label>
            <label style={{ fontSize: 12, color: "var(--txt-3)" }}>Productos observados (dato humano — la IA no lo toca)
              <textarea className="adm-input" style={{ marginTop: 4, minHeight: 56, resize: "vertical" }} value={prodObsHuman}
                onChange={(e) => setProdObsHuman(e.target.value)}
                placeholder="zapatillas, championes, chinelas, mochilas" />
            </label>
            {ia.productos && (
              <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Detectado por IA
                <div style={{ marginTop: 4, padding: 8, border: "1px solid var(--border)", borderRadius: 8, color: "var(--txt-2)" }}>
                  {ia.productos}
                  {ia.subcategoria && <div style={{ opacity: .8, marginTop: 4 }}>Subcategoría: {ia.subcategoria}</div>}
                </div>
              </div>
            )}
            <label style={{ fontSize: 12, color: "var(--txt-3)" }}>Descripción (la regenera la IA en cada análisis)
              <textarea className="adm-input" style={{ marginTop: 4, minHeight: 70, resize: "vertical" }} value={descripcion} onChange={(e) => setDescripcion(e.target.value)} placeholder="Se completa al analizar las fotos" />
            </label>
            </fieldset>

            {/* La clave de acceso del comercio: sólo con `comercios.cuenta`. Va FUERA
                del fieldset (que se desactiva sin `comercios.editar`): no edita la ficha. */}
            {puedeCuenta && <GenerarClaveComercio comercioId={comercio.id} nombre={comercio.nombre} />}

            {/* La galería va FUERA del fieldset: subir y borrar fotos usa el permiso de
                moderar, no el de editar, y tiene que andar también en sólo lectura. */}
            <FotosComercio
              comercioId={comercio.id}
              portada={portada}
              puedeEditar={puedeEditar}
              onPortada={(pt) => { setPortada(pt); setPortadaPos(null); cambioEnServidor.current = true; }}
            />

            <fieldset disabled={!puedeEditar} style={FS_MODAL}>
            <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Categorías (tocá para elegir varias)
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6,
                            maxHeight: 170, overflowY: "auto", padding: 6,
                            border: "1px solid var(--border)", borderRadius: 10 }}>
                {rubros.map((r) => {
                  const on = rubroSlugs.includes(r.slug);
                  return (
                    <button type="button" key={r.slug} className={`mchip ${on ? "active" : ""}`} style={{ cursor: "pointer" }}
                      onClick={() => setRubroSlugs((prev) => {
                        const ahora = on ? prev.filter((s) => s !== r.slug) : [...prev, r.slug];
                        // Si se destildó el principal, el principal pasa a ser
                        // otro de los que quedan: dejarlo apuntando a uno que
                        // ya no está haría que la ficha siga mostrándolo.
                        if (on && r.slug === principal) setPrincipal(ahora[0] ?? "");
                        if (!on && !principal) setPrincipal(r.slug);
                        return ahora;
                      })}>
                      {on && r.slug === principal ? <><Ic n="estrella" s={12} peso="fill" /> </> : ""}{r.nombre}
                    </button>
                  );
                })}
              </div>
              {/* Cuál manda. Es el que se ve abajo del nombre en la ficha, el
                  color del pin y por el que filtra el buscador — y hasta ahora
                  no había forma de elegirlo: salía el primero que se hubiera
                  tocado. */}
              {rubroSlugs.length > 1 && (
                <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <span style={{ fontSize: 12 }}><Ic n="estrella" s={12} peso="fill" /> El principal (es el que se ve en la ficha):</span>
                  <select className="adm-input" style={{ width: "auto" }} value={principal}
                          onChange={(e) => setPrincipal(e.target.value)}>
                    {rubroSlugs.map((sl) => (
                      <option key={sl} value={sl}>{rubros.find((r) => r.slug === sl)?.nombre ?? sl}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
            <label style={{ fontSize: 12, color: "var(--txt-3)" }}>Modalidad
              <select className="adm-input" style={{ marginTop: 4 }} value={modalidad} onChange={(e) => setModalidad(e.target.value)}>
                {/* Las tres que existen. Antes ofrecía Local, Delivery, Online
                    y Mixto —que no son modalidades de venta sino canales, y
                    ninguna existe en la base: `modalidad` sólo acepta
                    mayorista, minorista o ambos. Cuatro de las cinco opciones
                    reventaban el guardado con un 500, y las dos válidas que
                    faltaban hacían que los 53 comercios con «ambos» no se
                    pudieran editar: el desplegable no encontraba su valor,
                    mostraba «Local», y guardar cualquier cosa fallaba.

                    Sale de MODALIDAD_LABEL para que haya UNA lista: la misma
                    que usan la ficha, el buscador y la app de campo. */}
                {Object.entries(MODALIDAD_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </label>
            <label style={{ fontSize: 12, color: "var(--txt-3)" }}>Dirección
              <input className="adm-input" style={{ marginTop: 4 }} value={direccion} onChange={(e) => setDireccion(e.target.value)} placeholder="Calle, número, referencia" />
            </label>
            {/* HORARIO: el campo más caro del proyecto.
                Son 886 comercios y ninguno lo tiene, y es el dato que decide si
                alguien camina hasta el local o no. Escribirlo a mano 886 veces
                no lo hace nadie, así que acá se toca en vez de escribirse.
                "Igual que el anterior" es el que más rinde: en una cuadra los
                locales abren casi todos a la misma hora, y viniendo de a uno
                con las flechas, el anterior suele ser el vecino. */}
            <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Horario
              <EditorHorario value={horario} onChange={setHorario} />
            </div>

            {/* Las columnas y el endpoint existían desde el init; lo que no
                había era dónde escribirlas, así que la ficha pública nunca
                mostró una red social de nadie. Se puede pegar "@lobito" o el
                link entero: lo de abajo lo normaliza. */}
            <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Redes y contacto
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 6 }}>
                <input className="adm-input" value={instagram} onChange={(e) => setInstagram(e.target.value)} placeholder="Instagram: @usuario o link" />
                <input className="adm-input" value={facebook} onChange={(e) => setFacebook(e.target.value)} placeholder="Facebook: usuario o link" />
                <input className="adm-input" value={tiktok} onChange={(e) => setTiktok(e.target.value)} placeholder="TikTok: @usuario o link" />
                <input className="adm-input" value={sitioWeb} onChange={(e) => setSitioWeb(e.target.value)} placeholder="Sitio web" />
                <input className="adm-input" style={{ gridColumn: "1 / -1" }} value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email (opcional)" />
              </div>
            </div>

            {/* LO QUE SUMA: sale destacado en la ficha, cada uno si está cargado. Lo
                mismo que ve el agente y el comerciante. Plegable para no alargar
                más el modal; arranca abierto. Sin `comercios.editar` el fieldset lo
                deshabilita entero (el PDF también: sus botones quedan inertes). */}
            <details id="adm-suma" open style={{ border: "1px solid var(--border)", borderRadius: 12, padding: "4px 12px" }}>
              <summary style={{ cursor: "pointer", minHeight: 44, display: "flex", alignItems: "center", gap: 8, fontSize: 13.5, fontWeight: 600 }}>
                <Ic n="destacado" s={15} /> Lo que suma
              </summary>
              <div style={{ display: "flex", flexDirection: "column", gap: 12, paddingBottom: 12 }}>
                <TildesSuma quien="admin" valor={tildes}
                  onChange={(k, v) => { setTildes((p) => ({ ...p, [k]: v })); setErr(""); }} />
                <div>
                  <label htmlFor="adm-pedido" style={{ fontSize: 12, color: "var(--txt-3)" }}>Pedido mínimo</label>
                  <input id="adm-pedido" className="adm-input" style={{ marginTop: 4 }} value={pedidoMinimo}
                    onChange={(e) => setPedidoMinimo(e.target.value)} placeholder="Ej: 3 docenas, 200 Bs" />
                </div>
                <div>
                  <label htmlFor="adm-canal" style={{ fontSize: 12, color: "var(--txt-3)" }}>Canal de WhatsApp del comercio</label>
                  <input id="adm-canal" className="adm-input" style={{ marginTop: 4 }} inputMode="url" autoCapitalize="none"
                    value={canalWa} onChange={(e) => setCanalWa(e.target.value)}
                    placeholder="https://whatsapp.com/channel/..." />
                  <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginTop: 4 }}>El de él, donde publica sus ofertas. No el de URUKU. Vacío lo quita.</div>
                </div>
                <div>
                  <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 6 }}>Catálogo</div>
                  {/* El PDF se sube al elegirlo (como las fotos), no con «Guardar cambios». */}
                  <CatalogoPdf url={catalogoUrl}
                    subir={(file, onP) => adminSubirCatalogo(comercio.id, file, onP)}
                    quitar={() => adminQuitarCatalogo(comercio.id)}
                    onCambio={catalogoCambio} />
                  {esCatalogoSubido(catalogoUrl) ? (
                    <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginTop: 6 }}>Para usar un enlace en vez del PDF, primero quitá el PDF.</div>
                  ) : (
                    <>
                      <label htmlFor="adm-catalogo" style={{ display: "block", fontSize: 12, color: "var(--txt-3)", marginTop: 10 }}>O un enlace</label>
                      <input id="adm-catalogo" className="adm-input" style={{ marginTop: 4 }} inputMode="url" autoCapitalize="none"
                        value={catalogoUrl} onChange={(e) => setCatalogoUrl(e.target.value)}
                        placeholder="Enlace a un PDF, Drive o su tienda" />
                      <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginTop: 4 }}>Vacío lo quita. El enlace se guarda con «Guardar cambios».</div>
                    </>
                  )}
                </div>
              </div>
            </details>

              {/* Al final y plegado: es una herramienta de clasificación por IA, no la
                  acción principal sobre las fotos. «Aplicar» actualiza el formulario
                  sin cerrar el modal. */}
              <details style={{ border: "1px solid var(--border)", borderRadius: 12, padding: "4px 12px" }}>
                <summary style={{ cursor: "pointer", minHeight: 44, display: "flex", alignItems: "center", gap: 8, fontSize: 13.5, fontWeight: 600 }}>
                  <Ic n="destacado" s={15} /> Clasificar desde las fotos (IA)
                </summary>
                <div style={{ paddingBottom: 10 }}>
                  <AnalisisComercio comercioId={comercio.id} onAplicado={aplicarIA} />
                </div>
              </details>
            </fieldset>

            {err && <span role="alert" style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
            <div style={{ display: "flex", gap: 10, marginTop: 4, flexWrap: "wrap" }}>
              {puedeEditar ? (
                <>
                  <button type="button" className="btn btn-ghost" style={{ flex: 1, minWidth: 110, minHeight: 44 }} onClick={cerrar}>Cancelar</button>
                  <button type="submit" className="btn btn-primary" style={{ flex: 2, minWidth: 150, minHeight: 44 }} disabled={saving}>
                    {saving ? "Guardando…" : "Guardar cambios"}
                  </button>
                  {haySiguiente && (
                    <button type="button" className="btn btn-primary" style={{ flex: 2, minWidth: 170, minHeight: 44 }}
                      disabled={saving} onClick={guardarYSeguir}>
                      {saving ? "Guardando…" : "Guardar y siguiente →"}
                    </button>
                  )}
                </>
              ) : (
                <button type="button" className="btn btn-ghost" style={{ flex: 1, minHeight: 44 }} onClick={cerrar}>Cerrar</button>
              )}
            </div>
          </form>
        </div>
      </div>
    </Portal>
  );
}

// ── Modal Pago ────────────────────────────────────────────────────────────────

/** Clasificación por fotos de todos los comercios pendientes.
 *
 * Va de a pocos y en bucle desde el navegador, no en una sola llamada: cada
 * análisis tarda varios segundos, y 161 seguidos superan cualquier timeout y
 * chocan con el límite de frecuencia de Gemini. Así además el avance se ve y se
 * puede cortar en cualquier momento sin perder lo hecho.
 */
function AnalisisMasivo({ ciudad, onTerminado }: { ciudad: Ciudad | null; onTerminado: () => void }) {
  const [pendientes, setPendientes] = useState<number | null>(null);
  const [corriendo, setCorriendo] = useState(false);
  const [hechos, setHechos] = useState(0);
  const [ultimos, setUltimos] = useState<ResultadoTanda[]>([]);
  const [err, setErr] = useState("");
  const cancelar = useRef(false);
  const slug = ciudad?.slug;
  // La ciudad que se está mirando AHORA. `correr` compara contra esto después
  // de cada espera: una tanda que salió para otra ciudad no escribe nada acá.
  const slugActual = useRef(slug);
  slugActual.current = slug;

  // Vuelve a pedir el número al cambiar de ciudad. No mientras corre: el bucle
  // sigue con la ciudad con la que arrancó, y pisarle el contador a mitad de
  // camino mostraría otro número que no es el de lo que se está analizando.
  // Al terminar (`corriendo` vuelve a false) se pide de nuevo.
  useEffect(() => {
    if (corriendo) return;
    let vivo = true;
    pendientesAnalisis(slug).then((n) => { if (vivo) setPendientes(n); }).catch(() => { if (vivo) setPendientes(null); });
    return () => { vivo = false; };
  }, [slug, corriendo]);

  // Cambiar de ciudad corta un análisis en curso (termina la tanda que está
  // haciendo) y limpia lo mostrado: si no, seguiría gastando la IA en la ciudad
  // anterior bajo el título de la nueva. El número también se borra: mientras
  // no llega el de la ciudad nueva, el recuadro no se dibuja en vez de mostrar
  // los pendientes de la anterior.
  useEffect(() => {
    cancelar.current = true;
    setHechos(0); setUltimos([]); setErr(""); setPendientes(null);
  }, [slug]);

  async function correr() {
    const slugCorrida = slug;
    const otraCiudad = () => slugActual.current !== slugCorrida;
    setErr(""); setHechos(0); setUltimos([]); setCorriendo(true);
    cancelar.current = false;
    try {
      for (;;) {
        if (cancelar.current) break;
        const t = await analizarTanda(3, true, slugCorrida);
        // La respuesta tardó segundos. Si mientras tanto se eligió otra ciudad,
        // estos resultados son de la anterior: no se escribe ninguno, porque
        // aparecerían bajo el título de la nueva.
        if (otraCiudad()) break;
        if (t.sin_mas || t.procesados === 0) { setPendientes(0); break; }
        setHechos((n) => n + t.procesados);
        setPendientes(t.restantes);
        setUltimos((prev) => [...t.resultados, ...prev].slice(0, 12));

        const fallo = t.resultados.find((r) => r.error);
        if (fallo) { setErr(`Se detuvo en "${fallo.nombre}": ${fallo.error}`); break; }
        if (t.restantes === 0) break;
        // Respiro entre tandas: el límite de Gemini es por ventana de tiempo, y
        // encadenar sin pausa es lo que dispara el 429.
        await new Promise((r) => setTimeout(r, 2500));
      }
    } catch (e) {
      // El error de una tanda de otra ciudad tampoco se muestra acá.
      if (!otraCiudad()) setErr(e instanceof Error ? e.message : "Falló el análisis");
    } finally {
      setCorriendo(false);
      onTerminado();
    }
  }

  if (pendientes === null) return null;
  if (pendientes === 0 && !corriendo && hechos === 0) return null;

  return (
    <div style={{ border: "1px solid var(--neon)", background: "rgba(57,255,158,.06)",
                  borderRadius: 12, padding: 14, margin: "0 16px 12px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14 }}>Clasificar por fotos{ciudad ? ` · ${ciudad.nombre}` : ""}</div>
          <div style={{ fontSize: 12.5, color: "var(--txt-3)", marginTop: 2 }}>
            {corriendo
              ? `Analizando… ${hechos} listos · ${pendientes} por delante`
              : hechos > 0
                ? `${hechos} clasificados${pendientes ? ` · quedan ${pendientes}` : " · no queda ninguno"}`
                : `${pendientes} comercios con foto sin clasificar`}
          </div>
        </div>
        {corriendo ? (
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => { cancelar.current = true; }}>
            Detener
          </button>
        ) : (
          <button type="button" className="btn btn-primary btn-sm" onClick={correr} disabled={!pendientes}>
            Analizar {pendientes} pendientes
          </button>
        )}
      </div>

      {err && <div style={{ color: "var(--pink)", fontSize: 12.5, marginTop: 8 }}>{err}</div>}

      {ultimos.length > 0 && (
        <div style={{ marginTop: 10, borderTop: "1px solid var(--border)", paddingTop: 8, fontSize: 12 }}>
          {ultimos.map((r, i) => (
            <div key={`${r.slug}-${i}`} style={{ display: "flex", gap: 8, padding: "3px 0" }}>
              <span style={{ color: r.error ? "var(--pink)" : r.confianza >= 0.7 ? "var(--neon)" : "var(--amber)" }}>
                {r.error ? "error" : `${Math.round(r.confianza * 100)}%`}
              </span>
              <b style={{ minWidth: 120 }}>{r.nombre}</b>
              <span style={{ color: "var(--txt-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {r.error ?? `${r.subcategoria || "—"} · ${r.productos || "nada detectado"}`}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Saca el contenido al <body>.
 *
 * Los modales viven dentro de `.panel-card.glass`, y `.glass` tiene
 * backdrop-filter. Un elemento con backdrop-filter se vuelve el marco de
 * referencia de todo `position: fixed` que tenga adentro, así que el modal no se
 * centraba en la pantalla sino sobre la tarjeta de la lista: había que scrollear
 * hasta el fondo para encontrarlo. En el celular quedaba directamente perdido.
 */
function Portal({ children }: { children: React.ReactNode }) {
  const [montado, setMontado] = useState(false);
  useEffect(() => setMontado(true), []);
  if (!montado) return null;
  return createPortal(children, document.body);
}

/** Clasificación por fotos: propone y, si el admin acepta, aplica.
 *
 * La propuesta se muestra SIEMPRE antes de escribir. El modelo es elocuente
 * aunque no vea nada —ante una persiana cerrada va a inventar algo plausible—,
 * así que la confianza va en grande y la decisión es de una persona. */
function AnalisisComercio({ comercioId, onAplicado }: { comercioId: string; onAplicado: (p: PropuestaIA) => void | Promise<void> }) {
  const [res, setRes] = useState<AnalisisIA | null>(null);
  const [cargando, setCargando] = useState(false);
  const [aplicando, setAplicando] = useState(false);
  const [aplicado, setAplicado] = useState(false);
  const [err, setErr] = useState("");

  async function analizar() {
    setErr(""); setCargando(true); setRes(null); setAplicado(false);
    try { setRes(await analizarComercio(comercioId, false)); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo analizar"); }
    finally { setCargando(false); }
  }

  async function aplicar() {
    setErr(""); setAplicando(true);
    try {
      // Lo que quedó escrito es lo de ESTA llamada (vuelve a mirar las fotos), no
      // necesariamente lo que se vio en la vista previa: el formulario se pone al día con esto.
      const r = await analizarComercio(comercioId, true);
      setRes(null);
      await onAplicado(r.propuesta);
      setAplicado(true);
    } catch (e) { setErr(e instanceof Error ? e.message : "No se pudo aplicar"); }
    finally { setAplicando(false); }
  }

  const p = res?.propuesta;
  const conf = p?.confianza ?? 0;
  const colorConf = conf >= 0.7 ? "var(--neon)" : conf >= 0.4 ? "var(--amber)" : "var(--pink)";
  const etiquetaConf = conf >= 0.7 ? "alta" : conf >= 0.4 ? "media" : "baja";

  return (
    <div style={{ border: "1px solid var(--neon)", background: "rgba(57,255,158,.06)",
                  borderRadius: 12, padding: 14 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <span style={{ fontSize: 13.5, fontWeight: 600 }}>Clasificar desde las fotos</span>
        <button type="button" className={res ? "btn btn-ghost btn-sm" : "btn btn-primary btn-sm"}
          disabled={cargando} onClick={analizar}>
          {cargando ? "Mirando las fotos…" : res ? "Analizar de nuevo" : "Analizar"}
        </button>
      </div>

      {err && <div role="alert" style={{ color: "var(--pink)", fontSize: 12.5, marginTop: 8 }}>{err}</div>}
      {aplicado && !res && (
        <div role="status" style={{ color: "var(--neon)", fontSize: 12.5, marginTop: 8 }}>
          <Ic n="listo" s={14} /> Aplicado: la descripción, los productos detectados y las categorías ya están actualizados arriba. Lo que escribiste sigue ahí.
        </div>
      )}

      {p && (
        <div style={{ marginTop: 10, fontSize: 12.5, lineHeight: 1.5 }}>
          <div style={{ marginBottom: 8 }}>
            Confianza <b style={{ color: colorConf }}>{etiquetaConf} ({Math.round(conf * 100)}%)</b>
            <span style={{ color: "var(--txt-3)" }}> · {p.fotos_analizadas} foto(s) analizada(s)</span>
            {p.tokens?.total != null && (
              // Entrada y salida por separado: la salida cuesta ~8 veces más y
              // en los modelos que razonan incluye los tokens de pensamiento.
              // Con el total solo no se ve si el costo se fue por ese lado.
              <span style={{ color: "var(--txt-3)" }}>
                {" · "}{p.tokens.total.toLocaleString("es-BO")} tokens
                {p.tokens.entrada != null && p.tokens.salida != null && (
                  <> ({p.tokens.entrada.toLocaleString("es-BO")} entrada +{" "}
                  <b style={{ color: p.tokens.salida > 1000 ? "var(--amber)" : "inherit" }}>
                    {p.tokens.salida.toLocaleString("es-BO")} salida
                  </b>)</>
                )}
              </span>
            )}
          </div>

          {/* Un fallo de la llamada NO es lo mismo que "no vio nada": antes las
              dos cosas mostraban el mismo cartel y no había cómo distinguirlas. */}
          {p.error ? (
            <div style={{ color: "var(--pink)", marginBottom: 8 }}>
              <Ic n="aviso" s={14} /> La llamada al modelo falló: {p.error}
            </div>
          ) : conf < 0.4 && (
            <div style={{ color: "var(--amber)", marginBottom: 8 }}>
              El modelo miró las fotos y no reconoció mercadería. Abrí la foto para
              ver si efectivamente no se ve nada, o si hay que sacar otra.
            </div>
          )}

          <div><b>Productos:</b> {p.productos || <i style={{ color: "var(--txt-3)" }}>nada detectado</i>}</div>
          <div><b>Subcategoría:</b> {p.subcategoria || <i style={{ color: "var(--txt-3)" }}>—</i>}</div>
          <div><b>Categorías:</b> {p.rubro_slugs.length ? p.rubro_slugs.join(", ") : <i style={{ color: "var(--txt-3)" }}>ninguna</i>}</div>
          {/* Sin esto, un rubro descartado se ve igual que un rubro no propuesto:
              "ninguna", sin explicación. Saber QUÉ propuso el modelo es lo que
              permite corregir la taxonomía o el prompt. */}
          {p.slugs_descartados && p.slugs_descartados.length > 0 && (
            <div style={{ color: "var(--amber)" }}>
              Propuso categorías que no existen y se descartaron: {p.slugs_descartados.join(", ")}
            </div>
          )}
          {p.descripcion && <div style={{ marginTop: 6 }}><b>Descripción:</b> {p.descripcion}</div>}

          <div style={{ color: "var(--txt-3)", marginTop: 8, fontSize: 11.5 }}>
            Al aplicar se guardan en <b>prod_det_ia</b>, <b>subcategoría</b> y
            se <b>reemplaza la descripción</b>.
            Tus productos observados no se tocan
            {res?.comercio.prod_obs_human ? ` (siguen siendo: "${res.comercio.prod_obs_human}")` : ""}.
          </div>

          {p.crudo && (
            <details style={{ marginTop: 8 }}>
              <summary style={{ cursor: "pointer", color: "var(--txt-3)", fontSize: 11.5 }}>
                Ver la respuesta del modelo
              </summary>
              <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 11,
                            color: "var(--txt-3)", marginTop: 6, maxHeight: 180, overflowY: "auto" }}>
                {p.crudo}
              </pre>
            </details>
          )}

          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <button type="button" className="btn btn-ghost btn-sm" style={{ flex: 1 }} onClick={() => setRes(null)}>
              Descartar
            </button>
            <button type="button" className="btn btn-primary btn-sm" style={{ flex: 2 }}
              disabled={aplicando || conf <= 0} onClick={aplicar}>
              {aplicando ? "Aplicando…" : "Aplicar"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Fotos del comercio dentro del editor.
 *
 * Existe porque para saber qué vende un local muchas veces hay que MIRAR la
 * vidriera: el texto que trajo el agente no siempre alcanza para clasificarlo.
 *
 * Va DENTRO del modal. Antes todo su contenido estaba envuelto en un `<Portal>`
 * (que lo monta en `document.body`), y eso lo sacaba del modal: quedaba debajo del
 * fondo oscuro, sin poder verse ni tocarse. El único pedazo que de verdad tiene
 * que ir al `body` es la foto ampliada —`.glass` tiene backdrop-filter y un
 * `position: fixed` adentro se centraría sobre el modal, no sobre la pantalla—, y
 * ese sí lleva su Portal.
 *
 * `puedeEditar`: sin `comercios.editar` no hay «Usar como portada» (el servidor
 * contestaría 403); agregar y borrar fotos usa otro permiso (moderar) y sigue.
 */
function FotosComercio({ comercioId, portada, puedeEditar, onPortada }: {
  comercioId: string;
  portada: PortadaAdmin;
  puedeEditar: boolean;
  onPortada: (p: PortadaAdmin) => void;
}) {
  // `null` = todavía no llegó la lista (cargando); distinto de «no tiene fotos».
  const [fotos, setFotos] = useState<FotoComercio[] | null>(null);
  const [errLista, setErrLista] = useState("");
  const [ampliada, setAmpliada] = useState<string | null>(null);
  // «3 de 8» mientras sube varias; null = no está subiendo.
  const [subiendo, setSubiendo] = useState<{ n: number; de: number } | null>(null);
  const [cambiando, setCambiando] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const input = useRef<HTMLInputElement>(null);

  const cargar = useCallback(() => {
    setErrLista("");
    adminListarFotos(comercioId).then(setFotos).catch((e) => setErrLista(mensajeDeError(e, "No se pudieron cargar las fotos")));
  }, [comercioId]);
  useEffect(() => { cargar(); }, [cargar]);

  // Tope de fotos del plan del comercio: el admin sólo puede reemplazar la más
  // vieja (no paga extras por el comercio).
  const [tope, setTope] = useState<{ datos: TopeFotos; file: File } | null>(null);

  /** Sube una o varias, de a una (como la galería del agente y del comercio).
   *  Si una choca con el tope del plan, frena ahí: se abre el diálogo para esa
   *  foto y se avisa cuántas quedaron sin subir. */
  async function subir(files: File[], reemplazar?: string) {
    if (files.length === 0) return;
    setErr("");
    let subidas = 0;
    try {
      for (const file of files) {
        setSubiendo({ n: subidas + 1, de: files.length });
        try {
          const nueva = await adminSubirFoto(comercioId, file, reemplazar ? { reemplazar } : undefined);
          setFotos((prev) => [...(prev ?? []).filter((f) => f.id !== reemplazar), nueva]);
          setTope(null);
          subidas++;
        } catch (e) {
          const t = datosTope(e);
          const resto = files.length - subidas - 1;
          if (t) {
            setTope({ datos: t, file });
            if (resto > 0) setErr(`Llegó al tope del plan: ${resto} foto${resto === 1 ? "" : "s"} más quedaron sin subir.`);
          } else {
            setErr(mensajeDeError(e, "No se pudo subir la foto") + (resto > 0 ? ` · ${resto} sin subir` : ""));
          }
          return;
        }
      }
    } finally { setSubiendo(null); if (input.current) input.current.value = ""; }
  }

  function decidirTope(d: DecisionTope | null) {
    const t = tope;
    setTope(null);
    if (d === "reemplazar" && t?.datos.mas_vieja) subir([t.file], t.datos.mas_vieja.id);
  }

  async function borrar(id: string) {
    if (!window.confirm("¿Borrar esta foto? No se puede deshacer.")) return;
    setErr("");
    try {
      await adminBorrarFoto(comercioId, id);
      setFotos((prev) => prev?.filter((f) => f.id !== id) ?? prev);
    } catch (e) { setErr(mensajeDeError(e, "No se pudo borrar la foto")); }
  }

  /** Intercambio: la elegida pasa a ser la portada y la anterior entra a la galería. */
  async function usarComoPortada(id: string) {
    if (cambiando) return;
    setErr(""); setCambiando(id);
    try {
      const r = await adminUsarComoPortada(comercioId, id);
      setFotos(r.fotos);
      onPortada({ url: r.portada_url, thumb: r.portada_thumb_url });
    } catch (e) {
      // La portada anterior sigue igual: no se tocó nada.
      setErr(mensajeDeError(e, "No se pudo cambiar la portada") + ". La anterior sigue igual.");
    } finally { setCambiando(null); }
  }

  const hayPortada = !!(portada.url || portada.thumb);
  const celda: React.CSSProperties = { display: "flex", flexDirection: "column", gap: 6, width: 96 };
  const marco: React.CSSProperties = { position: "relative", width: 96, height: 96 };
  const imagen: React.CSSProperties = { width: 96, height: 96, objectFit: "cover", borderRadius: 10, cursor: "zoom-in", display: "block" };

  return (
    <div style={{ fontSize: 12, color: "var(--txt-3)" }}>
      Fotos del local (tocá para ampliar){fotos ? ` · ${fotos.length + (hayPortada ? 1 : 0)}` : ""}
      {fotos === null && !errLista && <div style={{ marginTop: 6 }}><span className="ash-spin" aria-hidden /> Cargando las fotos…</div>}
      {errLista && (
        <div role="alert" style={{ marginTop: 6, color: "var(--pink)" }}>
          <Ic n="aviso" s={13} /> {errLista}{" "}
          <button type="button" className="link-more" style={{ minHeight: 44 }} onClick={cargar}>Reintentar</button>
        </div>
      )}
      {fotos && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 6 }}>
          {!hayPortada && fotos.length === 0 && <span style={{ opacity: 0.7 }}>Todavía no hay fotos.</span>}
          {hayPortada && (
            <div style={celda}>
              <div style={marco}>
                <img src={(portada.thumb ?? portada.url) as string} alt="Portada actual" onClick={() => setAmpliada((portada.url ?? portada.thumb) as string)}
                  style={{ ...imagen, border: "2px solid var(--neon)" }} />
                <span style={{ position: "absolute", left: 4, bottom: 4, display: "inline-flex", alignItems: "center", gap: 3, background: "var(--neon)", color: "#04240f",
                               fontSize: 10, fontWeight: 800, textTransform: "uppercase", letterSpacing: ".03em", padding: "2px 6px", borderRadius: 999 }}>
                  <Ic n="estrella" s={10} peso="fill" /> Portada
                </span>
              </div>
            </div>
          )}
          {fotos.map((f) => (
            <div key={f.id} style={celda}>
              <div style={marco}>
                <img src={f.thumb_url ?? f.url} alt="" onClick={() => setAmpliada(f.url)} style={imagen} />
                <button type="button" onClick={() => borrar(f.id)} aria-label="Borrar foto" title="Borrar foto"
                  style={{ position: "absolute", top: -6, right: -6, background: "var(--pink)", color: "#fff",
                           border: "none", borderRadius: "50%", width: 24, height: 24, cursor: "pointer", display: "grid", placeItems: "center" }}>
                  <Ic n="cerrar" s={12} />
                </button>
              </div>
              {puedeEditar && (
                <button type="button" className="btn btn-ghost btn-sm" disabled={!!cambiando}
                  style={{ minHeight: 44, width: "100%", padding: "4px 4px", fontSize: 11.5, lineHeight: 1.2, whiteSpace: "normal", textAlign: "center" }}
                  onClick={() => usarComoPortada(f.id)}>
                  {cambiando === f.id ? "Cambiando…" : "Usar como portada"}
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <input ref={input} type="file" accept="image/*" multiple style={{ display: "none" }}
        onChange={(e) => subir(Array.from(e.target.files ?? []))} />
      <button type="button" className="btn btn-ghost btn-sm" style={{ marginTop: 8, minHeight: 44 }}
        disabled={!!subiendo} onClick={() => input.current?.click()}>
        {subiendo ? (subiendo.de > 1 ? `Subiendo ${subiendo.n} de ${subiendo.de}…` : "Subiendo…") : "+ Agregar fotos"}
      </button>
      {err && <div role="alert" style={{ color: "var(--pink)", marginTop: 6 }}><Ic n="aviso" s={13} /> {err}</div>}
      {tope && <TopeFotosDialogo tope={tope.datos} puedePagarExtra={false} onElegir={decidirTope} />}

      {/* Visor: la foto grande, sobre todo lo demás (por Portal: ver arriba). */}
      {ampliada && (
        <Portal>
          <ImageLightbox src={ampliada} alt="Foto del local" onClose={() => setAmpliada(null)} />
        </Portal>
      )}
    </div>
  );
}

function ModalGestionComercio({ comercio, onClose }: { comercio: ComercioSuscripcion; onClose: () => void }) {
  const [confiable, setConfiable] = useState(!!comercio.confiable);
  const [rubros, setRubros] = useState<Rubro[]>([]);
  useEffect(() => { getRubros().then(setRubros).catch(() => {}); }, []);
  const [numeros, setNumeros] = useState<NumeroComercio[]>([]);
  const [nuevo, setNuevo] = useState("");
  const [etiqueta, setEtiqueta] = useState("");
  const [err, setErr] = useState("");
  const [cargando, setCargando] = useState(true);
  const [grupos, setGrupos] = useState<GrupoComercio[]>([]);
  // WAHA sólo lee (decisión del 11/9): los grupos se crean a mano desde la
  // tablet. Con esto puesto, el botón de crear no se ofrece.
  const [soloLectura, setSoloLectura] = useState(true);
  const [grupoNuevo, setGrupoNuevo] = useState("");
  const [errGrupo, setErrGrupo] = useState("");
  const [misRubros, setMisRubros] = useState<string[] | null>(null);
  const [errRubros, setErrRubros] = useState("");

  useEffect(() => {
    listarNumeros(comercio.id)
      .then((r) => setNumeros(r.items ?? []))
      .catch(() => setErr("No se pudieron cargar los números"))
      .finally(() => setCargando(false));
    listarGrupos(comercio.id)
      .then((r) => { setGrupos(r.items ?? []); setSoloLectura(r.solo_lectura ?? true); })
      .catch(() => setErrGrupo("No se pudieron cargar los grupos"));
    rubrosDeComercio(comercio.id)
      .then(setMisRubros)
      .catch(() => setErrRubros("No se pudieron cargar los rubros"));
  }, [comercio.id]);

  async function atar(e: React.FormEvent) {
    e.preventDefault();
    setErrGrupo("");
    try {
      const r = await atarGrupo(comercio.id, grupoNuevo.trim());
      setGrupos(r.grupos ?? []);
      setGrupoNuevo("");
    } catch (e2) {
      setErrGrupo(e2 instanceof Error ? e2.message : "No se pudo atar");
    }
  }

  // Un toque agrega o saca. Se guarda al instante y se revierte si falla: en un
  // trabajo de ir comercio por comercio, un botón "Guardar" por cada cambio es
  // el doble de toques y una oportunidad más de olvidárselo.
  async function toggleRubro(slug: string) {
    if (misRubros === null) return;
    const antes = misRubros;
    const ahora = antes.includes(slug) ? antes.filter((s) => s !== slug) : [...antes, slug];
    setMisRubros(ahora); setErrRubros("");
    try {
      setMisRubros(await editarRubrosComercio(comercio.id, ahora));
    } catch (e) {
      setMisRubros(antes);
      setErrRubros(e instanceof Error ? e.message : "No se pudo guardar");
    }
  }

  async function crearGrupo() {
    setErrGrupo("");
    if (!window.confirm(
      `Se va a crear un grupo de WhatsApp con ${comercio.nombre} y los números de URUKU. ` +
      `El comerciante lo va a ver aparecer en su teléfono. ¿Seguimos?`)) return;
    setGrupoNuevo("");
    try {
      const r = await crearGrupoComercio(comercio.id);
      setGrupos(r.grupos ?? []);
    } catch (e) {
      setErrGrupo(e instanceof Error ? e.message : "No se pudo crear el grupo");
    }
  }

  async function soltar(jid: string) {
    setErrGrupo("");
    try {
      const r = await soltarGrupo(comercio.id, jid);
      setGrupos(r.grupos ?? []);
    } catch {
      setErrGrupo("No se pudo soltar el grupo");
    }
  }

  async function toggleConfiable() {
    const valor = !confiable;
    setConfiable(valor);
    try { await setConfiable_(comercio.id, valor); }
    catch { setConfiable(!valor); setErr("No se pudo cambiar"); }
  }

  async function agregar(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      const r = await agregarNumero(comercio.id, nuevo.trim(), etiqueta.trim() || undefined);
      setNumeros((prev) => [...prev.filter((n) => n.numero !== r.numero.numero), r.numero]);
      setNuevo(""); setEtiqueta("");
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "No se pudo autorizar");
    }
  }

  return (
    <Portal>
      <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
        <div className="glass" style={{ width: "100%", maxWidth: 460, borderRadius: 16, padding: 24, maxHeight: "90vh", overflowY: "auto" }}>
          <h3 style={{ marginBottom: 4 }}>{comercio.nombre}</h3>
          <p style={{ color: "var(--txt-3)", fontSize: 13, marginBottom: 18 }}>Código, confianza y números autorizados</p>

          {/* Código del local: identificador estable de cara al dueño. El celular
              puede cambiar; esto no. Con él publica por WhatsApp desde cualquier
              número, sin cuenta y sin haber pagado. */}
          {comercio.codigo && (
            <div style={{ padding: 12, borderRadius: 10, background: "var(--panel)", border: "1px solid var(--border)", marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 4 }}>Código del local</div>
              <div style={{ fontFamily: "monospace", fontSize: 22, fontWeight: 700, letterSpacing: 2, color: "var(--neon)" }}>
                URUKU-{comercio.codigo}
              </div>
              <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}>
                Escribiéndolo en un WhatsApp, sus ofertas caen en este comercio.
              </div>
            </div>
          )}

          {/* Confiable */}
          <label style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 0", borderBottom: "1px solid var(--border)", cursor: "pointer" }}>
            <input type="checkbox" checked={confiable} onChange={toggleConfiable} />
            <div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>Comercio confiable</div>
              <div style={{ fontSize: 12, color: "var(--txt-3)" }}>
                Lo que publique sale directo, sin pasar por moderación.
              </div>
            </div>
          </label>

          {/* Rubros: agregar y sacar de a un toque. Es el trabajo que hay que
              hacer comercio por comercio, así que no lleva botón de guardar. */}
          <div style={{ marginTop: 16, paddingBottom: 16, borderBottom: "1px solid var(--border)" }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Rubros</div>
            <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 10 }}>
              Tocá para agregar o sacar. El primero es el principal.
            </div>
            {misRubros === null ? (
              <div style={{ fontSize: 13, color: "var(--txt-3)" }}>Cargando…</div>
            ) : (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {rubros.map((r) => {
                  const puesto = misRubros.indexOf(r.slug);
                  return (
                    <button key={r.slug} type="button" onClick={() => toggleRubro(r.slug)}
                            style={{ padding: "5px 10px", borderRadius: 999, fontSize: 12,
                                     cursor: "pointer", border: "1px solid var(--border)",
                                     background: puesto >= 0 ? "var(--neon)" : "var(--panel)",
                                     color: puesto >= 0 ? "#000" : "var(--txt-2)",
                                     fontWeight: puesto === 0 ? 700 : 400 }}>
                      {puesto === 0 && <><Ic n="estrella" s={12} peso="fill" /> </>}{r.nombre}
                    </button>
                  );
                })}
              </div>
            )}
            {misRubros?.length === 0 && (
              <div style={{ fontSize: 12, color: "var(--amber)", marginTop: 8 }}>
                Sin rubros: no va a aparecer en ningún filtro de categoría.
              </div>
            )}
            {errRubros && <div style={{ color: "salmon", fontSize: 12, marginTop: 6 }}>{errRubros}</div>}
          </div>

          {/* Grupo de WhatsApp: el canal por el que llegan las ofertas.
              Se ata solo cuando alguien manda URUKU-XXXX adentro del grupo;
              esto es para verlo, y para atarlo a mano si hizo falta rehacerlo. */}
          <div style={{ marginTop: 16, paddingBottom: 16, borderBottom: "1px solid var(--border)" }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Grupo de WhatsApp</div>
            <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 10 }}>
              El grupo del comercio con URUKU y el testigo. Lo que se manda ahí entra como oferta.
            </div>

            {grupos.length === 0 && soloLectura && (
              <div style={{ padding: "8px 0", fontSize: 12.5, lineHeight: 1.5 }}>
                {/* El flujo manual, paso a paso, porque es lo que hay que hacer
                    y no está escrito en ningún otro lado que se vea desde acá. */}
                <b>El grupo se crea a mano:</b>
                <ol style={{ margin: "6px 0 0", paddingLeft: 18, color: "var(--txt-2)" }}>
                  <li>Desde el Samsung: grupo nuevo <span style={{ fontFamily: "monospace" }}>URUKU · {comercio.nombre}</span></li>
                  <li>Agregar al comerciante y al número de la tablet (el Registrador, el que corre WAHA)</li>
                  <li>Mandar adentro:{" "}
                    <span style={{ fontFamily: "monospace", color: "var(--neon)", fontWeight: 700 }}>
                      URUKU-{comercio.codigo ?? "XXXX"}
                    </span>
                  </li>
                </ol>
                <div style={{ color: "var(--txt-3)", marginTop: 6 }}>
                  Con el código adentro, el grupo queda atado a este comercio solo y aparece acá.
                </div>
              </div>
            )}

            {grupos.length === 0 && !soloLectura && (
              <div style={{ padding: "8px 0" }}>
                {/* El camino corto: el sistema crea el grupo y, como lo crea él,
                    sabe su identificador y lo ata en el mismo acto. Sin código,
                    sin que nadie escriba nada. */}
                <button className="btn btn-primary" style={{ width: "100%" }} onClick={crearGrupo}>
                  Crear el grupo de WhatsApp
                </button>
                <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 8, lineHeight: 1.45 }}>
                  Lo arma con {comercio.nombre} y los números de URUKU, y queda atado solo.
                  {" "}También se ata si alguien escribe{" "}
                  <span style={{ fontFamily: "monospace", color: "var(--neon)" }}>
                    URUKU-{comercio.codigo ?? "XXXX"}
                  </span>{" "}
                  adentro de un grupo ya existente.
                </div>
              </div>
            )}

            {grupos.map((g) => (
              <div key={g.grupo_jid}
                   style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 0" }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontFamily: "monospace", fontSize: 12, overflow: "hidden",
                                textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {g.nombre || g.grupo_jid}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--txt-3)" }}>
                    {g.origen === "codigo" ? "se ató con el código" : "atado a mano"}
                  </div>
                </div>
                <button onClick={() => soltar(g.grupo_jid)}
                        style={{ background: "none", border: "1px solid var(--border)",
                                 borderRadius: 8, padding: "4px 10px", fontSize: 12,
                                 color: "var(--txt-3)", cursor: "pointer" }}>
                  Soltar
                </button>
              </div>
            ))}

            <form onSubmit={atar} style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <input value={grupoNuevo} onChange={(e) => setGrupoNuevo(e.target.value)}
                     placeholder="1203630...@g.us"
                     style={{ flex: 1, minWidth: 0, padding: "8px 10px", borderRadius: 8,
                              border: "1px solid var(--border)", background: "var(--panel)",
                              color: "var(--txt-1)", fontSize: 13, fontFamily: "monospace" }} />
              <button type="submit" disabled={!grupoNuevo.trim()}
                      style={{ padding: "8px 14px", borderRadius: 8, border: "none",
                               background: "var(--neon)", color: "#000", fontSize: 13,
                               fontWeight: 600, cursor: "pointer" }}>
                Atar
              </button>
            </form>
            {errGrupo && <div style={{ color: "salmon", fontSize: 12, marginTop: 6 }}>{errGrupo}</div>}
          </div>

          {/* Números */}
          <div style={{ marginTop: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Números que pueden publicar</div>
            <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 10 }}>
              El número del local y el del empleado que manda las fotos pueden ser distintos.
              Cualquiera de estos identifica al comercio cuando escribe por WhatsApp.
            </div>

            {cargando && <div style={{ fontSize: 13, color: "var(--txt-3)" }}>Cargando…</div>}
            {!cargando && numeros.length === 0 && (
              <div style={{ fontSize: 13, color: "var(--amber)" }}>
                Ninguno. Si escribe por WhatsApp se va a crear un comercio nuevo duplicado.
              </div>
            )}
            {numeros.map((n) => (
              <div key={n.id} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--border)", fontSize: 13 }}>
                <span>+{n.numero}</span>
                <span style={{ color: "var(--txt-3)" }}>{n.etiqueta || "—"}</span>
              </div>
            ))}

            <form onSubmit={agregar} style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
              <input className="adm-input" value={nuevo} onChange={(e) => setNuevo(e.target.value)}
                placeholder="Número (ej: 70123456)" inputMode="tel" />
              <input className="adm-input" value={etiqueta} onChange={(e) => setEtiqueta(e.target.value)}
                placeholder="De quién es (ej: vendedora del local)" />
              <button type="submit" className="btn btn-primary btn-sm" disabled={!nuevo.trim()}>Autorizar número</button>
            </form>
          </div>

          {err && <div style={{ color: "var(--pink)", fontSize: 13, marginTop: 10 }}>{err}</div>}

          <button className="btn btn-ghost" style={{ width: "100%", marginTop: 18 }} onClick={onClose}>Cerrar</button>
        </div>
      </div>
    </Portal>
  );
}

/** Elegir el plan de un comercio y, si corresponde, ponerlo «de cortesía»: tiene
 *  el plan (y la estrella «Verificado por URUKU») sin pagar y sin vencimiento,
 *  para quien ayuda a URUKU. No aparece en cobros, por vencer ni vencimientos. */
function ModalPlanComercio({ comercio, planes, planesListos, errPlanes, onClose, onDone }: {
  comercio: ComercioSuscripcion; planes: PlanAdmin[]; planesListos: boolean; errPlanes: string;
  onClose: () => void; onDone: () => void;
}) {
  const opciones = opcionesDePlanes(planes, comercio.plan ?? "gratis");
  const [plan, setPlan] = useState(comercio.plan ?? "gratis");
  const [cortesia, setCortesia] = useState(!!comercio.plan_cortesia);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  // La cortesía sólo tiene sentido en un plan pago: en uno gratis no hay nada
  // que regalar ni estrella que dar.
  const esGratis = (opciones.find((o) => o.slug === plan)?.precio_mes ?? 0) <= 0;
  const hayCortesia = cortesia && !esGratis;

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    if (!planesListos) return;
    if (comercio.plan_cortesia && !hayCortesia && !window.confirm(
      `${comercio.nombre} deja de ser de cortesía: va a tener que pagar y su plan va a vencer. ¿Seguimos?`)) return;
    if (hayCortesia && !comercio.plan_cortesia && !window.confirm(
      `${comercio.nombre} va a tener el plan sin pagar y sin vencimiento, y no va a aparecer en cobros ni en vencimientos. ¿Seguimos?`)) return;
    setSaving(true);
    try {
      await asignarPlanComercio(comercio.id, plan, hayCortesia);
      onDone();
    } catch (e2) {
      setErr(e2 instanceof Error && e2.message ? e2.message : "No se pudo guardar el plan.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Portal>
      <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
        <div className="glass" style={{ width: "100%", maxWidth: 420, borderRadius: 16, padding: 24 }}>
          <h3 style={{ marginBottom: 4 }}>Plan del comercio</h3>
          <p style={{ color: "var(--txt-3)", fontSize: 13, marginBottom: 18 }}>{comercio.nombre}</p>
          <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, color: "var(--txt-2)" }}>
              Plan
              <select className="adm-input" value={plan} onChange={(e) => setPlan(e.target.value)}>
                {opciones.map((o) => <option key={o.slug} value={o.slug}>{o.nombre}</option>)}
              </select>
            </label>
            <label style={{ display: "flex", alignItems: "flex-start", gap: 10, fontSize: 14, opacity: esGratis ? 0.55 : 1 }}>
              <input type="checkbox" checked={hayCortesia} disabled={esGratis}
                     style={{ width: 20, height: 20, marginTop: 1 }}
                     onChange={(e) => setCortesia(e.target.checked)} />
              <span>
                De cortesía (no paga, no vence)
                <span style={{ display: "block", fontSize: 12, color: "var(--txt-3)", marginTop: 2 }}>
                  {esGratis
                    ? "Elegí un plan pago para poder darlo de cortesía."
                    : "Tiene la estrella «Verificado por URUKU» y no aparece en cobros ni vencimientos."}
                </span>
              </span>
            </label>
            {!planesListos && !errPlanes && <span style={{ color: "var(--txt-3)", fontSize: 13 }}>Cargando los planes…</span>}
            {errPlanes && <span style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={14} /> {errPlanes}</span>}
            {err && <span style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={14} /> {err}</span>}
            <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
              <button type="button" className="btn btn-ghost" style={{ flex: 1 }} onClick={onClose}>Cancelar</button>
              <button type="submit" className="btn btn-primary" style={{ flex: 2 }} disabled={saving || !planesListos}>
                {saving ? "Guardando…" : "Guardar plan"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Portal>
  );
}

function ModalPago({ comercio, onClose, onDone }: { comercio: ComercioSuscripcion; onClose: () => void; onDone: () => void }) {
  const [monto, setMonto] = useState("100");
  const [moneda, setMoneda] = useState("BOB");
  const [metodo, setMetodo] = useState("qr-bolivia");
  const [meses, setMeses] = useState("1");
  const [referencia, setReferencia] = useState("");
  const [notas, setNotas] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  // Resultado del pago: el backend avisa si el WhatsApp del comercio no sirve y
  // si le quedó cuenta para entrar al panel. Se muestra ANTES de cerrar, porque
  // es el único momento en que el admin está cara a cara con el dueño.
  const [resultado, setResultado] = useState<{ advertencias: string[]; login: boolean } | null>(null);

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    if (!monto || isNaN(Number(monto))) { setErr("Ingresá un monto válido"); return; }
    setSaving(true);
    try {
      const r = await registrarPago(comercio.id, {
        monto: Number(monto), moneda, metodo, meses: Number(meses),
        referencia: referencia || undefined, notas: notas || undefined,
      });
      setResultado({ advertencias: r?.advertencias ?? [], login: !!r?.login });
    } catch {
      setErr("No se pudo registrar el pago. Verificá el backend.");
    } finally {
      setSaving(false);
    }
  }

  if (resultado) {
    return (
      <Portal>
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
          <div className="glass" style={{ width: "100%", maxWidth: 420, borderRadius: 16, padding: 24 }}>
            <h3 style={{ marginBottom: 4 }}>Pago registrado</h3>
            <p style={{ color: "var(--txt-3)", fontSize: 13, marginBottom: 18 }}>{comercio.nombre}</p>

            <div style={{ fontSize: 14, marginBottom: 12 }}>
              {resultado.login
                ? <span style={{ color: "var(--neon)" }}>El comercio ya puede entrar al panel</span>
                : <span style={{ color: "var(--amber)" }}><Ic n="aviso" s={14} /> No se pudo crear la cuenta del panel</span>}
            </div>

            {resultado.advertencias.length > 0 && (
              <div style={{ border: "1px solid var(--amber)", borderRadius: 10, padding: 12, marginBottom: 14 }}>
                <div style={{ color: "var(--amber)", fontWeight: 600, fontSize: 13, marginBottom: 6 }}>
                  Revisá esto con el dueño ahora
                </div>
                {resultado.advertencias.map((a, i) => (
                  <div key={i} style={{ fontSize: 13, color: "var(--txt-2)" }}>· {a}</div>
                ))}
                <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 8 }}>
                  Sin un WhatsApp válido no le llegan las reservas de la tienda.
                </div>
              </div>
            )}

            <button className="btn btn-primary" style={{ width: "100%" }} onClick={onDone}>Listo</button>
          </div>
        </div>
      </Portal>
    );
  }

  return (
    <Portal>
      <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 999, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
        <div className="glass" style={{ width: "100%", maxWidth: 420, borderRadius: 16, padding: 24 }}>
          <h3 style={{ marginBottom: 4 }}>Registrar pago</h3>
          <p style={{ color: "var(--txt-3)", fontSize: 13, marginBottom: 18 }}>{comercio.nombre}</p>
          <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "flex", gap: 10 }}>
              <input className="adm-input" style={{ flex: 2 }} type="number" value={monto} onChange={(e) => setMonto(e.target.value)} placeholder="Monto" />
              <select className="adm-input" style={{ flex: 1 }} value={moneda} onChange={(e) => setMoneda(e.target.value)}>
                <option value="BOB">BOB</option>
                <option value="ARS">ARS</option>
                <option value="USD">USD</option>
              </select>
            </div>
            <select className="adm-input" value={metodo} onChange={(e) => setMetodo(e.target.value)}>
              <option value="qr-bolivia">QR Bolivia</option>
              <option value="efectivo">Efectivo</option>
              <option value="transferencia">Transferencia</option>
            </select>
            <select className="adm-input" value={meses} onChange={(e) => setMeses(e.target.value)}>
              <option value="1">1 mes</option>
              <option value="3">3 meses</option>
              <option value="6">6 meses</option>
              <option value="12">12 meses</option>
            </select>
            <input className="adm-input" value={referencia} onChange={(e) => setReferencia(e.target.value)} placeholder="N° comprobante / referencia (opcional)" />
            <input className="adm-input" value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Notas (opcional)" />
            {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
            <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
              <button type="button" className="btn btn-ghost" style={{ flex: 1 }} onClick={onClose}>Cancelar</button>
              <button type="submit" className="btn btn-primary" style={{ flex: 2 }} disabled={saving}>
                {saving ? "Guardando…" : "Confirmar pago"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Portal>
  );
}


/** Cuánto pesan las fotos, y el botón para achicar las que se fueron de rango.
 *
 * La medición va primero y el botón queda apagado hasta verla. Todo lo que
 * sube por el backend ya pasa por el procesador de imágenes, así que lo
 * probable es que las fotos estén bien y el peso esté en los videos —que se
 * guardan crudos, tal como salen del celular—. Apretar "reducir" sin haber
 * mirado sería trabajar sobre una suposición.
 */
function PanelPesoFotos() {
  const [peso, setPeso] = useState<PesoFotos | null>(null);
  const [midiendo, setMidiendo] = useState(false);
  const [maxKb, setMaxKb] = useState(250);
  const [corriendo, setCorriendo] = useState(false);
  const [res, setRes] = useState<ResultadoOptimizar | null>(null);
  const [err, setErr] = useState("");

  const mb = (b: number) => `${(b / 1024 / 1024).toFixed(1)} MB`;

  async function medir() {
    setMidiendo(true); setErr(""); setRes(null);
    try { setPeso(await getPesoFotos()); }
    catch { setErr("No se pudo medir. ¿El backend está arriba?"); }
    finally { setMidiendo(false); }
  }

  async function optimizar() {
    // Pisa el archivo original y no hay vuelta atrás: la confirmación dice
    // exactamente eso, no un "¿estás seguro?" que nadie lee.
    if (!confirm(`Se van a recomprimir las imágenes de más de ${maxKb} KB.

` +
                 `El archivo original se pierde: esto NO se puede deshacer.

¿Seguimos?`)) return;
    setCorriendo(true); setErr("");
    try {
      const r = await optimizarFotos(maxKb, 50);
      setRes(r);
      await medir();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "No se pudo optimizar");
    } finally { setCorriendo(false); }
  }

  return (
    <div className="panel-card glass">
      <div className="ph">
        <h3>Peso de las fotos</h3>
        <button className="btn btn-ghost btn-sm" onClick={medir} disabled={midiendo}>
          {midiendo ? "Midiendo…" : peso ? "Volver a medir" : "Medir"}
        </button>
      </div>

      {!peso && !midiendo && (
        <div style={{ padding: 20, color: "var(--txt-3)", fontSize: 13 }}>
          Recorre el disco de fotos y dice cuánto ocupa cada cosa. Puede tardar unos segundos.
        </div>
      )}

      {peso && peso.existe === false && (
        <div style={{ padding: 20, color: "var(--amber)", fontSize: 13 }}>
          No existe el directorio {peso.dir}. Si el backend está en otro contenedor, revisá el volumen.
        </div>
      )}

      {peso?.existe && (
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
            <div>
              <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Imágenes</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{mb(peso.imagenes?.bytes ?? 0)}</div>
              <div style={{ fontSize: 11, color: "var(--txt-3)" }}>
                {peso.imagenes?.n ?? 0} archivos · {peso.imagenes?.promedio_kb ?? 0} KB promedio
              </div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Videos (sin procesar)</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: (peso.videos?.bytes ?? 0) > (peso.imagenes?.bytes ?? 0) ? "var(--amber)" : undefined }}>
                {mb(peso.videos?.bytes ?? 0)}
              </div>
              <div style={{ fontSize: 11, color: "var(--txt-3)" }}>
                {peso.videos?.n ?? 0} archivos · {peso.videos?.promedio_kb ?? 0} KB promedio
              </div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Total en disco</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{mb(peso.bytes_total ?? 0)}</div>
            </div>
          </div>

          {/* Si el peso está en los videos, el botón de abajo no los toca y
              decirlo evita apretarlo esperando que resuelva algo. */}
          {(peso.videos?.bytes ?? 0) > (peso.imagenes?.bytes ?? 0) && (
            <div style={{ fontSize: 12.5, color: "var(--amber)", border: "1px solid var(--amber)",
                          borderRadius: 8, padding: "8px 12px" }}>
              El grueso del peso está en los videos, que se guardan crudos. Optimizar las
              imágenes no los toca: si hay que bajar el disco, es ahí donde hay que mirar.
            </div>
          )}

          {peso.imagenes && peso.imagenes.top.length > 0 && (
            <div>
              <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 6 }}>Las más pesadas</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                {peso.imagenes.top.slice(0, 8).map((f) => (
                  <div key={f.path} style={{ display: "flex", justifyContent: "space-between", gap: 10, fontSize: 12 }}>
                    <span style={{ color: "var(--txt-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.path}</span>
                    <b style={{ flexShrink: 0, color: f.kb > 400 ? "var(--amber)" : "var(--txt-2)" }}>{f.kb} KB</b>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div style={{ borderTop: "1px solid var(--border)", paddingTop: 14, display: "flex",
                        gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <label style={{ fontSize: 12, color: "var(--txt-3)" }}>
              Achicar las que pasen de
              <input className="adm-input" type="number" min={50} step={50} value={maxKb}
                     onChange={(e) => setMaxKb(Number(e.target.value) || 250)}
                     style={{ width: 90, marginLeft: 8 }} /> KB
            </label>
            <button className="btn btn-primary btn-sm" onClick={optimizar} disabled={corriendo}>
              {corriendo ? "Achicando…" : "Reducir peso"}
            </button>
            <span style={{ fontSize: 11.5, color: "var(--txt-3)" }}>
              De a 50 por vez · pisa el original, no se puede deshacer
            </span>
          </div>

          {res && (
            <div style={{ fontSize: 13 }}>
              Se achicaron <b>{res.optimizados}</b> de {res.revisados} · ahorro <b>{mb(res.ahorro_bytes)}</b>
              {res.restantes > 0 && (
                <span style={{ color: "var(--amber)" }}> · quedan {res.restantes}, volvé a apretar</span>
              )}
            </div>
          )}
          {err && <div style={{ color: "var(--pink)", fontSize: 13 }}>{err}</div>}
        </div>
      )}
    </div>
  );
}


/** Lee las fotos de las ofertas: qué son, con qué palabras se buscan, y el
 *  precio si está escrito en la imagen.
 *
 *  Existe por una razón concreta y no por completitud: el índice de búsqueda de
 *  las publicaciones sale del título y la descripción, y cuando la oferta trae
 *  foto el título queda en NULL a propósito —la oferta ES la foto—. Un
 *  comerciante apurado manda la foto sola, y esa oferta no aparecía en ninguna
 *  búsqueda: existía, se veía en la ficha, y era invisible para quien la
 *  buscaba.
 *
 *  Va de a pocas y en bucle, igual que el análisis de comercios: cada llamada
 *  tarda segundos, el avance se ve, y se puede cortar sin perder lo hecho. */
function AnalisisOfertas() {
  const [pendientes, setPendientes] = useState<number | null>(null);
  const [corriendo, setCorriendo] = useState(false);
  const [hechas, setHechas] = useState(0);
  const [ultimas, setUltimas] = useState<ResultadoOferta[]>([]);
  const [err, setErr] = useState("");
  const cancelar = useRef(false);

  useEffect(() => { ofertasPendientesAnalisis().then(setPendientes).catch(() => setPendientes(null)); }, []);

  async function correr() {
    setErr(""); setHechas(0); setUltimas([]); setCorriendo(true);
    cancelar.current = false;
    try {
      for (;;) {
        if (cancelar.current) break;
        const t = await analizarTandaOfertas(3);
        if (t.sin_mas || t.procesados === 0) { setPendientes(0); break; }
        setHechas((n) => n + t.procesados);
        setPendientes(t.restantes);
        setUltimas((prev) => [...t.resultados, ...prev].slice(0, 10));
        const fallo = t.resultados.find((r) => r.error);
        if (fallo) { setErr(`Se detuvo: ${fallo.error}`); break; }
        if (t.restantes === 0) break;
        // Respiro: el límite de Gemini es por ventana de tiempo.
        await new Promise((r) => setTimeout(r, 1200));
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "No se pudo analizar");
    } finally { setCorriendo(false); }
  }

  if (pendientes === 0 && !hechas) return null;

  return (
    <div className="panel-card glass" style={{ padding: 16, marginBottom: 14 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 260px" }}>
          <b style={{ fontSize: 14.5 }}>Leer las fotos de las ofertas</b>
          <div style={{ fontSize: 12.5, color: "var(--txt-3)", marginTop: 3 }}>
            Una oferta que llega como foto sin texto <b>no se puede buscar</b>: el buscador
            mira el título y la descripción, y con foto el título queda vacío. Esto le pone
            las palabras con las que un cliente la buscaría, y el precio si está escrito
            en la imagen.
          </div>
          <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 4 }}>
            No pisa lo que escribió el comerciante: si él puso título o precio, gana el suyo.
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{pendientes ?? "—"}</div>
          <div style={{ fontSize: 11.5, color: "var(--txt-3)" }}>sin analizar</div>
        </div>
        {corriendo ? (
          <button className="btn btn-ghost btn-sm" onClick={() => { cancelar.current = true; }}>
            Cortar ({hechas})
          </button>
        ) : (
          <button className="btn btn-primary btn-sm" onClick={correr} disabled={!pendientes}>
            Analizar
          </button>
        )}
      </div>

      {err && <div style={{ color: "var(--pink)", fontSize: 13, marginTop: 10 }}>{err}</div>}

      {ultimas.length > 0 && (
        <div style={{ marginTop: 12, fontSize: 12.5 }}>
          {ultimas.map((r) => (
            <div key={r.id} style={{ padding: "4px 0", borderTop: "1px solid var(--border)" }}>
              {r.aplicado
                ? <span style={{ color: "var(--neon)" }}><Ic n="si" s={14} /></span>
                : <span style={{ color: "var(--amber)" }} title={r.es_oferta === false ? "La foto no muestra un producto" : "El modelo no reconoció nada"}>—</span>}
              {" "}<b>{r.titulo || "(sin título)"}</b>
              {r.precio != null && <span style={{ color: "var(--neon)" }}> · {r.precio}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
