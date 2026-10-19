"""Doble en memoria de `app/db/integracion_repo.py` (mixin de FakeRepo)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone


def _ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FakeIntegracionMixin:
    # Se crean perezosamente: FakeRepo no los declara en su __init__.
    def _integ(self) -> dict:
        d = self.__dict__
        if "_integ_state" not in d:
            d["_integ_state"] = {"clientes": {}, "alcance": {}, "idem": {}, "eventos": [], "seq": 0}
        return d["_integ_state"]

    @property
    def integ_eventos(self) -> list[dict]:
        return self._integ()["eventos"]

    # ── clientes ─────────────────────────────────────────────────────────────────────────────────────────
    def integracion_cliente_por_key_id(self, key_id):
        return next((dict(c) for c in self._integ()["clientes"].values() if c["key_id"] == key_id), None)

    def integracion_get_cliente(self, cliente_id):
        c = self._integ()["clientes"].get(cliente_id)
        return {k: v for k, v in c.items() if k != "key_hash"} if c else None

    def integracion_listar_clientes(self):
        return [{k: v for k, v in c.items() if k != "key_hash"} for c in self._integ()["clientes"].values()]

    def integracion_crear_cliente(self, row):
        fila = {"id": row.get("id") or str(uuid.uuid4()), "activo": True, "created_at": _ahora_iso(),
                "last_used_at": None, "rotada_de": None, "revocada_at": None, **row}
        fila.setdefault("grupo_id", fila["id"])
        self._integ()["clientes"][fila["id"]] = fila
        return dict(fila)

    def integracion_actualizar_cliente(self, cliente_id, patch):
        c = self._integ()["clientes"].get(cliente_id)
        if not c:
            return {}
        c.update(patch)
        return dict(c)

    def integracion_tocar_cliente(self, cliente_id):
        c = self._integ()["clientes"].get(cliente_id)
        if c:
            c["last_used_at"] = _ahora_iso()

    # ── alcance ──────────────────────────────────────────────────────────────────────────────────────────
    def es_comercio_gestionado(self, comercio_id):
        return any(f["comercio_id"] == comercio_id and f["activo"] for f in self._integ()["alcance"].values())

    def integracion_comercios_de(self, grupo_id, solo_activos=True):
        return [dict(f) for (g, _), f in sorted(self._integ()["alcance"].items())
                if g == grupo_id and (f["activo"] or not solo_activos)]

    def integracion_set_comercio(self, grupo_id, comercio_id, activo, por):
        fila = {"cliente_id": grupo_id, "comercio_id": comercio_id, "activo": activo, "agregado_por": por,
                "desde": _ahora_iso()}
        self._integ()["alcance"][(grupo_id, comercio_id)] = fila
        return dict(fila)

    def integracion_comercios_verificados(self):
        return [{"id": c["id"], "slug": c.get("slug"), "nombre": c.get("nombre")}
                for c in self.comercios.values() if c.get("activo", True) and c.get("verificado")]

    def integracion_info_comercios(self, comercio_ids):
        salida = []
        for cid in comercio_ids:
            c = self.comercios.get(cid)
            if not c:
                continue
            ciudad = self.get_ciudad_por_id(c.get("ciudad_id")) if hasattr(self, "get_ciudad_por_id") else None
            salida.append({"id": c["id"], "slug": c.get("slug"), "nombre": c.get("nombre"),
                           "ciudad_id": c.get("ciudad_id"), "plan": c.get("plan"), "activo": c.get("activo", True),
                           "ciudad": (ciudad or {}).get("nombre"),
                           "grupo_atado": bool(c.get("_grupo_atado"))})
        return salida

    def integracion_registrar_evento(self, row):
        self._integ()["eventos"].append({"created_at": _ahora_iso(), **row})

    # ── idempotencia ─────────────────────────────────────────────────────────────────────────────────────
    def integracion_idem_reclamar(self, grupo_id, key, request_hash):
        idem = self._integ()["idem"]
        previa = idem.get((grupo_id, key))
        if previa is not None:
            creada = datetime.fromisoformat(previa["created_at"])
            ahora = datetime.now(timezone.utc)
            if ahora - creada > timedelta(days=7) or (previa["status"] == 0 and (ahora - creada).total_seconds() > 120):
                del idem[(grupo_id, key)]
            else:
                return {"nuevo": False, **previa}
        idem[(grupo_id, key)] = {"request_hash": request_hash, "status": 0, "response": None, "created_at": _ahora_iso()}
        return {"nuevo": True}

    def integracion_idem_cerrar(self, grupo_id, key, status, response):
        fila = self._integ()["idem"].get((grupo_id, key))
        if fila:
            fila.update({"status": status, "response": response})

    def integracion_idem_liberar(self, grupo_id, key):
        self._integ()["idem"].pop((grupo_id, key), None)

    def integracion_idem_purgar(self):
        return 0

    # ── publicaciones ────────────────────────────────────────────────────────────────────────────────────
    def _integ_bump(self, pub):
        """Equivale al trigger de la 0157: cada UPDATE mueve updated_at (monótono, para los tests)."""
        st = self._integ()
        st["seq"] += 1
        pub["updated_at"] = f"2026-10-01T00:00:00.{st['seq']:06d}+00:00"

    @staticmethod
    def _integ_clave(p):
        return (str(p.get("updated_at") or p.get("created_at") or ""), str(p.get("id")))

    def integracion_listar_publicaciones(self, comercio_ids, cursor, limite, estado):
        filas = [p for p in self.publicaciones if p.get("comercio_id") in set(comercio_ids)
                 and (estado is None or p.get("estado") == estado)]
        if cursor:
            filas = [p for p in filas if self._integ_clave(p) > (cursor[0], cursor[1])]
        return [dict(p) for p in sorted(filas, key=self._integ_clave)[:limite]]

    def integracion_get_publicacion(self, pub_id):
        p = self.get_publicacion(pub_id)
        return dict(p) if p else None

    def integracion_actualizar_publicacion_si(self, pub_id, patch, condiciones):
        p = self.get_publicacion(pub_id)
        if not p or any(p.get(col) != val for col, val in condiciones.items()):
            return None
        p.update(patch)
        self._integ_bump(p)
        return dict(p)

    # ── difusión ─────────────────────────────────────────────────────────────────────────────────────────
    def difusion_de_publicacion(self, publicacion_id):
        return [dict(f) for f in self.difusion if f["publicacion_id"] == publicacion_id]

    def get_difusion_fila(self, fila_id):
        return next((dict(f) for f in self.difusion if f["id"] == fila_id), None)

    def reclamar_difusion(self, fila_id, desde="pendiente"):
        for f in self.difusion:
            if f["id"] == fila_id and f["estado"] == desde:
                f["estado"] = "incierto"
                return True
        return False

    def actualizar_difusion(self, fila_id, patch):
        for f in self.difusion:
            if f["id"] == fila_id:
                f.update(patch)
