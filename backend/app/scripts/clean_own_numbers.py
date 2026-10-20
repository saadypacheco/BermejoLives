"""Limpieza única del bug P1: números de URUKU autorizados para un comercio.

Hasta E1, un número propio (`WA_NUMEROS_PROPIOS`) que le escribía 1-a-1 al
Registrador con un URUKU-XXXX válido quedaba AUTORIZADO para ese comercio en
`comercio_numeros`. Este script los encuentra y, con `--apply`, los da de baja.

    # en el contenedor; sin --apply sólo LISTA y no cambia nada
    docker compose -f docker-compose.prod.yml exec -T backend \\
        python -m app.scripts.clean_own_numbers
    docker compose -f docker-compose.prod.yml exec -T backend \\
        python -m app.scripts.clean_own_numbers --apply

También lista los comercios cuyo `wa_jid` quedó atado a un número de URUKU (`@c.us` o
`@s.whatsapp.net`) y, con `--apply`, les suelta ese `wa_jid` (queda NULL).

Con `--apply` pone `activo=false` (baja lógica): NO hay DELETE. Además lista lo que
esos números hicieron publicar, para que el admin lo mire a mano; las publicaciones
no se tocan.

El explorador (`WA_NUMEROS_EXPLORADOR`) también es un número propio, pero publica
por código a propósito y no deja nada en `comercio_numeros`: si aparece acá es un
resto del bug y también se limpia.
"""
from __future__ import annotations

import argparse

from app.core import config as cfg
from app.core.config import settings
from app.db.repository import Repo, get_repo


def _propios() -> list[str]:
    return sorted(cfg._numeros_propios(settings.wa_numeros_propios)
                  | cfg._numeros_propios(settings.wa_numeros_explorador, "WA_NUMEROS_EXPLORADOR"))


def main(argv: list[str] | None = None, repo: Repo | None = None) -> int:
    ap = argparse.ArgumentParser(prog="clean_own_numbers", description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true",
                    help="dar de baja (activo=false) los números; sin esto sólo se lista")
    args = ap.parse_args(argv)

    repo = repo or get_repo()
    propios = _propios()
    if not propios:
        print("WA_NUMEROS_PROPIOS está vacío o no tiene números válidos: no hay nada que limpiar.")
        return 0

    filas = repo.list_numeros_propios_autorizados(propios)
    print(f"Números de URUKU autorizados para algún comercio: {len(filas)}")
    for f in filas:
        comercio = f.get("comercios") or {}
        print(f"  {f['numero']}  ->  {comercio.get('nombre') or f['comercio_id']}"
              f"  (creado por {f.get('created_by')}, {f.get('created_at')})")

    # El mismo bug también ataba el `wa_jid` del comercio al número de URUKU
    # (`vincular_wa_jid`): desde ahí todo lo que ese teléfono mandaba lo identificaba.
    jids = [f"{n}{sufijo}" for n in propios for sufijo in ("@c.us", "@s.whatsapp.net")]
    con_jid = repo.list_comercios_con_wa_jid_propio(jids)
    print(f"\nComercios con el wa_jid de un número de URUKU: {len(con_jid)}")
    for c in con_jid:
        print(f"  {c['wa_jid']}  ->  {c.get('nombre') or c['id']}")

    publicadas = repo.list_wa_inbox_publicadas_de(propios)
    print(f"\nPublicaciones que hicieron esos números (para revisar a mano): {len(publicadas)}")
    for p in publicadas:
        comercio = p.get("comercios") or {}
        print(f"  {p['wa_message_id']}  {p['phone']}  ->  {comercio.get('nombre') or p.get('comercio_id')}"
              f"  ({p.get('created_at')})")

    if not args.apply:
        print("\nSIN --apply: no se cambió nada.")
        return 0

    for f in filas:
        repo.desactivar_numero_comercio(f["id"])
    for c in con_jid:
        repo.limpiar_wa_jid_comercio(c["id"])
    print(f"\nListo: {len(filas)} número(s) dados de baja (activo=false) y "
          f"{len(con_jid)} wa_jid de comercio soltados (queda vacío).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
