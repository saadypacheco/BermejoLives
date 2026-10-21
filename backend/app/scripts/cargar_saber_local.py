"""Carga el saber local de una ciudad desde `data/saber_local/<ciudad>.json`.

    # en el contenedor (el JSON viaja en la imagen, en /app/data)
    docker compose -f docker-compose.prod.yml --env-file .env exec -T backend \\
        python -m app.scripts.cargar_saber_local bermejo --dry-run
    docker compose -f docker-compose.prod.yml --env-file .env exec -T backend \\
        python -m app.scripts.cargar_saber_local bermejo

El archivo es una lista de {pregunta, respuesta, palabras, tema, fuente, consultado, verificado}.
Va a la tabla `saber_local` (la que lee `asistente._saber_local`):

    palabras -> etiquetas      tema -> seccion (los temas que la guía no tiene van a «general»)

  - Por defecto entra SÓLO lo `verificado: true`; `--todos` suma también lo no verificado.
  - `--dry-run` cuenta y lista lo que haría, sin escribir nada.
  - Idempotente: la pregunta (sin tildes, mayúsculas ni signos) es la clave. Si ya existe, se
    ACTUALIZA (respuesta, etiquetas, sección) y no se duplica; si no cambió nada, no se toca.
    Eso incluye las preguntas que sembraron las migraciones 0106/0107/0110.
  - Nunca borra. Una fila que el admin dio de baja (`activo = false`) se actualiza igual pero
    sigue de baja: reimportar no resucita lo que alguien apagó a propósito.
  - `fuente`, `consultado` y `verificado` no tienen columna: `verificado` decide qué entra y
    el resto queda en el JSON (que está en el repo).

Sale con código 1 si el archivo no se puede leer o tiene una fila inválida; en ese caso no
escribe nada.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from app.api.asistente import SECCIONES, _etiquetas
from app.services.asistente import _norm

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "saber_local"

# El tema del JSON no siempre es una sección de la guía (/guia): lo que no está acá se
# ordena por afinidad, y lo que no tiene afinidad va a «general».
_TEMA_A_SECCION = {
    "compras": "comercios", "cambio": "comercios", "pagos": "comercios",
}


def seccion_de(tema: str | None) -> str:
    t = (tema or "").strip().lower()
    t = _TEMA_A_SECCION.get(t, t)
    return t if t in SECCIONES else "general"


def _leer(ruta: Path) -> list[dict]:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if not isinstance(datos, list):
        raise ValueError("el JSON tiene que ser una lista de entradas")
    return datos


def _validar(entrada: dict, i: int) -> dict:
    """La entrada lista para guardar; ValueError si está mal."""
    if not isinstance(entrada, dict):
        raise ValueError(f"entrada {i}: no es un objeto")
    pregunta = " ".join(str(entrada.get("pregunta") or "").split())
    respuesta = str(entrada.get("respuesta") or "").strip()
    if len(pregunta) < 3 or len(pregunta) > 300:
        raise ValueError(f"entrada {i}: la pregunta tiene que tener entre 3 y 300 caracteres")
    if len(respuesta) < 3 or len(respuesta) > 2000:
        raise ValueError(f"entrada {i} («{pregunta}»): la respuesta tiene que tener entre 3 y 2000 caracteres")
    palabras = entrada.get("palabras") or []
    if not isinstance(palabras, list):
        raise ValueError(f"entrada {i} («{pregunta}»): «palabras» tiene que ser una lista")
    return {
        "pregunta": pregunta,
        "respuesta": respuesta,
        "etiquetas": _etiquetas([str(p) for p in palabras]),
        "seccion": seccion_de(entrada.get("tema")),
        "verificado": entrada.get("verificado") is True,
    }


def planificar(repo, entradas: list[dict], ciudad_id: str | None, todos: bool = False) -> list[dict]:
    """Qué se haría con cada entrada: {accion, entrada, existente}. `accion` es
    crea | actualiza | sin_cambios | omite. No escribe."""
    # Una sola lectura: el saber del SITIO (sin las respuestas de un local), activo o no.
    # Si hay dos filas con la misma pregunta se prefiere la de esta ciudad.
    existentes: dict[str, dict] = {}
    for f in repo.list_saber_local(False) or []:
        clave = _norm(f.get("pregunta", ""))
        previa = existentes.get(clave)
        if previa is None or (f.get("ciudad_id") == ciudad_id and previa.get("ciudad_id") != ciudad_id):
            existentes[clave] = f

    # Si el archivo repite una pregunta, vale la última (como si se cargaran en orden).
    por_clave: dict[str, dict] = {}
    for e in entradas:
        por_clave[_norm(e["pregunta"])] = e

    plan = []
    for clave, e in por_clave.items():
        if not e["verificado"] and not todos:
            plan.append({"accion": "omite", "entrada": e, "existente": None})
            continue
        f = existentes.get(clave)
        if f is None:
            plan.append({"accion": "crea", "entrada": e, "existente": None})
            continue
        igual = (f.get("respuesta") == e["respuesta"]
                 and sorted(f.get("etiquetas") or []) == e["etiquetas"]
                 and (f.get("seccion") or "general") == e["seccion"])
        plan.append({"accion": "sin_cambios" if igual else "actualiza", "entrada": e, "existente": f})
    return plan


def aplicar(repo, plan: list[dict], ciudad_id: str | None, ciudad: str) -> None:
    for p in plan:
        e, f = p["entrada"], p["existente"]
        if p["accion"] == "crea":
            repo.upsert_saber_local({
                "pregunta": e["pregunta"], "respuesta": e["respuesta"], "etiquetas": e["etiquetas"],
                "seccion": e["seccion"], "ciudad_id": ciudad_id, "activo": True,
                "creado_por": f"import:{ciudad}",
            })
        elif p["accion"] == "actualiza":
            # Se conservan la ciudad, el `activo` y el `creado_por` de la fila que ya estaba.
            repo.upsert_saber_local({
                "id": f["id"], "respuesta": e["respuesta"], "etiquetas": e["etiquetas"],
                "seccion": e["seccion"], "activo": f.get("activo", True),
            })


_ROTULO = {"crea": "crea", "actualiza": "actualiza", "sin_cambios": "sin cambios", "omite": "omite (no verificado)"}


def main(argv: list[str] | None = None, repo=None) -> int:
    ap = argparse.ArgumentParser(prog="cargar_saber_local", description=__doc__.split("\n")[0])
    ap.add_argument("ciudad", help="slug de la ciudad: lee data/saber_local/<ciudad>.json (o la ruta a un .json)")
    ap.add_argument("--todos", action="store_true", help="incluye también las entradas con verificado: false")
    ap.add_argument("--dry-run", action="store_true", help="muestra qué haría, sin escribir")
    args = ap.parse_args(argv)

    if args.ciudad.endswith(".json"):
        ruta = Path(args.ciudad)
        ciudad = ruta.stem
    else:
        if not re.fullmatch(r"[a-z0-9_-]+", args.ciudad):
            print(f"Ciudad inválida: {args.ciudad!r} (un slug, como «bermejo»).", file=sys.stderr)
            return 1
        ciudad = args.ciudad
        ruta = DATA_DIR / f"{ciudad}.json"

    try:
        crudo = _leer(ruta)
        entradas = [_validar(e, i) for i, e in enumerate(crudo, 1)]
    except (OSError, ValueError) as exc:        # JSONDecodeError es un ValueError
        print(f"No se pudo leer {ruta}: {exc}", file=sys.stderr)
        return 1

    if repo is None:
        from app.db.repository import get_repo
        repo = get_repo()
    ciudad_id = repo.get_ciudad_id(ciudad)
    if not ciudad_id:
        print(f"No existe la ciudad «{ciudad}» en la base.", file=sys.stderr)
        return 1

    plan = planificar(repo, entradas, ciudad_id, todos=args.todos)
    for p in plan:
        print(f"  {_ROTULO[p['accion']]:<24} {p['entrada']['pregunta']}")
    cuenta = {a: sum(1 for p in plan if p["accion"] == a) for a in _ROTULO}

    if not args.dry_run:
        aplicar(repo, plan, ciudad_id, ciudad)
    print(("DRY-RUN, no se escribió nada. " if args.dry_run else "")
          + f"Crea: {cuenta['crea']} · Actualiza: {cuenta['actualiza']} · "
            f"Sin cambios: {cuenta['sin_cambios']} · Omite (no verificadas): {cuenta['omite']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
