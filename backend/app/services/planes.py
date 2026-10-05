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
from pathlib import Path

import structlog

from app.core.config import settings

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

    SIN PRECIOS DE PLANES
    =====================
    El plan de arriba se nombra con su cuota, nunca con lo que cuesta: los
    precios de los planes no se muestran en ningún texto (decisión del
    4/10/2026) y se hablan con el comerciante. El Bs de la publicación extra sí
    va: es lo que va a pagar si sigue, y no avisarle sería cobrarle de sorpresa.
    """
    plan = est["plan"]
    if est.get("consecuencia") == "vencido":
        meses = int(plan.get("publica_meses") or 0)
        partes = [f"Se terminaron los {meses} meses de publicar gratis con el plan "
                  f"{plan.get('nombre') or plan.get('slug')}. Tu local sigue en el mapa."]
        if siguiente:
            cuota = siguiente.get("publicaciones_mes")
            cuanto = "sin límite" if cuota is None else f"hasta {cuota} publicaciones por mes"
            partes.append(f"Para seguir publicando, pasás a {siguiente.get('nombre')} "
                          f"y tenés {cuanto}.")
        partes.append("Avisanos y lo arreglamos.")
        return " ".join(partes)

    partes = [f"Llegaste a las {est['cuota']} publicaciones de tu plan "
              f"{plan.get('nombre') or plan.get('slug')}."]

    if plan.get("permite_extras"):
        extra = plan.get("precio_publicacion_extra")
        partes.append(f"Las siguientes salen a Bs {_monto(extra)} cada una.")
    else:
        partes.append("Para seguir publicando este mes hay que pasar de plan.")

    if siguiente:
        cuota = siguiente.get("publicaciones_mes")
        cuanto = "publicaciones sin límite" if cuota is None else f"{cuota} publicaciones por mes"
        partes.append(f"O pasás a {siguiente.get('nombre')} y tenés {cuanto}.")

    partes.append("Avisanos y lo arreglamos.")
    return " ".join(partes)


def _monto(v) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{f:,.0f}".replace(",", ".") if f == int(f) else f"{f:,.2f}"


def periodo_vencido(plan: dict, comercio: dict, hoy: date | None = None) -> bool:
    """¿Se le terminó al comercio el tiempo de publicar con este plan?

    `publica_meses` es cuántos meses desde el alta puede publicar el plan
    (NULL = siempre). Es el "gratis por dos meses" del Básico en la etapa de
    arranque: después sigue en el mapa, pero para publicar hay que pasar a
    Publica. Sin fecha de alta no se puede saber, y ante la duda se deja
    publicar: bloquear por un dato que falta es castigar al comercio por un
    problema nuestro.
    """
    meses = plan.get("publica_meses")
    if not meses:
        return False
    crudo = comercio.get("created_at")
    if not crudo:
        return False
    try:
        alta = date.fromisoformat(str(crudo)[:10])
    except ValueError:
        return False
    hoy = hoy or date.today()
    return hoy > alta + timedelta(days=int(meses) * 30)


def revisar_antes_de_publicar(repo, comercio: dict) -> dict:
    """¿Puede publicar? Y si se pasó, ¿qué corresponde hacer?

    Devuelve siempre `puede`, y cuando se pasó, con qué consecuencia:
    - `cobrar`: sale, y genera un cargo de la publicación extra.
    - `bloquear`: no sale, porque el plan no admite extras.
    - `vencido`: no sale, porque el plan sólo publica los primeros meses y ya
      pasaron. El comercio sigue en el mapa; para publicar, pasa de plan.

    No manda el aviso ni crea el cargo: sólo decide. Quien publica es el que
    tiene el mensaje a mano para contestarle al comerciante en su propio chat,
    que es donde el aviso sirve.
    """
    est = estado(repo, comercio)
    if periodo_vencido(est["plan"], comercio):
        return {"puede": False, "consecuencia": "vencido", **est}
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


# ══════════════════════════════════════════════ el tope de publicaciones guardadas
#
# POR QUÉ EXISTE
# ==============
# Cada oferta que entra por WhatsApp deja una foto en el disco. Sin tope, el
# disco crece mientras haya comercios publicando. El plan fija cuántas
# publicaciones activas guarda cada comercio (`publicaciones_guardadas`); al
# entrar una más, la más vieja se archiva y su foto se borra.
#
# ARCHIVAR NO ES BORRAR LA FILA
# =============================
# La regla del proyecto es soft-delete: la fila queda con `activo = false`. Lo que
# ocupa espacio es el archivo de la foto, y es lo único que se borra.

# Dónde guarda la ingesta las fotos de ofertas: `{slug}/ofertas/{hex}.jpg`
# (wa_media.guardar_imagen_publicacion). Es lo ÚNICO que se borra al archivar.
#
# POR QUÉ NO "TODO LO QUE ESTÉ BAJO LA BASE DE FOTOS"
# ===================================================
# El `imagen_url` de una publicación hecha desde el panel es un campo de texto
# libre: el comerciante puede pegar ahí la URL de su portada o de una foto de
# su galería, que viven en la misma base pública (`{slug}/{hex}.jpg`). Borrar
# eso al archivar la publicación dejaría la ficha del local con una foto rota,
# por algo que el comerciante ni sabe que pasó. Las únicas fotos que nacen de
# una publicación, y que nadie más referencia, son las de `ofertas/`.
_CARPETA_OFERTAS = "ofertas"

#: Cuántas publicaciones se archivan como máximo por cada publicación nueva.
_MAX_ARCHIVAR_POR_VEZ = 5


def _archivo_de_oferta(imagen_url: str | None, slug: str | None) -> Path | None:
    """La ruta en disco de una foto de oferta PROPIA de ese comercio, o None si
    no hay que tocarla.

    Devuelve None —y entonces no se borra nada— cuando la URL:
    - está vacía o no cuelga de `fotos_public_base_url` (una foto externa, un
      producto de la tienda, un link: no es nuestra);
    - no es CANÓNICA: trae `?`, `#` o cualquier caracter codificado (`%2F`,
      `%2e`…). La guarda de «otra publicación la usa» compara la URL tal cual
      está en la base; si acá se limpiara la URL antes de armar la ruta, una
      variante (`…/abc.jpg?x=1`) no coincidiría con la de la otra fila y se
      borraría una foto que alguien sigue mostrando. La que arma URUKU nunca
      trae nada de eso;
    - no es exactamente `<slug-del-comercio>/ofertas/<archivo>`. Un comercio
      sólo puede hacer borrar SUS fotos de ofertas: el `imagen_url` de una
      publicación hecha desde el panel es texto libre, y sin esto bastaba con
      pegar la URL de la oferta de otro local;
    - trae `..`, `.`, `\\`, partes vacías o un byte nulo;
    - resuelta (siguiendo enlaces simbólicos) cae fuera de `fotos_dir`.
    """
    if not imagen_url or not slug:
        return None
    # Con la barra final: sin ella, `.../fotos-viejas/x.jpg` pasaría por colgar
    # de `.../fotos`.
    base = settings.fotos_public_base_url.rstrip("/") + "/"
    if not imagen_url.startswith(base):
        return None
    relativa = imagen_url[len(base):]
    if any(c in relativa for c in "?#%\\\x00"):
        return None
    partes = relativa.split("/")
    if len(partes) != 3 or partes[0] != slug or partes[1] != _CARPETA_OFERTAS:
        return None
    if any(p in ("", ".", "..") for p in partes):
        return None
    try:
        raiz = Path(settings.fotos_dir).resolve()
        ruta = (raiz / relativa).resolve()
    except (OSError, ValueError):
        return None
    # La última palabra: aunque todo lo anterior fallara, una ruta que no cuelga
    # de la carpeta de fotos no se toca.
    if not ruta.is_relative_to(raiz) or ruta == raiz:
        return None
    return ruta


def _borrar_foto_de_oferta(repo, comercio: dict, pub: dict) -> bool:
    """Borra el archivo de la foto si es una oferta propia del comercio y nadie
    más la usa.

    Devuelve True si el archivo se borró. Un archivo que ya no existe no es un
    error: el objetivo era que no esté, y no está.
    """
    ruta = _archivo_de_oferta(pub.get("imagen_url"), comercio.get("slug"))
    if ruta is None:
        # Dicho y no callado: si las fotos quedaran guardadas con otra base (un
        # cambio de dominio), el tope archivaría sin bajar el disco y nadie lo
        # sabría. Con este evento se ve.
        if pub.get("imagen_url"):
            logger.info("planes.foto_no_se_borra", pub=pub.get("id"),
                        motivo="no es una foto de ofertas propia en forma canónica")
        return False
    # Otra publicación activa con la misma URL (un comercio que reutilizó la
    # foto, una publicación fusionada) la sigue mostrando: borrarla la rompe.
    if repo.imagen_en_uso(pub["imagen_url"], pub["id"]):
        logger.info("planes.foto_en_uso_no_se_borra", pub=pub["id"])
        return False
    try:
        ruta.unlink(missing_ok=True)
    except OSError:
        logger.warning("planes.foto_borrar_fallo", pub=pub["id"], exc_info=True)
        return False
    logger.info("planes.foto_borrada", pub=pub["id"])
    return True


def _archivar_una(repo, comercio: dict, pub: dict) -> bool:
    """Archiva UNA publicación. True si quedó archivada.

    Los tres pasos son independientes y van en este orden a propósito: primero
    se archiva la fila, y SÓLO si eso salió bien se toca lo demás. Borrar la
    foto de una publicación que sigue activa la dejaría rota en el feed.
    """
    try:
        repo.archivar_publicacion(pub["id"])
    except Exception:  # noqa: BLE001
        logger.warning("planes.archivar_fallo", comercio=comercio.get("id"),
                       pub=pub.get("id"), exc_info=True)
        return False

    # Una publicación archivada no sale a las redes. `procesar` además la frena
    # si alguien reintenta a mano, pero lo que está pendiente se descarta acá
    # para que la cola no muestre como "por salir" algo que no va a salir.
    try:
        repo.descartar_difusion_de(pub["id"], "archivada por el tope de publicaciones guardadas")
    except Exception:  # noqa: BLE001
        logger.warning("planes.descartar_difusion_fallo", pub=pub.get("id"), exc_info=True)

    try:
        _borrar_foto_de_oferta(repo, comercio, pub)
    except Exception:  # noqa: BLE001
        logger.warning("planes.foto_fallo", pub=pub.get("id"), exc_info=True)
    return True


def archivar_excedentes(repo, comercio: dict) -> int:
    """Deja al comercio dentro de su tope de publicaciones guardadas.

    Cuenta las publicaciones ACTIVAS del comercio, del estado que sean —todas
    ocupan disco, también las pendientes y las rechazadas— y archiva las más
    viejas por `created_at` hasta quedar en el tope. Con `publicaciones_guardadas`
    en NULL no hace nada. Devuelve cuántas archivó.

    NUNCA LANZA
    ===========
    Se llama DESPUÉS de insertar la publicación nueva. Si esto rompiera, el
    comerciante vería un error por una oferta que sí quedó creada, y mandaría
    otra: dos publicaciones por un problema de limpieza. Todo falla al log y el
    flujo sigue; lo que no se archivó hoy se archiva en la próxima publicación.
    """
    try:
        tope = plan_de(repo, comercio).get("publicaciones_guardadas")
        if tope is None:
            return 0
        tope = int(tope)
        # La base lo impide (CHECK > 0), pero un 0 acá vaciaría el comercio entero
        # y una publicación recién creada saldría archivada: se ignora.
        if tope < 1:
            logger.warning("planes.tope_invalido", comercio=comercio.get("id"), tope=tope)
            return 0
        activas = repo.publicaciones_activas_de(comercio["id"])
        sobran = len(activas) - tope
        if sobran <= 0:
            return 0
    except Exception:  # noqa: BLE001
        logger.warning("planes.archivar_excedentes_fallo", comercio=comercio.get("id"), exc_info=True)
        return 0

    # `activas` viene de la más vieja a la más nueva: se archivan las primeras.
    #
    # De a pocas por publicación nueva. Si alguien baja el tope de 70 a 7 en
    # Admin (o se equivoca de tecla), sin este freno la próxima oferta de cada
    # comercio archivaría 63 publicaciones y borraría 63 fotos de una, sin
    # vuelta atrás. Así el comercio converge al tope de a poco y el error se
    # alcanza a ver y corregir.
    if sobran > _MAX_ARCHIVAR_POR_VEZ:
        logger.warning("planes.tope_muy_excedido", comercio=comercio.get("id"),
                       sobran=sobran, tope=tope, archiva_ahora=_MAX_ARCHIVAR_POR_VEZ)
        sobran = _MAX_ARCHIVAR_POR_VEZ
    archivadas = sum(1 for pub in activas[:sobran] if _archivar_una(repo, comercio, pub))
    if archivadas:
        logger.info("planes.archivadas", comercio=comercio.get("id"),
                    archivadas=archivadas, tope=tope)
    return archivadas
