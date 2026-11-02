"""`FakeContentRepo`: el repositorio de contenido para redes en memoria.

Las tablas nuevas (0181) viven en dicts propios. Las lecturas de tablas viejas (comercios,
planes, galería, ofertas, pagos, leads) las toma del `FakeRepo` de `conftest.py` que se le pasa
al construirlo: así un test siembra `repo.comercios`, `repo.publicaciones`, etc. como siempre y el
módulo de contenido los ve.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.db.content_repository import ContentConflict

#: Piezas por ciclo de cada plan, como las deja la 0181.
CUOTAS = {"gratis": 0, "publica": 2, "destacado": 4, "pro": 4, "empleado_ia": 4, "premium": 4}
DEPARTAMENTOS = {"bermejo": "Tarija", "santa-cruz": "Santa Cruz"}
VIVA = ("queued", "rendering", "ready_for_review", "approved", "published")


def _lista(v):
    return list(v) if isinstance(v, (list, tuple, set)) else [v]


class FakeContentRepo:
    def __init__(self, base):
        self.base = base
        for slug, cuota in CUOTAS.items():
            if slug in base.planes:
                base.planes[slug].setdefault("social_pieces_per_month", cuota)
        self.consents: list[dict] = []
        self.assets: dict[str, dict] = {}
        self.pieces: dict[str, dict] = {}
        self.sources: list[dict] = []
        self.posts: dict[str, dict] = {}
        self.tasks: dict[str, dict] = {}
        self.profiles: dict[str, dict] = {}
        self.reports: dict[str, dict] = {}
        self._t = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # ── utilidades ──
    def _tic(self) -> str:
        self._t += timedelta(seconds=1)
        return self._t.isoformat()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── autorización ──
    def add_consent(self, row):
        fila = {"id": str(uuid.uuid4()), "activo": True, "recorded_at": self._tic(), **row}
        self.consents.append(fila)
        return fila

    def list_consents(self, comercio_id, limit=50):
        filas = [c for c in self.consents if c["comercio_id"] == comercio_id and c.get("activo", True)]
        return sorted(filas, key=lambda c: (c["recorded_at"], c["id"]), reverse=True)[:limit]

    def current_consents(self, comercio_ids=None):
        out = {}
        for c in sorted(self.consents, key=lambda c: (c["recorded_at"], c["id"])):
            if c.get("activo", True) and (comercio_ids is None or c["comercio_id"] in comercio_ids):
                out[c["comercio_id"]] = c
        return out

    # ── banco ──
    def insert_asset(self, row):
        for a in self.assets.values():
            if a["comercio_id"] == row["comercio_id"] and a.get("activo", True):
                if a["sha256"] == row["sha256"] or (row.get("source_sha256") and a.get("source_sha256") == row["source_sha256"]):
                    raise ContentConflict("duplicate key")
        fila = {"id": str(uuid.uuid4()), "activo": True, "use_count": 0, "last_used_at": None, "gallery_photo_id": None,
                "usable_for_social": True, "has_people": False, "people_ok": None, "created_at": self._tic(),
                "file_purged_at": None, **row}
        self.assets[fila["id"]] = fila
        return fila

    def get_asset(self, asset_id):
        return self.assets.get(asset_id)

    def find_asset(self, comercio_id, sha256=None, source_sha256=None):
        for a in self.assets.values():
            if a["comercio_id"] != comercio_id or not a.get("activo", True):
                continue
            if (sha256 and a["sha256"] == sha256) or (source_sha256 and a.get("source_sha256") == source_sha256):
                return a
        return None

    def list_assets(self, comercio_ids, only_active=True):
        filas = [a for a in self.assets.values() if a["comercio_id"] in comercio_ids and (a.get("activo", True) or not only_active)]
        return sorted(filas, key=lambda a: a["created_at"], reverse=True)

    def update_asset(self, asset_id, patch):
        a = self.assets.get(asset_id)
        if a:
            a.update(patch)
        return a

    def assets_to_purge(self, cutoff_iso, limit=200):
        return [a for a in self.assets.values() if not a.get("activo", True) and not a.get("file_purged_at")
                and (a.get("deactivated_at") or "9") <= cutoff_iso][:limit]

    def bump_asset_use(self, asset_ids, now_iso):
        for i in asset_ids:
            a = self.assets.get(i)
            if a:
                a["use_count"] = int(a.get("use_count") or 0) + 1
                a["last_used_at"] = now_iso

    def recent_uploaded_comercios(self, uploaded_by, limit=5):
        out = []
        for a in sorted(self.assets.values(), key=lambda a: a["created_at"], reverse=True):
            if a.get("uploaded_by") == uploaded_by and a.get("activo", True) and a["comercio_id"] not in out:
                out.append(a["comercio_id"])
        return out[:limit]

    # ── piezas ──
    def insert_piece(self, row):
        for p in self.pieces.values():
            if (p.get("activo", True) and p["scheduled_for"] == row["scheduled_for"] and p["pillar"] == row["pillar"]
                    and p["status"] not in ("skipped", "failed") and row.get("status", "queued") not in ("skipped", "failed")):
                return None
        fila = {"id": str(uuid.uuid4()), "activo": True, "status": "queued", "render_attempts": 0, "render_next_at": self._now(),
                "caption_edited": False, "hashtags": [], "caption_checks": [], "created_at": self._tic(),
                "updated_at": self._now(), "files_purged_at": None, "video_path": None, "cover_path": None,
                "template_version": 1, **row}
        self.pieces[fila["id"]] = fila
        return fila

    def get_piece(self, piece_id):
        p = self.pieces.get(piece_id)
        return p if p and p.get("activo", True) else None

    def get_piece_by_token(self, token):
        return next((p for p in self.pieces.values() if p.get("share_token") == token and p.get("activo", True)), None)

    def update_piece(self, piece_id, patch, if_status=None):
        p = self.pieces.get(piece_id)
        if not p or (if_status is not None and p["status"] not in _lista(if_status)):
            return None
        p.update(patch)
        p["updated_at"] = self._now()
        return p

    def list_pieces(self, statuses=None, date_from=None, date_to=None, comercio_id=None, limit=300):
        filas = [p for p in self.pieces.values() if p.get("activo", True)]
        if statuses:
            filas = [p for p in filas if p["status"] in statuses]
        if date_from:
            filas = [p for p in filas if p["scheduled_for"] >= date_from]
        if date_to:
            filas = [p for p in filas if p["scheduled_for"] <= date_to]
        if comercio_id:
            filas = [p for p in filas if p.get("comercio_id") == comercio_id]
        return sorted(filas, key=lambda p: (p["scheduled_for"], p["created_at"]))[:limit]

    def list_published_with_video(self, ciudad_id=None, limit=100):
        filas = [p for p in self.pieces.values() if p.get("activo", True) and p["status"] == "published"
                 and p.get("video_path") and p.get("cover_path") and not p.get("files_purged_at")
                 and (not ciudad_id or p.get("ciudad_id") == ciudad_id)]
        return sorted(filas, key=lambda p: p.get("published_at") or "", reverse=True)[:limit]

    def list_queued_due(self, now_iso, limit=5):
        filas = [p for p in self.pieces.values() if p.get("activo", True) and p["status"] == "queued"
                 and p["render_next_at"] <= now_iso]
        return sorted(filas, key=lambda p: (p["scheduled_for"], p["created_at"]))[:limit]

    def stuck_rendering(self, cutoff_iso):
        return [p for p in self.pieces.values() if p["status"] == "rendering" and (p.get("render_started_at") or "9") < cutoff_iso]

    def count_pieces_by_status(self):
        out = {s: 0 for s in ("queued", "rendering", "ready_for_review", "failed")}
        for p in self.pieces.values():
            if p.get("activo", True) and p["status"] in out:
                out[p["status"]] += 1
        return out

    def list_own_pieces_since(self, since):
        return [{k: p.get(k) for k in ("id", "comercio_id", "scheduled_for", "status", "counts_for_quota", "quota_cycle_start")}
                for p in self.pieces.values() if p.get("activo", True) and p.get("comercio_id") and p["status"] in VIVA
                and p["scheduled_for"] >= since]

    def weeks_planned_by_selector(self, since):
        return {p["week_start"] for p in self.pieces.values()
                if p.get("activo", True) and p.get("created_by") == "selector" and p["week_start"] >= since}

    def pieces_to_purge(self, published_before_iso, dead_before_iso, limit=200):
        out = []
        for p in self.pieces.values():
            if not p.get("video_path") or p.get("files_purged_at"):
                continue
            if p["status"] == "published" and (p.get("published_at") or "9") <= published_before_iso:
                out.append(p)
            elif p["status"] in ("skipped", "failed") and (p.get("updated_at") or "9") <= dead_before_iso:
                out.append(p)
        return out[:limit]

    # ── fuentes ──
    def insert_sources(self, rows):
        out = []
        for r in rows:
            # `unique (piece_id, position)` de la 0181: cuenta también las fuentes inactivas.
            if any(s["piece_id"] == r["piece_id"] and s["position"] == r["position"] for s in self.sources):
                raise ContentConflict("duplicate key value violates unique constraint (piece_id, position)")
            fila = {"id": str(uuid.uuid4()), "activo": True, "created_at": self._tic(), **r}
            self.sources.append(fila)
            out.append(fila)
        return out

    def list_sources(self, piece_id, only_active=True):
        filas = [s for s in self.sources if s["piece_id"] == piece_id and (s.get("activo", True) or not only_active)]
        return sorted(filas, key=lambda s: s["position"])

    def deactivate_source(self, piece_id, position):
        for s in self.sources:
            if s["piece_id"] == piece_id and s["position"] == position:
                s["activo"] = False

    def recent_sources(self, since):
        out = []
        for s in self.sources:
            p = self.pieces.get(s["piece_id"])
            if s.get("activo", True) and p and p.get("activo", True) and p["status"] in VIVA and p["scheduled_for"] >= since:
                out.append({"piece_id": s["piece_id"], "source_type": s["source_type"], "source_id": s.get("source_id"),
                            "file_ref": s.get("file_ref"), "comercio_id": s.get("comercio_id"), "pillar": p["pillar"]})
        return out

    def piece_ids_by_source_comercio(self, comercio_id):
        return sorted({s["piece_id"] for s in self.sources if s.get("comercio_id") == comercio_id and s.get("activo", True)})

    def piece_ids_by_source_asset(self, asset_id):
        return sorted({s["piece_id"] for s in self.sources if s.get("source_type") == "asset"
                       and s.get("source_id") == asset_id and s.get("activo", True)})

    # ── posteos ──
    def insert_posts(self, rows):
        out = []
        for r in rows:
            if any(p["piece_id"] == r["piece_id"] and p["network"] == r["network"] for p in self.posts.values()):
                continue
            fila = {"id": str(uuid.uuid4()), "activo": True, "status": "pending", "claimed_by": None, "claimed_at": None,
                    "posted_by": None, "posted_at": None, "post_url": None, "posted_without_link": False,
                    "skip_reason": None, "created_at": self._tic(), **r}
            self.posts[fila["id"]] = fila
            out.append(fila)
        return out

    def list_posts(self, piece_ids):
        return sorted([p for p in self.posts.values() if p["piece_id"] in piece_ids and p.get("activo", True)],
                      key=lambda p: p["created_at"])

    def get_post(self, post_id):
        p = self.posts.get(post_id)
        return p if p and p.get("activo", True) else None

    def update_post(self, post_id, patch, if_status=None):
        p = self.posts.get(post_id)
        if not p or (if_status is not None and p["status"] not in _lista(if_status)):
            return None
        p.update(patch)
        return p

    def claim_post(self, post_id, actor, now_iso, expired_before_iso):
        """Reclamo atómico: la misma condición que el UPDATE real (pendiente, vencido o del mismo actor)."""
        p = self.posts.get(post_id)
        if not p:
            return None
        libre = (p["status"] == "pending"
                 or (p["status"] == "claimed" and (p.get("claimed_at") or "") < expired_before_iso)
                 or (p["status"] == "claimed" and p.get("claimed_by") == actor))
        if not libre:
            return None
        p.update({"status": "claimed", "claimed_by": actor, "claimed_at": now_iso})
        return p

    def release_expired_claims(self, cutoff_iso):
        n = 0
        for p in self.posts.values():
            if p["status"] == "claimed" and (p.get("claimed_at") or "9") < cutoff_iso:
                p.update({"status": "pending", "claimed_by": None, "claimed_at": None})
                n += 1
        return n

    # ── cuidado ──
    def insert_task(self, row):
        if any(t["comercio_id"] == row["comercio_id"] and t["kind"] == row["kind"] and t["due_on"] == row["due_on"]
               for t in self.tasks.values()):
            return None
        fila = {"id": str(uuid.uuid4()), "activo": True, "status": "open", "piece_id": None, "report_id": None,
                "sent_text": None, "outcome": None, "done_by": None, "done_at": None, "auto_closed": False,
                "note": None, "created_at": self._tic(), **row}
        self.tasks[fila["id"]] = fila
        return fila

    def get_task(self, task_id):
        t = self.tasks.get(task_id)
        return t if t and t.get("activo", True) else None

    def update_task(self, task_id, patch, if_status=None):
        t = self.tasks.get(task_id)
        if not t or (if_status is not None and t["status"] != if_status):
            return None
        t.update(patch)
        return t

    def list_tasks(self, status="open", due_from=None, due_to=None, comercio_id=None, kinds=None, limit=500):
        filas = [t for t in self.tasks.values() if t.get("activo", True)]
        if status:
            filas = [t for t in filas if t["status"] == status]
        if due_from:
            filas = [t for t in filas if t["due_on"] >= due_from]
        if due_to:
            filas = [t for t in filas if t["due_on"] <= due_to]
        if comercio_id:
            filas = [t for t in filas if t["comercio_id"] == comercio_id]
        if kinds:
            filas = [t for t in filas if t["kind"] in kinds]
        return sorted(filas, key=lambda t: (t["due_on"], t["created_at"]))[:limit]

    def get_profile(self, comercio_id):
        return self.profiles.get(comercio_id)

    def list_profiles(self, comercio_ids):
        return {i: self.profiles[i] for i in comercio_ids if i in self.profiles}

    def upsert_profile(self, comercio_id, patch):
        fila = self.profiles.setdefault(comercio_id, {"comercio_id": comercio_id, "activo": True})
        fila.update(patch)
        return fila

    def insert_report(self, row):
        if any(r["comercio_id"] == row["comercio_id"] and r["period_start"] == row["period_start"] for r in self.reports.values()):
            return None
        fila = {"id": str(uuid.uuid4()), "activo": True, "created_at": self._tic(), **row}
        self.reports[fila["id"]] = fila
        return fila

    def get_report(self, comercio_id, period_start):
        return next((r for r in self.reports.values() if r["comercio_id"] == comercio_id and r["period_start"] == period_start), None)

    def last_report(self, comercio_id):
        filas = [r for r in self.reports.values() if r["comercio_id"] == comercio_id]
        return max(filas, key=lambda r: r["period_start"], default=None)

    def get_reports(self, ids):
        return {i: self.reports[i] for i in ids if i in self.reports}

    # ── tablas viejas (salen del FakeRepo) ──
    def _ficha(self, c):
        ficha = dict(c)
        if "ciudades" not in ficha and ficha.get("ciudad_id"):
            ciudad = next((x for x in self.list_ciudades() if x["id"] == ficha["ciudad_id"]), None)
            if ciudad:
                ficha["ciudades"] = {k: ciudad[k] for k in ("nombre", "slug", "departamento")}
        return ficha

    def get_comercio_ficha(self, comercio_id):
        c = self.base.comercios.get(comercio_id)
        return self._ficha(c) if c else None

    def list_comercios_activos(self, ciudad_id=None, planes=None, ids=None):
        out = []
        for c in self.base.comercios.values():
            if c.get("activo", True) is False:
                continue
            if ciudad_id and c.get("ciudad_id") != ciudad_id:
                continue
            if planes is not None and (c.get("plan") or "gratis") not in planes:
                continue
            if ids is not None and c["id"] not in ids:
                continue
            out.append(self._ficha(c))
        return sorted(out, key=lambda c: ((c.get("nombre") or "").lower(), c["id"]))

    def search_comercios(self, q, ciudad_id, limit=20):
        texto = (q or "").strip().lower()
        filas = [c for c in self.list_comercios_activos(ciudad_id) if not texto or texto in (c.get("nombre") or "").lower()]
        return filas[:limit]

    def list_ciudades(self):
        return [{"id": c["id"], "slug": c["slug"], "nombre": c["nombre"],
                 "departamento": DEPARTAMENTOS.get(c["slug"], "Bolivia")} for c in self.base.list_ciudades()]

    def get_plan(self, slug):
        return self.base.planes.get(slug)

    def list_planes(self):
        return sorted(self.base.planes.values(), key=lambda p: p.get("orden", 0))

    def gallery_photos(self, comercio_ids):
        filas = [f for f in self.base.comercio_fotos if f["comercio_id"] in comercio_ids]
        return sorted(filas, key=lambda f: str(f.get("created_at") or ""), reverse=True)

    def list_offers(self, since_iso, comercio_id=None):
        out = []
        for p in self.base.publicaciones:
            if (p.get("tipo") == "oferta" and p.get("estado") == "aprobado" and p.get("activo", True)
                    and p.get("imagen_url") and p.get("precio") is not None and (p.get("approved_at") or "") >= since_iso
                    and (comercio_id is None or p.get("comercio_id") == comercio_id)):
                out.append(p)
        return sorted(out, key=lambda p: p.get("approved_at") or "", reverse=True)

    def count_offers_since(self, comercio_id, desde_iso):
        return sum(1 for p in self.base.publicaciones
                   if p.get("comercio_id") == comercio_id and p.get("tipo") == "oferta" and p.get("estado") == "aprobado"
                   and p.get("activo", True) and str(p.get("created_at") or "9999") >= desde_iso)

    def payments_since(self, since_iso):
        return sorted([p for p in self.base.pagos.values() if p.get("estado", "confirmado") == "confirmado"
                       and (p.get("created_at") or "") >= since_iso], key=lambda p: p["created_at"])

    def count_payments_before(self, comercio_id, before_iso):
        return sum(1 for p in self.base.pagos.values() if p["comercio_id"] == comercio_id
                   and p.get("estado", "confirmado") == "confirmado" and (p.get("created_at") or "") < before_iso)

    def count_leads(self, comercio_id, desde_iso, tipo=None, origen_prefixes=None):
        n = 0
        for l in self.base.leads:
            if l.get("comercio_id") != comercio_id or (l.get("created_at") or "") < desde_iso:
                continue
            if tipo and l.get("tipo") != tipo:
                continue
            if origen_prefixes and not any((l.get("origen") or "").startswith(p) for p in origen_prefixes):
                continue
            n += 1
        return n
