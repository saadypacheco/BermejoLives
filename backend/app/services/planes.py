"""Qué puede publicar cada comercio, y qué pasa cuando se pasa.

LO QUE ESTO ARREGLA
===================
La página de venta prometía 15 y 50 publicaciones por mes y el sistema no
contaba ninguna. Un comercio del plan de 15 podía mandar 300 y salían las 300 —
así que el plan caro no daba nada que el barato no tuviera, y no había ninguna
razón para subir.

EL CICLO NO ES EL MES CALENDARIO
================================
Se paga un día y corren dos meses desde ese día. Contar por mes calendario le
daría al que paga el 28 una cuota de tres días. El ciclo arranca en la fecha de
pago y se cuenta hacia atrás desde `paga_hasta`, que es el dato que ya existe.

EL SILENCIO ES EL PEOR RESULTADO
================================
Cuando un comercio llega al tope, lo que NO puede pasar es que su foto no
aparezca y no se entere. Es exactamente cómo se perdían las ofertas antes de la
bandeja: el comerciante manda otra vez, tampoco sale, y se va convencido de que
esto no funciona. Por eso el aviso es parte de la regla, no un extra.
"""
from __future__ import annotations

from datetime import date, timedelta

import structlog

logger = structlog.get_logger()

# Cuánto dura un ciclo si no se puede deducir de los pagos. Un mes.
_CICLO_DIAS = 30


def plan_de(repo, comercio: dict) -> dict:
    """El plan del comercio, con sus valores. Nunca devuelve None.

    Si el plan quedó apuntando a algo que no existe —dato viejo, plan borrado—
    cae al gratuito en vez de explotar. Un comercio sin plan no puede quedar sin
    poder publicar por un problema de datos nuestro.
    """
    slug = (comercio.get("plan") or "gratis").strip() or "gratis"
    plan = repo.get_plan(slug)
    if not plan:
        logger.warning("planes.plan_inexistente", comercio=comercio.get("id"), plan=slug)
        plan = repo.get_plan("gratis") or {}
    return plan


def inicio_del_ciclo(comercio: dict, hoy: date | None = None) -> date:
    """Desde cuándo se cuentan las publicaciones de este comercio.

    `paga_hasta` marca el final del período pago. El ciclo actual es el mes que
    termina ahí. Sin `paga_hasta` (nunca pagó, o es gratuito) se usan los
    últimos 30 días corridos, que es lo más parecido a "su mes".
    """
    hoy = hoy or date.today()
    crudo = comercio.get("paga_hasta")
    if crudo:
        try:
            hasta = date.fromisoformat(str(crudo)[:10])
        except ValueError:
            hasta = None
        if hasta:
            # Se retrocede de a un mes hasta caer en el ciclo que contiene hoy.
            # Si el pago venció hace rato, el ciclo vigente es el que corre
            # ahora, no el último pago — cobrarle a alguien las publicaciones de
            # un ciclo viejo sería cobrarle dos veces lo mismo.
            inicio = hasta - timedelta(days=_CICLO_DIAS)
            while inicio > hoy:
                hasta, inicio = inicio, inicio - timedelta(days=_CICLO_DIAS)
            while inicio + timedelta(days=_CICLO_DIAS) <= hoy:
                inicio = inicio + timedelta(days=_CICLO_DIAS)
            return inicio
    return hoy - timedelta(days=_CICLO_DIAS)


def funcion(plan: dict, nombre: str) -> bool:
    """¿El plan incluye esta función? Lo que no está declarado es que no.

    Es lo que permite agregar una función nueva sin migrar la base: se le suma
    la clave al `funciones` del plan y el código que ya pregunta por ella
    empieza a decir que sí.
    """
    return bool((plan.get("funciones") or {}).get(nombre))


