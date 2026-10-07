"use client";

// El tablero (Inicio) del panel de administración — docs/admin-rediseno.md §3.
//
// NO PIDE DATOS: los recibe. Quien lo monta hace el único pedido
// (`GET /admin/resumen`) y le pasa el resultado; acá sólo se dibuja. Así el
// Inicio, los números del menú y el botón «Actualizar» salen de la misma
// respuesta.
//
// QUÉ SE VE, DE ARRIBA ABAJO
// ==========================
// 1. Para hacer hoy: lo que alguien tiene que resolver, con su número y un
//    botón que lleva a la sección. Lo que está en cero no ocupa lugar.
// 2. Tarjetas con los números grandes.
// 3. Gráficos (SVG propios, ver graficos.tsx).
//
// UN `null` NO ES UN CERO. El backend manda `null` cuando una parte no se pudo
// calcular (p.ej. Reservalo no contesta). Mostrar «0 pagos» cuando en realidad
// no se supo sería decirle al dueño «todo bien» sin saberlo: se escribe «no se
// pudo calcular».

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import "@/app/styles/admin-dashboard.css";
import { Ic } from "@/components/ic";
import type { NombreIcono } from "@/components/ic";
import { puedo, type ResumenAdmin } from "@/lib/api";
import { defSeccion, type SeccionAdmin } from "@/components/admin/secciones";
import {
  BarrasHorizontales, BarrasVerticales, Lineas, LeyendaLineas, Progreso,
  fechaConDia, fechaCorta, fmt, pct, pctNum,
} from "@/components/admin/graficos";

type Pendientes = ResumenAdmin["pendientes"];
type ClavePendiente = keyof Pendientes;

type DefPendiente = {
  clave: ClavePendiente;
  seccion: SeccionAdmin;
  icono: NombreIcono;
  /** «12 publicaciones esperan moderación»: el número va aparte, en grande. */
  uno: string;
  otros: string;
  /** Lo que dice el botón. */
  boton: string;
  /** Nombre corto, para la línea de «al día». */
  nombre: string;
  urgente?: boolean;
  /** Sale de TODAS las ciudades aunque arriba haya una elegida: es lo que
   *  lista su sección (que todavía no filtra por ciudad). Se dice en la fila;
   *  si no, con «Santa Cruz» arriba el número parecería de Santa Cruz. */
  global?: boolean;
};

// El orden ES la urgencia: lo que vence o es plata va primero; lo voluminoso y
// que puede esperar (verificar mil comercios), al final.
const PENDIENTES: DefPendiente[] = [
  { clave: "vencimientos", global: true, seccion: "vencimientos", icono: "aviso", urgente: true,
    uno: "alerta de vencimiento", otros: "alertas de vencimiento", boton: "Ver alertas", nombre: "Vencimientos" },
  { clave: "pagos", global: true, seccion: "pagos", icono: "pagos", urgente: true,
    uno: "pago espera confirmación", otros: "pagos esperan confirmación", boton: "Confirmar pagos", nombre: "Pagos" },
  { clave: "suscripciones", global: true, seccion: "suscripciones", icono: "calendario",
    uno: "suscripción por vencer, vencida o suspendida", otros: "suscripciones por vencer, vencidas o suspendidas",
    boton: "Ver suscripciones", nombre: "Suscripciones" },
  { clave: "publicaciones", global: true, seccion: "publicaciones", icono: "ofertas",
    uno: "publicación espera moderación", otros: "publicaciones esperan moderación", boton: "Moderar", nombre: "Publicaciones" },
  { clave: "reclamos", global: true, seccion: "reclamos", icono: "dax",
    uno: "reclamo o consulta sin responder", otros: "reclamos o consultas sin responder", boton: "Ver reclamos", nombre: "Reclamos" },
  { clave: "cambio_numero", global: true, seccion: "cambio-numero", icono: "telefono",
    uno: "cambio de número por resolver", otros: "cambios de número por resolver", boton: "Resolver", nombre: "Cambios de número" },
  { clave: "recepcion_sin_comercio", global: true, seccion: "whatsapp", icono: "whatsapp",
    uno: "mensaje de Recepción sin comercio (7 días)", otros: "mensajes de Recepción sin comercio (7 días)",
    boton: "Ver mensajes", nombre: "Recepción" },
  { clave: "comercios_sin_verificar", seccion: "negocios", icono: "verificado",
    uno: "comercio sin verificar", otros: "comercios sin verificar", boton: "Verificar", nombre: "Verificación" },
];

