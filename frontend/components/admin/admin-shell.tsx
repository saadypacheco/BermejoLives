"use client";

// El marco del panel de administración (docs/admin-rediseno.md §1):
//   · barra de arriba, fija: URUKU (Inicio del panel) · ciudad · Ver sitio ·
//     usuario y Salir;
//   · menú lateral agrupado, con un número en lo que tiene algo para resolver;
//   · en el celular el menú es un cajón que se abre con el botón de la barra y
//     se cierra al elegir.
// El contenido (lo que cada sección dibuja) entra por `children` y usa todo el
// ancho que sobra.
//
// Qué secciones hay, cómo se agrupan, con qué ícono y permiso: `secciones.ts`.
// Acá no se lista ninguna.

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import "@/app/styles/admin-shell.css";
import { Ic } from "@/components/ic";
import { AvisoCiudad, SelectorCiudad } from "@/components/admin-ciudad";
import { getToken, puedo, type ResumenAdmin } from "@/lib/api";
import { MENU, defSeccion, type SeccionAdmin } from "@/components/admin/secciones";

type Pendientes = ResumenAdmin["pendientes"];

/** Qué número del resumen es el badge de cada sección, y qué tan grave es. Lo que
 *  no está acá no lleva número. «grave» (rosa) es lo que no puede esperar. */
const BADGE: Partial<Record<SeccionAdmin, { campo: keyof Pendientes; grave?: boolean }>> = {
  publicaciones: { campo: "publicaciones" },
  negocios: { campo: "comercios_sin_verificar" },
  pagos: { campo: "pagos" },
  reclamos: { campo: "reclamos" },
  "cambio-numero": { campo: "cambio_numero" },
  suscripciones: { campo: "suscripciones" },
  vencimientos: { campo: "vencimientos", grave: true },
  whatsapp: { campo: "recepcion_sin_comercio" },
};

/** El enlace de una sección. `/admin` pelado es el Inicio. */
export function hrefSeccion(id: SeccionAdmin): string {
  return id === "inicio" ? "/admin" : `/admin?s=${id}`;
}

/** Quién está usando el panel, para mostrarlo en la barra. Del token (nombre o
 *  correo); sin eso, nada: no se inventa un nombre. */
function usuarioDelToken(): string | null {
  const t = getToken();
  if (!t) return null;
  try {
    const carga = JSON.parse(atob(t.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))) as Record<string, unknown>;
    for (const k of ["nombre", "name", "email"]) {
      const v = carga[k];
      if (typeof v === "string" && v.trim()) return v.trim();
    }
  } catch { /* token raro: sin nombre y listo */ }
  return null;
}

function numeroCorto(n: number): string {
  return n > 9999 ? "9999+" : String(n);
}

type Props = {
  seccion: SeccionAdmin;
  /** Va a otra sección (el que arma esto sube la URL). */
  onIr: (s: SeccionAdmin) => void;
  /** Los números del menú, del resumen. null = todavía no llegó o falló: sin número. */
  pendientes: Pendientes | null;
  onSalir: () => void;
  children: React.ReactNode;
};

