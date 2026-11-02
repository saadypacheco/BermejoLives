"""Repositorio del contenido para redes y el cuidado de suscriptores (migración 0181).

Aparte de `repository.py` (4.000 líneas, un `FakeRepo` de 2.600) a propósito: menos choques de
merge con otros trabajos sobre `main`, y el módulo se prueba solo con su propio fake
(`tests/content_fakes.py`). Incluye las lecturas de tablas viejas que este módulo necesita
(comercios con su plan, ofertas aprobadas, pagos recientes, conteo de leads por tipo y origen).

Todas las tablas nuevas son SÓLO de `service_role`: el front nunca las lee por PostgREST.
`comercios` se lee SIEMPRE por columnas (regla 11 de AGENTS.md): nunca `select("*")`, y nunca la
columna del código del comercio.
"""
from __future__ import annotations

from typing import Protocol

import structlog

from app.db.session import get_supabase

logger = structlog.get_logger()

#: Estados de una pieza que todavía cuentan como «viva» (no `skipped` ni `failed`).
PIEZA_VIVA = ("queued", "rendering", "ready_for_review", "approved", "published")
#: Los que consumen la cuota del ciclo (§3.3).
PIEZA_CONSUME_CUOTA = PIEZA_VIVA

#: La ficha de un comercio para este módulo: sólo columnas, con rubro y ciudad embebidos.
COLS_FICHA = (
    "id, slug, nombre, whatsapp, direccion, calle, horario, subcategoria, lat, lng, "
    "portada_url, portada_thumb_url, plan, plan_cortesia, paga_hasta, suspendido, activo, baja_motivo, "
    "ciudad_id, rubro_id, monedas_aceptadas, instagram_url, facebook_url, tiktok_url, sitio_web, "
    "canal_wa_url, created_at, "
    "rubros!comercios_rubro_id_fkey(nombre, slug), ciudades(nombre, slug, departamento)"
)


class ContentConflict(Exception):
    """Un índice único frenó el insert (ya había una fila igual)."""


def es_duplicado(exc: Exception) -> bool:
    t = str(exc)
    return "23505" in t or "duplicate key" in t.lower()


