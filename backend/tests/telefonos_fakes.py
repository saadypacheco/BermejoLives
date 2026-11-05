"""Un repositorio de teléfonos en memoria, apoyado en el mismo FakeRepo de los comercios (como `FakeContentRepo`)."""
from __future__ import annotations

from datetime import datetime, timezone


class FakeTelefonosRepo:
    def __init__(self, base):
        self.base = base
        self.detectados: dict[str, dict] = {}
        self.escaneadas: dict[tuple[str, str], dict] = {}
        self.falla_registro = False                   # para probar que un fallo de la base no frena la tanda
        self._n = 0

    # ── lecturas de tablas viejas ──
    def list_ciudades(self):
        return [{"id": c["id"], "slug": c["slug"], "nombre": c["nombre"], "departamento": "Tarija"}
                for c in self.base.list_ciudades()]

    def get_comercio_min(self, comercio_id):
        c = self.base.comercios.get(comercio_id)
        if not c:
            return None
        return {"id": c["id"], "slug": c.get("slug"), "nombre": c.get("nombre"), "whatsapp": c.get("whatsapp"),
                "telefono": c.get("telefono"), "activo": c.get("activo", True), "ciudad_id": c.get("ciudad_id")}

    # ── el worker ──
    def portadas_sin_escanear(self, motor, limit=20, ciudad_id=None):
        out = []
        for c in self.base.comercios.values():
            url = c.get("portada_url")
            if not c.get("activo", True) or not url:
                continue
            if ciudad_id and c.get("ciudad_id") != ciudad_id:
                continue
            visto = any((url, m) in self.escaneadas and not self.escaneadas[(url, m)].get("error")
                        for m in (motor, "gemini-relevamiento"))
            if visto:
                continue
            out.append({"comercio_id": c["id"], "portada_url": url, "whatsapp": c.get("whatsapp"),
                        "telefono": c.get("telefono"), "ciudad_id": c.get("ciudad_id")})
        out.sort(key=lambda f: bool((f["whatsapp"] or "").strip()))      # sin WhatsApp primero (el orden es estable)
        return out[:limit]

    def registrar_escaneada(self, foto_url, motor, comercio_id, numeros, error=None):
        if self.falla_registro:
            raise RuntimeError("base caída")
        self.escaneadas[(foto_url, motor)] = {"foto_url": foto_url, "motor": motor, "comercio_id": comercio_id,
                                              "numeros": numeros, "error": error}

    def insert_detectados(self, rows):
        creadas = []
        for r in rows:
            if any(d["comercio_id"] == r["comercio_id"] and d["numero"] == r["numero"]
                   for d in self.detectados.values()):
                continue                              # on conflict do nothing
            self._n += 1
            fila = {"id": f"tel-{self._n}", "compartido": False, "activo": True, "estado": "pendiente",
                    "revisado_por": None, "revisado_at": None,
                    "created_at": datetime.now(timezone.utc).isoformat(), **r}
            self.detectados[fila["id"]] = fila
            creadas.append(dict(fila))
        return creadas

    def list_por_numero(self, numero):
        return [{"id": d["id"], "comercio_id": d["comercio_id"]} for d in self.detectados.values()
                if d["numero"] == numero and d["activo"]]

    def marcar_compartido(self, numero):
        for d in self.detectados.values():
            if d["numero"] == numero and d["activo"]:
                d["compartido"] = True

    # ── el panel ──
    def _comercio_activo(self, d):
        c = self.base.comercios.get(d["comercio_id"])
        return c if c and c.get("activo", True) else None

    def resumen(self, motor, ciudad_id=None):
        def ok(c):
            return c is not None and (not ciudad_id or c.get("ciudad_id") == ciudad_id)
        return {
            "escaneadas": len({k[0] for k, v in self.escaneadas.items() if ok(self.base.comercios.get(v["comercio_id"]))}),
            "pendientes_de_escanear": len(self.portadas_sin_escanear(motor, 10_000, ciudad_id)),
            "numeros": sum(1 for d in self.detectados.values() if d["activo"] and ok(self._comercio_activo(d))),
            "sin_whatsapp_con_numero": len({
                d["comercio_id"] for d in self.detectados.values()
                if d["activo"] and ok(self._comercio_activo(d)) and d["estado"] == "pendiente"
                and d["tipo"] == "celular" and not d["compartido"]
                and not (self.base.comercios[d["comercio_id"]].get("whatsapp") or "").strip()}),
        }

    def list_detectados(self, estado, ciudad_id, sin_whatsapp, limit, offset):
        filas = []
        for d in self.detectados.values():
            c = self._comercio_activo(d)
            if not d["activo"] or c is None:
                continue
            if estado and d["estado"] != estado:
                continue
            if ciudad_id and c.get("ciudad_id") != ciudad_id:
                continue
            if sin_whatsapp and c.get("whatsapp") is not None:
                continue
            ciu = next((x for x in self.list_ciudades() if x["id"] == c.get("ciudad_id")), None)
            filas.append({**d, "comercios": {
                "id": c["id"], "slug": c.get("slug"), "nombre": c.get("nombre"), "whatsapp": c.get("whatsapp"),
                "telefono": c.get("telefono"), "ciudad_id": c.get("ciudad_id"), "portada_url": c.get("portada_url"),
                "portada_thumb_url": c.get("portada_thumb_url"),
                "ciudades": {"nombre": ciu["nombre"], "slug": ciu["slug"]} if ciu else None}})
        filas.sort(key=lambda f: (f["created_at"], f["id"]), reverse=True)
        return filas[offset:offset + limit], len(filas)

    def contar_comercios_por_numero(self, numeros):
        out: dict[str, set] = {}
        for d in self.detectados.values():
            if d["numero"] in numeros and d["activo"]:
                out.setdefault(d["numero"], set()).add(d["comercio_id"])
        return {n: len(c) for n, c in out.items()}

    def get_detectado(self, detectado_id):
        d = self.detectados.get(detectado_id)
        return dict(d) if d else None

    def update_detectado(self, detectado_id, patch):
        d = self.detectados.get(detectado_id)
        if not d:
            return None
        d.update(patch)
        return dict(d)
