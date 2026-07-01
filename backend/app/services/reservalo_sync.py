"""Cliente para el dashboard admin unificado: lee datos agregados de Reservalo
(reservas, consultas de soporte, clientes) vía /api/admin-sync/*.

Si `settings.tienda_api_url` o `settings.admin_sync_secret` están vacíos,
trabaja en modo STUB (devuelve vacío en vez de fallar) — el mismo criterio
que usa TiendaClient para no romper dev/tests sin Reservalo levantado.
"""
import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class ReservaloSyncClient:
    def __init__(self):
        self._url = settings.tienda_api_url.rstrip("/") if settings.tienda_api_url else ""
        self._secret = settings.admin_sync_secret
        self._stub = not (self._url and self._secret)
        self._headers = {"X-API-Key": self._secret}

    def _u(self, path: str) -> str:
        return f"{self._url}{path}"

    def resumen(self) -> dict | None:
        if self._stub:
            return None
        try:
            r = httpx.get(self._u("/api/admin-sync/resumen"), headers=self._headers, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("reservalo_sync.resumen.error", error=str(exc))
            return None

    def list_consultas(self, estado: str | None = None) -> list[dict]:
        if self._stub:
            return []
        try:
            params = {"estado": estado} if estado else {}
            r = httpx.get(self._u("/api/admin-sync/consultas"), headers=self._headers, params=params, timeout=15)
            r.raise_for_status()
            return r.json().get("items", [])
        except Exception as exc:  # noqa: BLE001
            logger.warning("reservalo_sync.consultas.error", error=str(exc))
            return []

    def responder_consulta(self, consulta_id: int, respuesta: str, respondida_por: str) -> dict | None:
        if self._stub:
            return None
        r = httpx.patch(
            self._u(f"/api/admin-sync/consultas/{consulta_id}"),
            json={"respuesta": respuesta, "respondida_por": respondida_por},
            headers=self._headers, timeout=15,
        )
        r.raise_for_status()
        return r.json()


def get_reservalo_sync_client() -> ReservaloSyncClient:
    return ReservaloSyncClient()