type Props = {
  resumen: ResumenAdmin | null;
  cargando: boolean;
  error: string | null;
  onIr: (s: SeccionAdmin) => void;
  onRecargar: () => void;
  ciudadNombre: string | null;
};

export function Dashboard({ resumen, cargando, error, onIr, onRecargar, ciudadNombre }: Props): JSX.Element {
  const hora = useHoraDeActualizacion(resumen);
  const titulo = ciudadNombre ?? "Todas las ciudades";

  return (
    <div className="adb" aria-busy={cargando}>
      <header className="adb-cab">
        <div>
          <span className="eyebrow">Inicio</span>
          <h2 className="adb-titulo">{titulo}</h2>
          <p className="adb-sub" role="status">
            {cargando && !resumen ? "Cargando los números…"
              : hora ? <>Actualizado a las {hora}{cargando ? " · actualizando…" : ""}</>
              : "Todavía sin datos"}
          </p>
        </div>
        <button type="button" className="adb-btn adb-btn-sec" onClick={onRecargar} disabled={cargando}>
          <Ic n="actualizar" s={18} className={cargando ? "adb-gira" : undefined} />
          {cargando ? "Actualizando…" : "Actualizar"}
        </button>
      </header>

      {error && (
        <div className="adb-aviso adb-aviso-pink" role="alert">
          <Ic n="aviso" s={20} />
          <p><b>{error}.</b>{resumen ? " Estás viendo los últimos números que llegaron." : ""}</p>
          <button type="button" className="adb-btn adb-btn-sec" onClick={onRecargar} disabled={cargando}>Reintentar</button>
        </div>
      )}

      {!resumen && cargando && <Esqueleto />}

      {!resumen && !cargando && !error && (
        <div className="glass panel-card adb-vacio">
          <Ic n="dato" s={28} />
          <h3>Todavía no hay números para mostrar</h3>
          <p>Probá actualizar en un momento.</p>
          <button type="button" className="adb-btn adb-btn-pri" onClick={onRecargar}>Actualizar</button>
        </div>
      )}

      {resumen && (
        <>
          <ParaHacerHoy pendientes={resumen.pendientes} onIr={onIr} ciudadNombre={ciudadNombre} />
          <Tarjetas resumen={resumen} ciudadNombre={ciudadNombre} onIr={onIr} />
          <Graficos resumen={resumen} />
        </>
      )}
    </div>
  );
}

/* ───────────────────────────── ayudas de estado ───────────────────────────── */

/** La hora en que llegó el último resumen (el componente no recibe la fecha:
 *  se anota cuando cambia el objeto). */