export function AdminShell({ seccion, onIr, pendientes, onSalir, children }: Props) {
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [sinConexion, setSinConexion] = useState(false);
  const [usuario] = useState<string | null>(usuarioDelToken);
  const burger = useRef<HTMLButtonElement>(null);
  const lateral = useRef<HTMLElement>(null);
  const activo = useRef<HTMLAnchorElement>(null);
  const def = defSeccion(seccion);

  // Lo que esta persona puede ver: los grupos que se quedan sin ítems no se dibujan.
  const grupos = useMemo(() => MENU
    .map((g) => ({ ...g, secciones: g.secciones.filter((s) => !s.permiso || puedo(s.permiso)) }))
    .filter((g) => g.secciones.length > 0), []);

  // Elegir una sección cierra el cajón (también cubre Atrás/Adelante).
  useEffect(() => { setMenuAbierto(false); }, [seccion]);

  // El cajón abierto: Escape lo cierra (y devuelve el foco al botón), el fondo
  // no se desplaza, y al pasar a pantalla ancha —donde el menú es fijo— se
  // cierra solo para no dejar el fondo bloqueado.
  useEffect(() => {
    if (!menuAbierto) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setMenuAbierto(false); burger.current?.focus(); }
    };
    const ancha = window.matchMedia("(min-width: 900px)");
    const onAncha = () => { if (ancha.matches) setMenuAbierto(false); };
    document.addEventListener("keydown", onKey);
    ancha.addEventListener("change", onAncha);
    const antes = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    // Al abrir, el foco va a la sección activa: el teclado arranca donde estás.
    activo.current?.focus({ preventScroll: true });
    return () => {
      document.removeEventListener("keydown", onKey);
      ancha.removeEventListener("change", onAncha);
      document.body.style.overflow = antes;
    };
  }, [menuAbierto]);

  // La sección activa tiene que verse en el menú aunque esté lejos: son 25
  // ítems y el menú se desplaza solo. Se acomoda a mano y no con scrollIntoView,
  // que en el cajón cerrado (fuera de pantalla) puede mover la página entera.
  useEffect(() => {
    const nav = lateral.current;
    const el = activo.current;
    if (!nav || !el) return;
    const arriba = el.offsetTop;
    const abajo = arriba + el.offsetHeight;
    if (arriba < nav.scrollTop + 48 || abajo > nav.scrollTop + nav.clientHeight - 48) {
      nav.scrollTop = Math.max(0, arriba - nav.clientHeight / 2);
    }
  }, [seccion]);

  // Sin conexión: se avisa arriba del contenido. Lo que se ve puede ser viejo y
  // las acciones van a fallar; mejor decirlo antes de que alguien toque.
  useEffect(() => {
    const actualizar = () => setSinConexion(!navigator.onLine);
    actualizar();
    window.addEventListener("online", actualizar);
    window.addEventListener("offline", actualizar);
    return () => {
      window.removeEventListener("online", actualizar);
      window.removeEventListener("offline", actualizar);
    };
  }, []);

  /** Clic normal = cambio de sección sin recargar; con Ctrl/Cmd/Shift o botón del
   *  medio, el navegador abre el enlace como siempre (nueva pestaña). */
  function alClic(e: React.MouseEvent<HTMLAnchorElement>, id: SeccionAdmin) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    // Cerrar acá y no sólo cuando cambia la sección: tocar la sección en la
    // que ya estás (o URUKU estando en el Inicio) dejaba el cajón abierto.
    setMenuAbierto(false);
    onIr(id);
  }

  return (
    <div className="ash">
      <a className="ash-saltar" href="#ash-contenido">Saltar al contenido</a>

      <header className="ash-top">
        <button ref={burger} type="button" className="ash-burger"
                aria-label={menuAbierto ? "Cerrar el menú" : "Abrir el menú"}
                aria-expanded={menuAbierto} aria-controls="ash-menu"
                onClick={() => setMenuAbierto((v) => !v)}>
          <Ic n={menuAbierto ? "cerrar" : "menu"} s={24} />
        </button>

        <a className="ash-marca" href="/admin" onClick={(e) => alClic(e, "inicio")} aria-label="URUKU: Inicio del panel">
          URU<i>KU</i>
        </a>

        <div className="ash-ciudad">
          <SelectorCiudad modo={def.ciudad} sinLeyenda />
        </div>

        <div className="ash-top-der">
          <Link className="ash-btn" href="/" aria-label="Ver el sitio" title="Ver el sitio">
            <Ic n="abrir" s={18} /><span className="ash-btn-txt">Ver sitio</span>
          </Link>
          {usuario && <span className="ash-usuario" title={usuario}><Ic n="usuario" s={16} /> {usuario}</span>}
          <button type="button" className="ash-btn ash-salir" onClick={onSalir}>
            <Ic n="cerrar_sesion" s={18} /><span className="ash-btn-txt">Salir</span>
          </button>
        </div>
      </header>

      <div className="ash-body">
        <aside ref={lateral} id="ash-menu" className={`ash-lateral${menuAbierto ? " abierto" : ""}`}>
          <nav aria-label="Secciones del panel">
            {grupos.map((g) => (
              <div className="ash-grupo" key={g.titulo ?? "inicio"}>
                {g.titulo && <p className="ash-grupo-t">{g.titulo}</p>}
                <ul>
                  {g.secciones.map((s) => {
                    const esActiva = s.id === seccion;
                    const b = BADGE[s.id];
                    const n = b && pendientes ? pendientes[b.campo] : null;
                    return (
                      <li key={s.id}>
                        <a ref={esActiva ? activo : undefined} href={hrefSeccion(s.id)}
                           className="ash-item" aria-current={esActiva ? "page" : undefined}
                           onClick={(e) => alClic(e, s.id)}>
                          <Ic n={s.icono} s={20} />
                          <span className="ash-item-txt">{s.label}</span>
                          {n != null && n > 0 && (
                            <span className={`ash-badge${b?.grave ? " grave" : ""}`}>
                              <span aria-hidden>{numeroCorto(n)}</span>
                              <span className="ash-sr"> {n === 1 ? "pendiente" : "pendientes"}</span>
                            </span>
                          )}
                        </a>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </nav>

          {/* En el celular el usuario y «Salir» no entran en la barra: van acá. */}
          <div className="ash-pie">
            {usuario && <p className="ash-usuario-pie"><Ic n="usuario" s={16} /> {usuario}</p>}
            <button type="button" className="ash-btn ash-btn-lleno" onClick={onSalir}>
              <Ic n="cerrar_sesion" s={18} /> Salir
            </button>
          </div>
        </aside>

        <div className={`ash-fondo${menuAbierto ? " abierto" : ""}`} aria-hidden onClick={() => setMenuAbierto(false)} />

        <main id="ash-contenido" className="ash-main" tabIndex={-1}>
          {sinConexion && (
            <div className="ash-aviso ash-aviso-error" role="status">
              <span className="ash-estado-txt"><Ic n="aviso" s={18} /> Sin conexión. Lo que ves puede estar desactualizado y los cambios no se van a guardar hasta que vuelva.</span>
            </div>
          )}

          {seccion === "inicio" ? (
            // El tablero trae su propio encabezado; el h1 queda para los lectores de pantalla.
            <h1 className="ash-sr">Inicio del panel</h1>
          ) : (
            <h1 className="ash-titulo"><Ic n={def.icono} s={26} tono="marca" /> {def.label}</h1>
          )}
          <div className="ash-ciudad-aviso"><AvisoCiudad modo={def.ciudad} /></div>

          {children}
        </main>
      </div>
    </div>
  );
}
