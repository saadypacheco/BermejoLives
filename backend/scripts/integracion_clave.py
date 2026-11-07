"""Claves de la API de integración (marketing): emitir, rotar, revocar, listar.

Se corre en el servidor, desde `backend/`, con el mismo `.env` del backend (usa SUPABASE_URL y la service_role):

    python -m scripts.integracion_clave emitir --nombre "Marketing"      # imprime la clave UNA sola vez
    python -m scripts.integracion_clave rotar --key-id 1a2b3c4d5e6f      # clave nueva; la vieja sigue activa
    python -m scripts.integracion_clave revocar --key-id 1a2b3c4d5e6f    # desde ya da 401
    python -m scripts.integracion_clave listar

La clave tiene la forma `uki_<key_id>.<secreto>`. En la base sólo queda sha256(secreto): si se pierde no se
recupera, se rota. Guardala en el `.env` del sistema de marketing (URUKU_API_KEY), nunca en una base ni en un chat.

Rotar sin cortar la integración: `rotar` → poner la clave nueva en marketing → comprobar que anda (GET /me) →
`revocar` la vieja.

El ALCANCE (qué comercios ve la clave) no se maneja acá sino desde el admin: /admin/integracion/clientes/<id>/comercios.
"""
from __future__ import annotations

import argparse
import getpass
import sys

from app.db.repository import get_repo
from app.services import integracion


def _quien() -> str:
    try:
        return f"script:{getpass.getuser()}"
    except Exception:  # noqa: BLE001
        return "script"


def _mostrar_clave(r: dict) -> None:
    print("\nGuardá esta clave AHORA: no se vuelve a mostrar (en la base queda sólo su sha256).\n")
    print(f"    {r['clave']}\n")
    print(f"key_id: {r['key_id']}   cliente (grupo) id: {r['grupo_id']}   scopes: {', '.join(r['scopes'])}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("emitir", help="cliente nuevo con su primera clave")
    e.add_argument("--nombre", required=True)
    e.add_argument("--scopes", nargs="*", default=None,
                   help=f"por defecto: {' '.join(integracion.SCOPES_POR_DEFECTO)} (broadcast:send sólo si se pide acá)")
    r = sub.add_parser("rotar", help="clave nueva para el mismo cliente (la vieja sigue activa)")
    r.add_argument("--key-id", required=True)
    v = sub.add_parser("revocar", help="desactiva una clave")
    v.add_argument("--key-id", required=True)
    sub.add_parser("listar", help="las claves (sin secretos)")
    a = ap.parse_args(argv)

    repo = get_repo()
    try:
        if a.cmd == "emitir":
            _mostrar_clave(integracion.emitir_clave(repo, a.nombre, a.scopes, _quien()))
        elif a.cmd == "rotar":
            res = integracion.rotar_clave(repo, a.key_id, _quien())
            _mostrar_clave(res)
            print(f"\nLa clave {res['reemplaza']} SIGUE activa: revocala cuando marketing ya use la nueva.")
        elif a.cmd == "revocar":
            res = integracion.revocar_clave(repo, a.key_id, _quien())
            print("ya estaba revocada" if res["ya_revocada"] else f"clave {a.key_id} revocada")
        else:
            for c in repo.integracion_listar_clientes():
                estado = "activa" if c.get("activo") and not c.get("revocada_at") else "revocada"
                print(f"{c['key_id']:<14} {estado:<9} {c['nombre']:<24} cliente={c['grupo_id']} "
                      f"último uso={c.get('last_used_at') or '-'} scopes={','.join(c['scopes'])}")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
