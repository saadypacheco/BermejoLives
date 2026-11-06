"""La parte de la medición (0193) del FakeRepo: lo mismo que hacen las funciones SQL, sobre listas en memoria.

`insert_site_rows` es lo que recibe el volcado del buffer; `site_metrics_summary`, `comercio_origins`,
`comercio_lead_counts` y `purge_site_metrics` imitan el contrato de las RPC de la 0193.
"""
from __future__ import annotations

import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone

_BO = timezone(timedelta(hours=-4))
_CONTACTOS_EMBUDO = ("whatsapp", "telefono", "reserva")


def _dia_de(ts) -> str | None:
    """La fecha en hora de Bolivia de un `created_at` ISO."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(_BO).date().isoformat()
    except ValueError:
        return str(ts)[:10]


class FakeSiteMetricsMixin:
    def _init_site_metrics(self):
        self.site_events: list[dict] = []
        self.insert_site_rows_falla = False          # para probar que un volcado fallido no rompe nada
        self.lotes_volcados: list[tuple[str, int]] = []

    # -- escritura (lo que vuelca el buffer) ---------------------------------------------
    def insert_site_rows(self, tabla, filas):
        if self.insert_site_rows_falla:
            raise RuntimeError("base caída")
        if tabla not in ("visitas", "site_events", "leads"):
            raise ValueError(tabla)
        self.lotes_volcados.append((tabla, len(filas)))
        ahora = datetime.now(timezone.utc).isoformat()
        for f in filas:
            if tabla == "leads":
                # En la base los NULL son NULL; en el fake, una clave ausente es lo mismo y los tests viejos lo miran así.
                fila = {"id": self._id("lead"), "created_at": ahora, **{k: v for k, v in f.items() if v is not None}}
                self.leads.append(fila)
            elif tabla == "visitas":
                self.visitas.append({"id": self._id("vis"), "created_at": ahora, **f})
            else:
                self.site_events.append({"id": self._id("evt"), "created_at": ahora, **f})

    def last_visit_at(self):
        return max((v.get("created_at") for v in self.visitas if v.get("created_at")), default=None)

    def purge_site_metrics(self, meses):
        if meses is None or meses < 13:
            raise RuntimeError("retención mínima: 13 meses")
        corte = (datetime.now(_BO).date() - timedelta(days=int(meses * 30.4375))).isoformat()
        antes = len(self.visitas) + len(self.site_events)
        self.visitas = [v for v in self.visitas if str(v.get("dia", "9999")) >= corte]
        self.site_events = [e for e in self.site_events if str(e.get("day", "9999")) >= corte]
        return antes - len(self.visitas) - len(self.site_events)

    # -- lectura (el contrato de las RPC) -------------------------------------------------
    def site_metrics_summary(self, desde, hasta, ciudad=None):
        def en_rango(d):
            return d is None or desde <= str(d) <= hasta

        v = [x for x in self.visitas if en_rango(x.get("dia")) and (not ciudad or x.get("ciudad_slug") == ciudad)]
        ev = [x for x in self.site_events if en_rango(x.get("day")) and (not ciudad or x.get("city_slug") == ciudad)]
        ls = [x for x in self.leads if en_rango(_dia_de(x.get("created_at")))]
        primeras = [x for x in v if x.get("primera")]

        por_dia: dict[str, dict] = {}
        d0, d1 = date.fromisoformat(desde), date.fromisoformat(hasta)
        for i in range((d1 - d0).days + 1):
            dia = (d0 + timedelta(days=i)).isoformat()
            por_dia[dia] = {"dia": dia, "visitas": 0, "personas": 0}
        for x in v:
            fila = por_dia.setdefault(str(x.get("dia", hasta)), {"dia": str(x.get("dia", hasta)), "visitas": 0, "personas": 0})
            fila["visitas"] += 1
            fila["personas"] += 1 if x.get("primera") else 0

        sesiones = {x["sesion"] for x in v}
        con_ficha = {x["sesion"] for x in v if str(x.get("ruta", "")).startswith("/comercios/")}
        con_contacto = {x["sesion"] for x in ls if x.get("sesion") in sesiones and x.get("tipo") in _CONTACTOS_EMBUDO}
        con_ia = [x for x in v if x.get("origen") or x.get("referido")]

        grupos: dict[tuple, dict] = {}
        rutas: Counter = Counter()
        for x in con_ia:
            g = grupos.setdefault((x.get("origen"), x.get("referido")), {"n": 0, "ses": set(), "fichas": 0})
            g["n"] += 1
            g["ses"].add(x["sesion"])
            g["fichas"] += 1 if str(x.get("ruta", "")).startswith("/comercios/") else 0
            rutas[(x.get("origen"), x.get("referido"), x.get("ruta"))] += 1

        return {
            "totals": {"pageviews": len(v), "sessions": len(sesiones), "first_pages": len(primeras)},
            "by_day": list(por_dia.values()),
            "top_paths": [{"ruta": r, "n": n} for r, n in Counter(x["ruta"] for x in v).most_common(15)],
            "referrers_raw": [{"referido": r, "origen": o, "n": n}
                              for (r, o), n in Counter((x.get("referido"), x.get("origen")) for x in primeras).most_common(300)],
            "origins": [{"origen": o, "n": n} for o, n in Counter(x["origen"] for x in v if x.get("origen")).most_common(50)],
            "devices": [{"device": d, "n": n} for d, n in Counter(x.get("device") or "unknown" for x in primeras).most_common()],
            "standalone_share": round(sum(1 for x in primeras if x.get("standalone")) / len(primeras), 4) if primeras else 0,
            "events": [{"event": e, "detail": d, "n": n}
                       for (e, d), n in Counter((x["event"], x.get("detail", "")) for x in ev).most_common(200)],
            "funnel": {"sessions": len(sesiones), "sessions_with_ficha": len(con_ficha), "sessions_with_contact": len(con_contacto)},
            "leads_by_type": dict(Counter(x.get("tipo") or "otro" for x in ls)),
            "ai_groups": [{"origen": o, "referido": r, "n": g["n"], "people": len(g["ses"]), "fichas": g["fichas"]}
                          for (o, r), g in grupos.items()],
            "ai_routes": [{"origen": o, "referido": r, "ruta": ru, "n": n} for (o, r, ru), n in rutas.items()],
        }

    def comercio_origins(self, comercio_id, desde):
        c = self.comercios.get(comercio_id) or {}
        slug = c.get("slug")
        if not slug:
            return []
        cont = Counter((x.get("origen"), x.get("referido")) for x in self.visitas
                       if x.get("ruta") == f"/comercios/{slug}" and x.get("primera") and str(x.get("dia", "9999")) >= desde)
        return [{"origen": o, "referido": r, "n": n} for (o, r), n in cont.most_common(100)]

    def comercio_lead_counts(self, comercio_id, dias=30):
        ahora = datetime.now(timezone.utc)

        def desde(d):
            return ahora - timedelta(days=d)

        def de_este(x, d):
            if x.get("comercio_id") != comercio_id:
                return False
            ts = x.get("created_at")
            try:
                return datetime.fromisoformat(str(ts).replace("Z", "+00:00")) >= desde(d)
            except ValueError:
                return True

        mios = [x for x in self.leads if de_este(x, dias)]
        mios7 = [x for x in self.leads if de_este(x, min(7, dias))]
        return {
            "por_tipo": dict(Counter(x.get("tipo") or "otro" for x in mios)),
            "por_tipo_7d": dict(Counter(x.get("tipo") or "otro" for x in mios7)),
            "redes": dict(Counter(x.get("detalle") or "otra" for x in mios if x.get("tipo") == "red")),
        }


def id_uuid() -> str:
    return str(uuid.uuid4())