class ContentRepo(Protocol):
    # ── autorización para redes ──
    def add_consent(self, row: dict) -> dict: ...
    def list_consents(self, comercio_id: str, limit: int = 50) -> list[dict]: ...
    def current_consents(self, comercio_ids: list[str] | None = None) -> dict[str, dict]: ...
    # ── banco de fotos ──
    def insert_asset(self, row: dict) -> dict: ...
    def get_asset(self, asset_id: str) -> dict | None: ...
    def find_asset(self, comercio_id: str, sha256: str | None = None,
                   source_sha256: str | None = None) -> dict | None: ...
    def list_assets(self, comercio_ids: list[str], only_active: bool = True) -> list[dict]: ...
    def update_asset(self, asset_id: str, patch: dict) -> dict | None: ...
    def assets_to_purge(self, cutoff_iso: str, limit: int = 200) -> list[dict]: ...
    def bump_asset_use(self, asset_ids: list[str], now_iso: str) -> None: ...
    def recent_uploaded_comercios(self, uploaded_by: str, limit: int = 5) -> list[str]: ...
    # ── piezas ──
    def insert_piece(self, row: dict) -> dict | None: ...
    def get_piece(self, piece_id: str) -> dict | None: ...
    def get_piece_by_token(self, token: str) -> dict | None: ...
    def update_piece(self, piece_id: str, patch: dict, if_status: str | list[str] | None = None) -> dict | None: ...
    def list_pieces(self, statuses: list[str] | None = None, date_from: str | None = None,
                    date_to: str | None = None, comercio_id: str | None = None,
                    limit: int = 300) -> list[dict]: ...
    def list_queued_due(self, now_iso: str, limit: int = 5) -> list[dict]: ...
    def stuck_rendering(self, cutoff_iso: str) -> list[dict]: ...
    def count_pieces_by_status(self) -> dict[str, int]: ...
    def list_own_pieces_since(self, since: str) -> list[dict]: ...
    def weeks_planned_by_selector(self, since: str) -> set[str]: ...
    def pieces_to_purge(self, published_before_iso: str, dead_before_iso: str, limit: int = 200) -> list[dict]: ...
    # ── fuentes ──
    def insert_sources(self, rows: list[dict]) -> list[dict]: ...
    def list_sources(self, piece_id: str, only_active: bool = True) -> list[dict]: ...
    def deactivate_source(self, piece_id: str, position: int) -> None: ...
    def recent_sources(self, since: str) -> list[dict]: ...
    def piece_ids_by_source_comercio(self, comercio_id: str) -> list[str]: ...
    def piece_ids_by_source_asset(self, asset_id: str) -> list[str]: ...
    # ── posteos por red ──
    def insert_posts(self, rows: list[dict]) -> list[dict]: ...
    def list_posts(self, piece_ids: list[str]) -> list[dict]: ...
    def get_post(self, post_id: str) -> dict | None: ...
    def update_post(self, post_id: str, patch: dict, if_status: str | list[str] | None = None) -> dict | None: ...
    def claim_post(self, post_id: str, actor: str, now_iso: str, expired_before_iso: str) -> dict | None: ...
    def release_expired_claims(self, cutoff_iso: str) -> int: ...
    # ── cuidado de suscriptores ──
    def insert_task(self, row: dict) -> dict | None: ...
    def get_task(self, task_id: str) -> dict | None: ...
    def update_task(self, task_id: str, patch: dict, if_status: str | None = None) -> dict | None: ...
    def list_tasks(self, status: str | None = "open", due_from: str | None = None, due_to: str | None = None,
                   comercio_id: str | None = None, kinds: list[str] | None = None,
                   limit: int = 500) -> list[dict]: ...
    def get_profile(self, comercio_id: str) -> dict | None: ...
    def list_profiles(self, comercio_ids: list[str]) -> dict[str, dict]: ...
    def upsert_profile(self, comercio_id: str, patch: dict) -> dict: ...
    def insert_report(self, row: dict) -> dict | None: ...
    def get_report(self, comercio_id: str, period_start: str) -> dict | None: ...
    def last_report(self, comercio_id: str) -> dict | None: ...
    def get_reports(self, ids: list[str]) -> dict[str, dict]: ...
    # ── lecturas de tablas viejas ──
    def get_comercio_ficha(self, comercio_id: str) -> dict | None: ...
    def list_comercios_activos(self, ciudad_id: str | None = None, planes: list[str] | None = None,
                               ids: list[str] | None = None) -> list[dict]: ...
    def search_comercios(self, q: str | None, ciudad_id: str | None, limit: int = 20) -> list[dict]: ...
    def list_ciudades(self) -> list[dict]: ...
    def get_plan(self, slug: str) -> dict | None: ...
    def list_planes(self) -> list[dict]: ...
    def gallery_photos(self, comercio_ids: list[str]) -> list[dict]: ...
    def list_offers(self, since_iso: str, comercio_id: str | None = None) -> list[dict]: ...
    def count_offers_since(self, comercio_id: str, desde_iso: str) -> int: ...
    def payments_since(self, since_iso: str) -> list[dict]: ...
    def count_payments_before(self, comercio_id: str, before_iso: str) -> int: ...
    def count_leads(self, comercio_id: str, desde_iso: str, tipo: str | None = None,
                    origen_prefixes: list[str] | None = None) -> int: ...


def _lista(v) -> list:
    return list(v) if isinstance(v, (list, tuple, set)) else [v]


