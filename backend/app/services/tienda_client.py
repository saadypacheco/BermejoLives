"""Cliente del ecommerce (marketplace multi-vendedor).

Contrato: docs/contrato-integracion.md. Si `settings.tienda_api_url` está vacío,
el cliente trabaja en modo **STUB** (dev/tests): devuelve datos simulados sin red.
Cuando se configure la URL real, usa httpx contra `/api/servicio/*` con `X-API-Key`.
"""
import uuid

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# Categorías por defecto en modo stub, hasta que el ecommerce real exponga las suyas.
_STUB_CATEGORIAS = [
    {"slug": "ropa", "nombre": "Ropa"},
    {"slug": "calzado", "nombre": "Calzado"},
    {"slug": "electronica", "nombre": "Electrónica"},
    {"slug": "alimentos", "nombre": "Alimentos y bebidas"},
    {"slug": "hogar", "nombre": "Hogar"},
    {"slug": "ferreteria", "nombre": "Ferretería"},
    {"slug": "belleza", "nombre": "Belleza y cuidado"},
    {"slug": "otros", "nombre": "Otros"},
]


class TiendaClient:
    def __init__(self):
        self._url = settings.tienda_api_url.rstrip("/") if settings.tienda_api_url else ""
        self._stub = not self._url
        self._headers = {"X-API-Key": settings.tienda_api_secret}

    @property
    def stub(self) -> bool:
        return self._stub

    def _u(self, path: str) -> str:
        return f"{self._url}{path}"

    def list_categorias(self) -> list[dict]:
        if self._stub:
            return list(_STUB_CATEGORIAS)
        r = httpx.get(self._u("/api/servicio/categorias"), headers=self._headers, timeout=15)
        r.raise_for_status()
        return r.json()

    def upsert_vendedor(self, vendedor_id: str, data: dict) -> dict:
        if self._stub:
            return {"id": vendedor_id, **data}
        r = httpx.put(self._u(f"/api/servicio/vendedores/{vendedor_id}"),
                      json=data, headers=self._headers, timeout=15)
        r.raise_for_status()
        return r.json()

    def crear_producto(self, vendedor_id: str, data: dict, fotos: list[bytes]) -> dict:
        """data = {nombre, precio, moneda, categoria_slug, descripcion?}. Devuelve {producto_id, url}."""
        if self._stub:
            pid = uuid.uuid4().hex[:8]
            return {"producto_id": pid, "url": f"/v/{data.get('slug', vendedor_id)}#p{pid}"}
        files = [("fotos", (f"foto{i}.jpg", b, "image/jpeg")) for i, b in enumerate(fotos)]
        r = httpx.post(self._u(f"/api/servicio/vendedores/{vendedor_id}/productos"),
                       data=data, files=files or None, headers=self._headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def update_producto(self, producto_id: str, patch: dict) -> dict:
        if self._stub:
            return {"producto_id": producto_id, **patch}
        r = httpx.put(self._u(f"/api/servicio/productos/{producto_id}"),
                      json=patch, headers=self._headers, timeout=15)
        r.raise_for_status()
        return r.json()

    def delete_producto(self, producto_id: str) -> None:
        if self._stub:
            return
        r = httpx.delete(self._u(f"/api/servicio/productos/{producto_id}"),
                         headers=self._headers, timeout=15)
        r.raise_for_status()

    def list_productos(self, vendedor_id: str) -> list[dict]:
        if self._stub:
            return []
        r = httpx.get(self._u(f"/api/servicio/vendedores/{vendedor_id}/productos"),
                      headers=self._headers, timeout=15)
        r.raise_for_status()
        return r.json()


def get_tienda_client() -> TiendaClient:
    return TiendaClient()