def estado(repo, comercio: dict, hoy: date | None = None) -> dict:
    """Cuánto lleva publicado, cuánto le queda y qué pasa si manda una más."""
    plan = plan_de(repo, comercio)
    cuota = plan.get("publicaciones_mes")
    desde = inicio_del_ciclo(comercio, hoy)
    usadas = repo.contar_publicaciones_desde(comercio["id"], desde.isoformat())

    if cuota is None:
        return {"plan": plan, "cuota": None, "usadas": usadas, "quedan": None,
                "desde": desde.isoformat(), "excedido": False}

    quedan = max(0, int(cuota) - usadas)
    return {"plan": plan, "cuota": int(cuota), "usadas": usadas, "quedan": quedan,
            "desde": desde.isoformat(), "excedido": quedan == 0}


def texto_de_aviso(est: dict, siguiente: dict | None) -> str:
    """El mensaje que recibe el comerciante cuando llega al tope.

    LAS DOS SALIDAS VAN JUNTAS, SIEMPRE
    ===================================
    El que no quiere gastar de más igual tiene que enterarse de que existe el
    plan de arriba, y el que tiene apuro tiene que poder pagar la extra y seguir.
    Ofrecer una sola es elegir por él.
    """
    plan = est["plan"]
    partes = [f"Llegaste a las {est['cuota']} publicaciones de tu plan "
              f"{plan.get('nombre') or plan.get('slug')}."]

    if plan.get("permite_extras"):
        extra = plan.get("precio_publicacion_extra")
        partes.append(f"Las siguientes salen a Bs {_monto(extra)} cada una.")
    else:
        partes.append("Para seguir publicando este mes hay que pasar de plan.")

    if siguiente:
        cuota = siguiente.get("publicaciones_mes")
        cuanto = "sin límite" if cuota is None else f"{cuota} publicaciones"
        partes.append(f"O pasás a {siguiente.get('nombre')} por Bs "
                      f"{_monto(siguiente.get('precio_mes'))} al mes y tenés {cuanto}.")

    partes.append("Avisanos y lo arreglamos.")
    return " ".join(partes)


def _monto(v) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{f:,.0f}".replace(",", ".") if f == int(f) else f"{f:,.2f}"


def revisar_antes_de_publicar(repo, comercio: dict) -> dict:
    """¿Puede publicar? Y si se pasó, ¿qué corresponde hacer?

    Devuelve siempre `puede`, y cuando se pasó, con qué consecuencia:
    - `cobrar`: sale, y genera un cargo de la publicación extra.
    - `bloquear`: no sale, porque el plan no admite extras.

    No manda el aviso ni crea el cargo: sólo decide. Quien publica es el que
    tiene el mensaje a mano para contestarle al comerciante en su propio chat,
    que es donde el aviso sirve.
    """
    est = estado(repo, comercio)
    if not est["excedido"]:
        return {"puede": True, "consecuencia": None, **est}

    plan = est["plan"]
    if plan.get("permite_extras"):
        return {"puede": True, "consecuencia": "cobrar", **est}
    return {"puede": False, "consecuencia": "bloquear", **est}


def plan_siguiente(repo, plan: dict) -> dict | None:
    """El plan de arriba, para poder ofrecerlo. None si ya está en el último."""
    todos = [p for p in repo.list_planes(solo_visibles=True)
             if (p.get("orden") or 0) > (plan.get("orden") or 0)]
    return sorted(todos, key=lambda p: p.get("orden") or 0)[0] if todos else None


def cobrar_extra(repo, comercio: dict, publicacion_id: str | None, plan: dict) -> None:
    """Deja el cargo anotado. Nunca rompe la publicación.

    Si esto fallara y cortara el flujo, un problema de facturación dejaría al
    comerciante sin publicar — que es cambiar un problema de plata por uno de
    servicio, el peor negocio posible.
    """
    try:
        repo.registrar_cargo_extra(comercio["id"], publicacion_id,
                                   plan.get("precio_publicacion_extra") or 0,
                                   plan.get("moneda") or "BOB")
    except Exception:  # noqa: BLE001
        logger.warning("planes.cargo_extra_fallo", comercio=comercio.get("id"), exc_info=True)