class SupabaseContentRepo:
    """Implementación real sobre Supabase self-hosted (PostgREST)."""

    def __init__(self, client=None):
        self._client = client

    @property
    def _db(self):
        """El cliente, recién cuando se necesita: un endpoint que sólo recibe este repo por inyección
        (el alta de campo sin autorización de redes) no toca la base ni exige la configuración."""
        if self._client is None:
            self._client = get_supabase()
        return self._client

    # ── autorización ─────────────────────────────────────────────────────────
    def add_consent(self, row: dict) -> dict:
        return self._db.table("comercio_social_consents").insert(row).execute().data[0]

    def list_consents(self, comercio_id: str, limit: int = 50) -> list[dict]:
        res = (self._db.table("comercio_social_consents").select("*").eq("comercio_id", comercio_id)
               .eq("activo", True).order("recorded_at", desc=True).limit(limit).execute())
        return res.data or []

    def current_consents(self, comercio_ids: list[str] | None = None) -> dict[str, dict]:
        """La vigente de cada comercio (la vista toma la última fila activa de la bitácora)."""
        out: dict[str, dict] = {}
        if comercio_ids is not None:
            for i in range(0, len(comercio_ids), 150):
                res = (self._db.table("comercio_social_consent_current").select("*")
                       .in_("comercio_id", comercio_ids[i:i + 150]).execute())
                out.update({r["comercio_id"]: r for r in (res.data or [])})
            return out
        desde = 0
        while True:
            res = (self._db.table("comercio_social_consent_current").select("*")
                   .range(desde, desde + 999).execute())
            lote = res.data or []
            out.update({r["comercio_id"]: r for r in lote})
            if len(lote) < 1000:
                return out
            desde += 1000

    # ── banco ────────────────────────────────────────────────────────────────
    def insert_asset(self, row: dict) -> dict:
        try:
            return self._db.table("content_assets").insert(row).execute().data[0]
        except Exception as exc:  # noqa: BLE001
            if es_duplicado(exc):
                raise ContentConflict(str(exc)) from exc
            raise

    def get_asset(self, asset_id: str) -> dict | None:
        res = self._db.table("content_assets").select("*").eq("id", asset_id).limit(1).execute()
        return res.data[0] if res.data else None

    def find_asset(self, comercio_id: str, sha256: str | None = None,
                   source_sha256: str | None = None) -> dict | None:
        for col, val in (("sha256", sha256), ("source_sha256", source_sha256)):
            if not val:
                continue
            res = (self._db.table("content_assets").select("*").eq("comercio_id", comercio_id)
                   .eq(col, val).eq("activo", True).limit(1).execute())
            if res.data:
                return res.data[0]
        return None

    def list_assets(self, comercio_ids: list[str], only_active: bool = True) -> list[dict]:
        out: list[dict] = []
        for i in range(0, len(comercio_ids), 100):
            q = self._db.table("content_assets").select("*").in_("comercio_id", comercio_ids[i:i + 100])
            if only_active:
                q = q.eq("activo", True)
            out += q.order("created_at", desc=True).limit(2000).execute().data or []
        return out

    def update_asset(self, asset_id: str, patch: dict) -> dict | None:
        res = self._db.table("content_assets").update(patch).eq("id", asset_id).execute()
        return res.data[0] if res.data else None

    def assets_to_purge(self, cutoff_iso: str, limit: int = 200) -> list[dict]:
        res = (self._db.table("content_assets").select("id, file_path, thumb_path")
               .eq("activo", False).is_("file_purged_at", "null").lte("deactivated_at", cutoff_iso)
               .limit(limit).execute())
        return res.data or []

    def bump_asset_use(self, asset_ids: list[str], now_iso: str) -> None:
        for aid in asset_ids:
            a = self.get_asset(aid)
            if a:
                self._db.table("content_assets").update(
                    {"use_count": int(a.get("use_count") or 0) + 1, "last_used_at": now_iso}).eq("id", aid).execute()

    def recent_uploaded_comercios(self, uploaded_by: str, limit: int = 5) -> list[str]:
        """Los últimos comercios donde subió esta persona (sin repetir, el más reciente primero)."""
        res = (self._db.table("content_assets").select("comercio_id, created_at").eq("uploaded_by", uploaded_by)
               .eq("activo", True).order("created_at", desc=True).limit(200).execute())
        out: list[str] = []
        for r in res.data or []:
            if r["comercio_id"] not in out:
                out.append(r["comercio_id"])
            if len(out) >= limit:
                break
        return out

    # ── piezas ───────────────────────────────────────────────────────────────
    def insert_piece(self, row: dict) -> dict | None:
        """None si el lugar del calendario ya tiene una pieza viva (índice `uq_content_pieces_slot`)."""
        try:
            return self._db.table("content_pieces").insert(row).execute().data[0]
        except Exception as exc:  # noqa: BLE001
            if es_duplicado(exc):
                return None
            raise

    def get_piece(self, piece_id: str) -> dict | None:
        res = self._db.table("content_pieces").select("*").eq("id", piece_id).eq("activo", True).limit(1).execute()
        return res.data[0] if res.data else None

    def get_piece_by_token(self, token: str) -> dict | None:
        res = (self._db.table("content_pieces").select("*").eq("share_token", token).eq("activo", True)
               .limit(1).execute())
        return res.data[0] if res.data else None

    def update_piece(self, piece_id: str, patch: dict, if_status: str | list[str] | None = None) -> dict | None:
        """UPDATE condicional: devuelve la fila nueva, o None si no estaba en el estado pedido."""
        q = self._db.table("content_pieces").update(patch).eq("id", piece_id)
        if if_status is not None:
            q = q.in_("status", _lista(if_status))
        res = q.execute()
        return res.data[0] if res.data else None

    def list_pieces(self, statuses: list[str] | None = None, date_from: str | None = None,
                    date_to: str | None = None, comercio_id: str | None = None,
                    limit: int = 300) -> list[dict]:
        q = self._db.table("content_pieces").select("*").eq("activo", True)
        if statuses:
            q = q.in_("status", statuses)
        if date_from:
            q = q.gte("scheduled_for", date_from)
        if date_to:
            q = q.lte("scheduled_for", date_to)
        if comercio_id:
            q = q.eq("comercio_id", comercio_id)
        return q.order("scheduled_for").order("created_at").limit(limit).execute().data or []

    def list_queued_due(self, now_iso: str, limit: int = 5) -> list[dict]:
        res = (self._db.table("content_pieces").select("id, scheduled_for").eq("activo", True)
               .eq("status", "queued").lte("render_next_at", now_iso)
               .order("scheduled_for").order("created_at").limit(limit).execute())
        return res.data or []

    def stuck_rendering(self, cutoff_iso: str) -> list[dict]:
        res = (self._db.table("content_pieces").select("*").eq("status", "rendering")
               .lt("render_started_at", cutoff_iso).limit(20).execute())
        return res.data or []

    def count_pieces_by_status(self) -> dict[str, int]:
        out = {}
        for st in ("queued", "rendering", "ready_for_review", "failed"):
            res = (self._db.table("content_pieces").select("id", count="exact").eq("activo", True)
                   .eq("status", st).limit(1).execute())
            out[st] = res.count or 0
        return out

    def list_own_pieces_since(self, since: str) -> list[dict]:
        """Piezas propias de un comercio, vivas, desde `since` (para cuota y separación)."""
        res = (self._db.table("content_pieces")
               .select("id, comercio_id, scheduled_for, status, counts_for_quota, quota_cycle_start")
               .eq("activo", True).not_.is_("comercio_id", "null").in_("status", list(PIEZA_VIVA))
               .gte("scheduled_for", since).limit(5000).execute())
        return res.data or []

    def weeks_planned_by_selector(self, since: str) -> set[str]:
        res = (self._db.table("content_pieces").select("week_start").eq("activo", True)
               .eq("created_by", "selector").gte("week_start", since).limit(1000).execute())
        return {r["week_start"] for r in (res.data or [])}

    def pieces_to_purge(self, published_before_iso: str, dead_before_iso: str, limit: int = 200) -> list[dict]:
        """Piezas con archivos que ya pasaron su retención (§4.4)."""
        cols = "id, status, video_path, cover_path"
        a = (self._db.table("content_pieces").select(cols).not_.is_("video_path", "null")
             .is_("files_purged_at", "null").eq("status", "published")
             .lte("published_at", published_before_iso).limit(limit).execute().data or [])
        b = (self._db.table("content_pieces").select(cols).not_.is_("video_path", "null")
             .is_("files_purged_at", "null").in_("status", ["skipped", "failed"])
             .lte("updated_at", dead_before_iso).limit(limit).execute().data or [])
        return a + b

    # ── fuentes ──────────────────────────────────────────────────────────────
    def insert_sources(self, rows: list[dict]) -> list[dict]:
        if not rows:
            return []
        return self._db.table("content_piece_sources").insert(rows).execute().data or []

    def list_sources(self, piece_id: str, only_active: bool = True) -> list[dict]:
        q = self._db.table("content_piece_sources").select("*").eq("piece_id", piece_id)
        if only_active:
            q = q.eq("activo", True)
        return q.order("position").limit(50).execute().data or []

    def deactivate_source(self, piece_id: str, position: int) -> None:
        (self._db.table("content_piece_sources").update({"activo": False})
         .eq("piece_id", piece_id).eq("position", position).execute())

    def recent_sources(self, since: str) -> list[dict]:
        """Las fuentes de piezas vivas desde `since`, con el pilar de la pieza."""
        piezas = (self._db.table("content_pieces").select("id, pillar").eq("activo", True)
                  .in_("status", list(PIEZA_VIVA)).gte("scheduled_for", since).limit(2000).execute().data or [])
        pilar = {p["id"]: p["pillar"] for p in piezas}
        out: list[dict] = []
        ids = list(pilar)
        for i in range(0, len(ids), 100):
            res = (self._db.table("content_piece_sources")
                   .select("piece_id, source_type, source_id, file_ref, comercio_id")
                   .in_("piece_id", ids[i:i + 100]).eq("activo", True).execute())
            out += [{**r, "pillar": pilar.get(r["piece_id"])} for r in (res.data or [])]
        return out

    def piece_ids_by_source_comercio(self, comercio_id: str) -> list[str]:
        """Las piezas que tienen una fuente ACTIVA de este comercio (propias y compilados de ofertas)."""
        res = (self._db.table("content_piece_sources").select("piece_id").eq("comercio_id", comercio_id)
               .eq("activo", True).limit(2000).execute())
        return sorted({r["piece_id"] for r in (res.data or [])})

    def piece_ids_by_source_asset(self, asset_id: str) -> list[str]:
        """Las piezas que usan esta foto del banco como fuente activa."""
        res = (self._db.table("content_piece_sources").select("piece_id").eq("source_type", "asset")
               .eq("source_id", asset_id).eq("activo", True).limit(500).execute())
        return sorted({r["piece_id"] for r in (res.data or [])})

    # ── posteos ──────────────────────────────────────────────────────────────
    def insert_posts(self, rows: list[dict]) -> list[dict]:
        """Una fila por red. Si ya existía (`unique (piece_id, network)`), no se duplica."""
        out = []
        for r in rows:
            try:
                out += self._db.table("content_posts").insert(r).execute().data or []
            except Exception as exc:  # noqa: BLE001
                if not es_duplicado(exc):
                    raise
        return out

    def list_posts(self, piece_ids: list[str]) -> list[dict]:
        out: list[dict] = []
        for i in range(0, len(piece_ids), 100):
            res = (self._db.table("content_posts").select("*").in_("piece_id", piece_ids[i:i + 100])
                   .eq("activo", True).order("created_at").execute())
            out += res.data or []
        return out

    def get_post(self, post_id: str) -> dict | None:
        res = self._db.table("content_posts").select("*").eq("id", post_id).eq("activo", True).limit(1).execute()
        return res.data[0] if res.data else None

    def update_post(self, post_id: str, patch: dict, if_status: str | list[str] | None = None) -> dict | None:
        q = self._db.table("content_posts").update(patch).eq("id", post_id)
        if if_status is not None:
            q = q.in_("status", _lista(if_status))
        res = q.execute()
        return res.data[0] if res.data else None

    def claim_post(self, post_id: str, actor: str, now_iso: str, expired_before_iso: str) -> dict | None:
        """Reclamo ATÓMICO: la condición va en el UPDATE, así de dos reclamos simultáneos sólo uno gana.
        Se puede reclamar si está pendiente, si el reclamo anterior venció o si ya lo tenía este mismo actor."""
        propio = '"' + actor.replace("\\", "\\\\").replace('"', '\\"') + '"'
        q = (self._db.table("content_posts")
             .update({"status": "claimed", "claimed_by": actor, "claimed_at": now_iso}).eq("id", post_id)
             .or_(f'status.eq.pending,and(status.eq.claimed,claimed_at.lt."{expired_before_iso}"),'
                  f'and(status.eq.claimed,claimed_by.eq.{propio})'))
        res = q.execute()
        return res.data[0] if res.data else None

    def release_expired_claims(self, cutoff_iso: str) -> int:
        res = (self._db.table("content_posts")
               .update({"status": "pending", "claimed_by": None, "claimed_at": None})
               .eq("status", "claimed").lt("claimed_at", cutoff_iso).execute())
        return len(res.data or [])

    # ── cuidado ──────────────────────────────────────────────────────────────
    def insert_task(self, row: dict) -> dict | None:
        """None si ya existe la tarea `(comercio_id, kind, due_on)`."""
        try:
            return self._db.table("subscriber_tasks").insert(row).execute().data[0]
        except Exception as exc:  # noqa: BLE001
            if es_duplicado(exc):
                return None
            raise

    def get_task(self, task_id: str) -> dict | None:
        res = self._db.table("subscriber_tasks").select("*").eq("id", task_id).eq("activo", True).limit(1).execute()
        return res.data[0] if res.data else None

    def update_task(self, task_id: str, patch: dict, if_status: str | None = None) -> dict | None:
        q = self._db.table("subscriber_tasks").update(patch).eq("id", task_id)
        if if_status is not None:
            q = q.eq("status", if_status)
        res = q.execute()
        return res.data[0] if res.data else None

    def list_tasks(self, status: str | None = "open", due_from: str | None = None, due_to: str | None = None,
                   comercio_id: str | None = None, kinds: list[str] | None = None,
                   limit: int = 500) -> list[dict]:
        q = self._db.table("subscriber_tasks").select("*").eq("activo", True)
        if status:
            q = q.eq("status", status)
        if due_from:
            q = q.gte("due_on", due_from)
        if due_to:
            q = q.lte("due_on", due_to)
        if comercio_id:
            q = q.eq("comercio_id", comercio_id)
        if kinds:
            q = q.in_("kind", kinds)
        return q.order("due_on").order("created_at").limit(limit).execute().data or []

    def get_profile(self, comercio_id: str) -> dict | None:
        res = (self._db.table("subscriber_profiles").select("*").eq("comercio_id", comercio_id)
               .eq("activo", True).limit(1).execute())
        return res.data[0] if res.data else None

    def list_profiles(self, comercio_ids: list[str]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for i in range(0, len(comercio_ids), 150):
            res = (self._db.table("subscriber_profiles").select("*")
                   .in_("comercio_id", comercio_ids[i:i + 150]).eq("activo", True).execute())
            out.update({r["comercio_id"]: r for r in (res.data or [])})
        return out

    def upsert_profile(self, comercio_id: str, patch: dict) -> dict:
        res = (self._db.table("subscriber_profiles")
               .upsert({**patch, "comercio_id": comercio_id, "activo": True}, on_conflict="comercio_id").execute())
        return res.data[0]

    def insert_report(self, row: dict) -> dict | None:
        try:
            return self._db.table("subscriber_reports").insert(row).execute().data[0]
        except Exception as exc:  # noqa: BLE001
            if es_duplicado(exc):
                return None
            raise

    def get_report(self, comercio_id: str, period_start: str) -> dict | None:
        res = (self._db.table("subscriber_reports").select("*").eq("comercio_id", comercio_id)
               .eq("period_start", period_start).eq("activo", True).limit(1).execute())
        return res.data[0] if res.data else None

    def last_report(self, comercio_id: str) -> dict | None:
        res = (self._db.table("subscriber_reports").select("*").eq("comercio_id", comercio_id)
               .eq("activo", True).order("period_start", desc=True).limit(1).execute())
        return res.data[0] if res.data else None

    def get_reports(self, ids: list[str]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for i in range(0, len(ids), 100):
            res = self._db.table("subscriber_reports").select("*").in_("id", ids[i:i + 100]).execute()
            out.update({r["id"]: r for r in (res.data or [])})
        return out

    # ── tablas viejas ────────────────────────────────────────────────────────
    def get_comercio_ficha(self, comercio_id: str) -> dict | None:
        res = self._db.table("comercios").select(COLS_FICHA).eq("id", comercio_id).limit(1).execute()
        return res.data[0] if res.data else None

    def list_comercios_activos(self, ciudad_id: str | None = None, planes: list[str] | None = None,
                               ids: list[str] | None = None) -> list[dict]:
        """Comercios ACTIVOS, paginados; filtrables por ciudad, por plan o por una lista de ids."""
        if ids is not None:
            out: list[dict] = []
            for i in range(0, len(ids), 100):
                out += (self._db.table("comercios").select(COLS_FICHA).eq("activo", True)
                        .in_("id", ids[i:i + 100]).execute().data or [])
            return out
        items: list[dict] = []
        pagina = 1000
        while True:
            q = self._db.table("comercios").select(COLS_FICHA).eq("activo", True)
            if ciudad_id:
                q = q.eq("ciudad_id", ciudad_id)
            if planes is not None:
                q = q.in_("plan", planes)
            lote = q.order("nombre").order("id").range(len(items), len(items) + pagina - 1).execute().data or []
            items.extend(lote)
            if len(lote) < pagina or len(items) >= 20000:
                return items

    def search_comercios(self, q: str | None, ciudad_id: str | None, limit: int = 20) -> list[dict]:
        from app.db.repository import limpiar_busqueda

        sel = self._db.table("comercios").select(COLS_FICHA).eq("activo", True)
        if ciudad_id:
            sel = sel.eq("ciudad_id", ciudad_id)
        texto = limpiar_busqueda(q)
        if texto:
            sel = sel.ilike("nombre", f"%{texto}%")
        return sel.order("nombre").limit(limit).execute().data or []

    def list_ciudades(self) -> list[dict]:
        res = self._db.table("ciudades").select("id, slug, nombre, departamento").order("orden").limit(200).execute()
        return res.data or []

    def get_plan(self, slug: str) -> dict | None:
        res = self._db.table("planes").select("*").eq("slug", slug).limit(1).execute()
        return res.data[0] if res.data else None

    def list_planes(self) -> list[dict]:
        return self._db.table("planes").select("*").order("orden").limit(100).execute().data or []

    def gallery_photos(self, comercio_ids: list[str]) -> list[dict]:
        out: list[dict] = []
        for i in range(0, len(comercio_ids), 100):
            res = (self._db.table("comercio_fotos").select("id, comercio_id, url, thumb_url, created_at")
                   .in_("comercio_id", comercio_ids[i:i + 100]).order("created_at", desc=True)
                   .limit(3000).execute())
            out += res.data or []
        return out

    def list_offers(self, since_iso: str, comercio_id: str | None = None) -> list[dict]:
        """Ofertas aprobadas con foto y precio desde `since_iso` (por `approved_at`)."""
        q = (self._db.table("publicaciones")
             .select("id, comercio_id, titulo, descripcion, precio, moneda, imagen_url, approved_at")
             .eq("tipo", "oferta").eq("estado", "aprobado").eq("activo", True)
             .not_.is_("imagen_url", "null").not_.is_("precio", "null").gte("approved_at", since_iso))
        if comercio_id:
            q = q.eq("comercio_id", comercio_id)
        return q.order("approved_at", desc=True).limit(1000).execute().data or []

    def count_offers_since(self, comercio_id: str, desde_iso: str) -> int:
        """Ofertas aprobadas del comercio desde esa fecha (sólo `tipo = 'oferta'`: una novedad no cuenta)."""
        res = (self._db.table("publicaciones").select("id", count="exact").eq("comercio_id", comercio_id)
               .eq("tipo", "oferta").eq("estado", "aprobado").eq("activo", True)
               .gte("created_at", desde_iso).limit(1).execute())
        return res.count or 0

    def payments_since(self, since_iso: str) -> list[dict]:
        res = (self._db.table("pagos").select("id, comercio_id, created_at, periodo_hasta")
               .eq("estado", "confirmado").gte("created_at", since_iso).order("created_at").limit(2000).execute())
        return res.data or []

    def count_payments_before(self, comercio_id: str, before_iso: str) -> int:
        res = (self._db.table("pagos").select("id", count="exact").eq("comercio_id", comercio_id)
               .eq("estado", "confirmado").lt("created_at", before_iso).limit(1).execute())
        return res.count or 0

    def count_leads(self, comercio_id: str, desde_iso: str, tipo: str | None = None,
                    origen_prefixes: list[str] | None = None) -> int:
        """Cuenta leads con `count="exact"` (no `list_leads_by_comercio`, que corta en 500)."""
        q = (self._db.table("leads").select("id", count="exact").eq("comercio_id", comercio_id)
             .gte("created_at", desde_iso))
        if tipo:
            q = q.eq("tipo", tipo)
        if origen_prefixes:
            q = q.or_(",".join(f"origen.like.{p}*" for p in origen_prefixes))
        return q.limit(1).execute().count or 0


def get_content_repo() -> ContentRepo:
    return SupabaseContentRepo()
