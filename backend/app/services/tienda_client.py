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

    def crear_producto(self, vendedor_id: str, data: dict, fotos_urls: list[str]) -> dict:
        """data = {nombre, precio, moneda, categoria_slug, descripcion?, slug?}.
        Las imágenes ya están alojadas en el disco de URUKU (fotos_urls). Se mandan
        como URLs (JSON), no como bytes. Devuelve {producto_id, url, imagen_url}."""
        if self._stub:
            pid = uuid.uuid4().hex[:8]
            return {"producto_id": pid, "url": f"/v/{data.get('slug', vendedor_id)}#p{pid}",
                    "imagen_url": fotos_urls[0] if fotos_urls else None}
        payload = {**data, "fotos_urls": fotos_urls}
        r = httpx.post(self._u(f"/api/servicio/vendedores/{vendedor_id}/productos"),
                       json=payload, headers=self._headers, timeout=30)
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