function useHoraDeActualizacion(resumen: ResumenAdmin | null): string | null {
  const [hora, setHora] = useState<string | null>(null);
  useEffect(() => {
    if (resumen) setHora(new Date().toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" }));
  }, [resumen]);
  return hora;
}


/* ───────────────────────────── para hacer hoy ───────────────────────────── */

function ParaHacerHoy({ pendientes, onIr, ciudadNombre }: { pendientes: Pendientes; onIr: (s: SeccionAdmin) => void; ciudadNombre: string | null }) {
  // Sólo lo que este usuario puede abrir: una fila de Recepción para quien no
  // tiene el permiso llevaba a «No tenés permiso».
  const visibles = PENDIENTES.filter((d) => { const p = defSeccion(d.seccion).permiso; return !p || puedo(p); });
  const conTrabajo = visibles.filter((d) => (pendientes[d.clave] ?? 0) > 0);
  const sinCalcular = visibles.filter((d) => pendientes[d.clave] === null);
  const alDia = visibles.filter((d) => pendientes[d.clave] === 0);
  const filas = [...conTrabajo, ...sinCalcular];
  const total = conTrabajo.reduce((s, d) => s + (pendientes[d.clave] ?? 0), 0);

  return (
    <section className="glass panel-card adb-card adb-hoy" aria-labelledby="adb-hoy-t">
      <div className="adb-card-cab">
        <h3 id="adb-hoy-t">Para hacer hoy</h3>
        {conTrabajo.length > 0 && <span className="adb-chip adb-chip-amber">{fmt(total)} en total</span>}
      </div>

      {filas.length === 0 ? (
        <div className="adb-aldia">
          <Ic n="listo" s={32} />
          <div>
            <b>Todo al día</b>
            <p>No hay nada esperando que lo resuelvas.</p>
          </div>
        </div>
      ) : (
        <ul className="adb-lista">
          {filas.map((d) => {
            const n = pendientes[d.clave];
            if (n === null) {
              return (
                <li key={d.clave} className="adb-fila adb-fila-nulo">
                  <span className="adb-fila-ic" aria-hidden><Ic n={d.icono} s={22} /></span>
                  <div className="adb-fila-txt">
                    <b className="adb-nulo"><Ic n="aviso" s={16} /> No se pudo calcular</b>
                    <span>{d.nombre}: revisalo a mano.</span>
                  </div>
                  <button type="button" className="adb-btn adb-btn-sec" onClick={() => onIr(d.seccion)}>
                    Revisar <Ic n="seguir" s={16} />
                  </button>
                </li>
              );
            }
            const frase = n === 1 ? d.uno : d.otros;
            return (
              <li key={d.clave} className={d.urgente ? "adb-fila adb-fila-urgente" : "adb-fila"}>
                <span className="adb-fila-ic" aria-hidden><Ic n={d.icono} s={22} /></span>
                <div className="adb-fila-txt">
                  <span className="adb-fila-linea">
                    <b className="adb-fila-num">{fmt(n)}</b>
                    {d.urgente && <span className="adb-chip adb-chip-pink">Urgente</span>}
                  </span>
                  <span>{frase}{d.global && ciudadNombre ? " · de todas las ciudades" : ""}</span>
                </div>
                <button type="button" className="adb-btn adb-btn-pri" onClick={() => onIr(d.seccion)}
                        aria-label={`${d.boton}: ${fmt(n)} ${frase}`}>
                  {d.boton} <Ic n="seguir" s={16} />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {filas.length > 0 && alDia.length > 0 && (
        <p className="adb-aldia-linea">
          <Ic n="listo" s={16} tono="marca" /> <span><b>Al día:</b> {alDia.map((d) => d.nombre).join(", ")}.</span>
        </p>
      )}
    </section>
  );
}

/* ───────────────────────────── tarjetas ───────────────────────────── */

function Tarjetas({ resumen, ciudadNombre, onIr }: { resumen: ResumenAdmin; ciudadNombre: string | null; onIr: (s: SeccionAdmin) => void }) {
  const c = resumen.comercios;
  const conHorario = Math.max(0, c.total - c.sin_horario);
  const conWhatsapp = Math.max(0, c.total - c.sin_whatsapp);
  const donde = ciudadNombre ? `en ${ciudadNombre}` : "en todas las ciudades";
  const a = resumen.actividad;

  return (
    <section aria-label="Números principales" className="adb-tarjetas">
      <Tarjeta icono="comercios" etiqueta="Comercios" valor={fmt(c.total)} detalle={`activos ${donde}`} />
      <Tarjeta icono="verificado" etiqueta="Verificados" valor={fmt(c.verificados)} insignia={pct(c.verificados, c.total)}
               detalle={`de ${fmt(c.total)} comercios`} progreso={pctNum(c.verificados, c.total)}
               accion={c.sin_verificar > 0 ? { texto: `Verificar (${fmt(c.sin_verificar)})`, ir: () => onIr("negocios") } : undefined} />
      <Tarjeta icono="reloj" etiqueta="Con horario" valor={fmt(conHorario)} insignia={pct(conHorario, c.total)}
               detalle={c.horario_estimado > 0 ? `${fmt(c.horario_estimado)} son estimados por calle` : `de ${fmt(c.total)} comercios`}
               progreso={pctNum(conHorario, c.total)}
               accion={c.sin_horario > 0 ? { texto: `Cargar horarios (${fmt(c.sin_horario)})`, ir: () => onIr("calles") } : undefined} />
      <Tarjeta icono="whatsapp" etiqueta="Con WhatsApp" valor={fmt(conWhatsapp)} insignia={pct(conWhatsapp, c.total)}
               detalle={`de ${fmt(c.total)} comercios`} progreso={pctNum(conWhatsapp, c.total)} />
      <Tarjeta icono="explorar" etiqueta="Visitas · 7 días" valor={a.visitas_7d === null ? null : fmt(a.visitas_7d)} detalle="en los últimos 7 días" />
      <Tarjeta icono="enviar" etiqueta="Contactos · 7 días" valor={a.contactos_7d === null ? null : fmt(a.contactos_7d)} detalle="en los últimos 7 días" />
    </section>
  );
}

function Tarjeta(props: {
  icono: NombreIcono; etiqueta: string;
  /** null = no se pudo calcular. */
  valor: string | null;
  detalle: string;
  insignia?: string;
  progreso?: number;
  accion?: { texto: string; ir: () => void };
}) {
  const { icono, etiqueta, valor, detalle, insignia, progreso, accion } = props;
  return (
    <article className="glass panel-card adb-tarjeta">
      <div className="adb-tarjeta-cab"><Ic n={icono} s={20} /><span>{etiqueta}</span></div>
      {valor === null ? (
        <p className="adb-nulo adb-nulo-grande"><Ic n="aviso" s={18} /> No se pudo calcular</p>
      ) : (
        <div className="adb-tarjeta-valor">
          <b>{valor}</b>
          {insignia && <span className="adb-chip adb-chip-neon">{insignia}</span>}
        </div>
      )}
      {valor !== null && <small className="adb-tarjeta-detalle">{detalle}</small>}
      {progreso !== undefined && valor !== null && (
        <div className="adb-pista adb-pista-fina" aria-hidden><div className="adb-relleno" style={{ width: `${progreso}%`, background: "var(--neon)" }} /></div>
      )}
      {accion && (
        <button type="button" className="adb-btn adb-btn-sec adb-btn-ancho" onClick={accion.ir}>
          {accion.texto} <Ic n="seguir" s={16} />
        </button>
      )}
    </article>
  );
}

/* ───────────────────────────── gráficos ───────────────────────────── */

function Graficos({ resumen }: { resumen: ResumenAdmin }) {
  const serie = resumen.actividad.serie_30d;
  const c = resumen.comercios;

  return (
    <div className="adb-graficos">
      <Cuadro titulo="Altas por día" sub="Comercios nuevos, últimos 30 días">
        {serie === null ? <NoSePudo />
          : serie.length === 0 ? <SinDatos texto="Todavía no hay días para mostrar." />
          : <AltasPorDia serie={serie} />}
      </Cuadro>

      <Cuadro titulo="Visitas y contactos por día" sub="Últimos 30 días">
        {serie === null ? <NoSePudo />
          : serie.length === 0 ? <SinDatos texto="Todavía no hay días para mostrar." />
          : <VisitasYContactos serie={serie} />}
      </Cuadro>

      <Cuadro titulo="Fichas completas" sub={`Qué tan completos están los ${fmt(c.total)} comercios`}>
        {c.total === 0 ? <SinDatos texto="Todavía no hay comercios." /> : (
          <div className="adb-progs">
            <Progreso etiqueta="Horario" icono={<Ic n="reloj" s={18} />} valor={Math.max(0, c.total - c.sin_horario)} total={c.total} />
            <Progreso etiqueta="WhatsApp" icono={<Ic n="whatsapp" s={18} />} valor={Math.max(0, c.total - c.sin_whatsapp)} total={c.total} />
            <Progreso etiqueta="Foto" icono={<Ic n="foto" s={18} />} valor={Math.max(0, c.total - c.sin_foto)} total={c.total} />
            <Progreso etiqueta="Rubro" icono={<Ic n="cartel" s={18} />} valor={Math.max(0, c.total - c.sin_rubro)} total={c.total} />
          </div>
        )}
      </Cuadro>

      <Cuadro titulo="Comercios por ciudad" sub="Siempre todas las ciudades, no depende del filtro de arriba">
        {resumen.por_ciudad.length === 0 ? <SinDatos texto="Todavía no hay ciudades con comercios." /> : <PorCiudad resumen={resumen} />}
      </Cuadro>
    </div>
  );
}

function Cuadro({ titulo, sub, children }: { titulo: string; sub: string; children: ReactNode }) {
  return (
    <section className="glass panel-card adb-card">
      <div className="adb-card-cab adb-card-cab-col">
        <h3>{titulo}</h3>
        <small>{sub}</small>
      </div>
      {children}
    </section>
  );
}

function NoSePudo() {
  return <p className="adb-nulo adb-nulo-grande"><Ic n="aviso" s={18} /> No se pudo calcular. Probá actualizar.</p>;
}

function SinDatos({ texto }: { texto: string }) {
  return <p className="adb-sindatos"><Ic n="dato" s={18} /> {texto}</p>;
}

type Dia = { dia: string; altas: number; visitas: number; contactos: number };

function AltasPorDia({ serie }: { serie: Dia[] }) {
  const total = serie.reduce((s, d) => s + d.altas, 0);
  const pico = serie.reduce((m, d) => (d.altas > m.altas ? d : m), serie[0]);
  const resumen = total === 0
    ? `Altas por día, últimos ${serie.length} días: no hubo altas.`
    : `Altas por día, últimos ${serie.length} días: ${fmt(total)} en total. El día con más fue el ${fechaCorta(pico.dia)}, con ${fmt(pico.altas)}.`;
  return (
    <>
      <p className="adb-total"><b>{fmt(total)}</b> {total === 1 ? "alta" : "altas"} en {serie.length} días</p>
      {total === 0 && <SinDatos texto="No hubo altas en este período." />}
      <BarrasVerticales
        datos={serie.map((d) => ({ etiqueta: fechaCorta(d.dia), detalle: fechaConDia(d.dia), valor: d.altas }))}
        color="var(--neon)" unidad={{ uno: "alta", otros: "altas" }} resumen={resumen} />
    </>
  );
}

function VisitasYContactos({ serie }: { serie: Dia[] }) {
  const visitas = serie.map((d) => d.visitas);
  const contactos = serie.map((d) => d.contactos);
  const tv = visitas.reduce((s, v) => s + v, 0);
  const tc = contactos.reduce((s, v) => s + v, 0);
  const resumen = `Visitas y contactos por día, últimos ${serie.length} días: ${fmt(tv)} visitas y ${fmt(tc)} contactos en total.`;
  const series = [
    { nombre: "Visitas", color: "var(--blue-soft)", valores: visitas },
    { nombre: "Contactos", color: "var(--amber)", valores: contactos, punteada: true },
  ];
  return (
    <>
      <LeyendaLineas items={series.map((s, i) => ({
        nombre: s.nombre, color: s.color, punteada: s.punteada, detalle: `${fmt(i === 0 ? tv : tc)} en ${serie.length} días`,
      }))} />
      {tv === 0 && tc === 0 && <SinDatos texto="Sin visitas ni contactos en este período." />}
      <Lineas etiquetas={serie.map((d) => fechaCorta(d.dia))} detalles={serie.map((d) => fechaConDia(d.dia))} series={series} resumen={resumen} />
    </>
  );
}

function PorCiudad({ resumen }: { resumen: ResumenAdmin }) {
  const ciudades = [...resumen.por_ciudad].sort((a, b) => b.total - a.total);
  const texto = ciudades.map((c) => `${c.nombre}: ${fmt(c.total)} comercios, ${fmt(c.sin_verificar)} sin verificar, ${fmt(c.sin_horario)} sin horario`).join(". ");
  return (
    <BarrasHorizontales
      color="var(--neon)"
      resumen={`Comercios por ciudad. ${texto}.`}
      filas={ciudades.map((c) => ({
        id: c.slug,
        etiqueta: c.nombre,
        valor: c.total,
        destacada: resumen.ciudad === c.slug,
        nota: resumen.ciudad === c.slug ? "la que estás mirando" : undefined,
        extras: [
          { etiqueta: "Sin verificar", valor: c.sin_verificar, color: "var(--amber)" },
          { etiqueta: "Sin horario", valor: c.sin_horario, color: "var(--pink)" },
        ],
      }))} />
  );
}

/* ───────────────────────────── esqueleto ───────────────────────────── */

function Esqueleto() {
  return (
    <div className="adb-esq" aria-hidden>
      <div className="glass panel-card adb-card">
        <div className="adb-esq-bloque adb-esq-t" />
        <div className="adb-esq-bloque adb-esq-fila" />
        <div className="adb-esq-bloque adb-esq-fila" />
      </div>
      <div className="adb-tarjetas">
        {[0, 1, 2, 3, 4, 5].map((k) => (
          <div key={k} className="glass panel-card adb-tarjeta">
            <div className="adb-esq-bloque adb-esq-t" />
            <div className="adb-esq-bloque adb-esq-num" />
          </div>
        ))}
      </div>
      <div className="adb-graficos">
        {[0, 1, 2, 3].map((k) => (
          <div key={k} className="glass panel-card adb-card">
            <div className="adb-esq-bloque adb-esq-t" />
            <div className="adb-esq-bloque adb-esq-graf" />
          </div>
        ))}
      </div>
    </div>
  );
}
