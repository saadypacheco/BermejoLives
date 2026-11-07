"""CA-4: ninguna tabla de medición guarda IP, User-Agent, cookie ni query string.

Dos pruebas:
1. Columnas permitidas: las de `visitas`, `site_events` y `leads` según las migraciones (create table + cada
   `alter table ... add column`) tienen que estar en una lista cerrada. Si alguien suma una columna, este test lo
   obliga a decidir si es un dato personal.
2. Volcado: se manda un pedido de prueba con una IP, un User-Agent y un `?q=` reconocibles, a todos los endpoints de
   medición, y se busca cada uno en TODO lo que quedó guardado (y en los logs).
"""
import json
import re
from pathlib import Path

import pytest
from structlog.testing import capture_logs

from app.services import site_metrics

RAIZ = Path(__file__).resolve().parents[2]
MIGRACIONES = RAIZ / "supabase/migrations"

PERMITIDAS = {
    "visitas": {"id", "dia", "ruta", "sesion", "origen", "referido", "ciudad_slug", "primera", "created_at",
                "device", "standalone"},
    "site_events": {"id", "day", "event", "detail", "path", "session", "city_slug", "created_at"},
    "leads": {"id", "comercio_id", "tipo", "created_at", "busqueda_id", "origen", "respondio", "respondio_en",
              "respondio_por", "sesion", "detalle"},
}
PROHIBIDO = re.compile(r"(^|_)(ip|ips|ua|user_agent|useragent|agent|cookie|cookies|query|qs|querystring|url|host|addr|address|fingerprint)($|_)")

IP = "203.0.113.77"
UA = "Mozilla/5.0 (Secreto/9.9) AgenteDePrueba-QWERTY"
Q = "zapatos-secretos-12345"


def _sin_comentarios(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def _columnas(tabla: str) -> set[str]:
    """Columnas de `tabla` según las migraciones: create table + `add column` (`alter table` de una o varias columnas)."""
    cols: set[str] = set()
    for f in sorted(MIGRACIONES.glob("*.sql")):
        sql = _sin_comentarios(f.read_text(encoding="utf-8"))
        for m in re.finditer(rf"create table(?: if not exists)? (?:public\.)?{tabla}\s*\((.*?)\n\);", sql, re.S | re.I):
            for linea in m.group(1).splitlines():
                linea = linea.strip()
                if linea and not re.match(r"(primary|unique|constraint|check|foreign)\b", linea, re.I):
                    cols.add(linea.split()[0].strip('",'))
        for alt in re.finditer(rf"alter\s+table\s+(?:if exists\s+)?(?:only\s+)?(?:public\.)?{tabla}\b(.*?);", sql, re.S | re.I):
            cols.update(re.findall(r"\badd\s+column\s+(?:if not exists\s+)?(\w+)", alt.group(1), re.I))
    return cols


@pytest.mark.parametrize("tabla", sorted(PERMITIDAS))
def test_CA4_las_columnas_de_las_tablas_de_medicion_son_las_permitidas(tabla):
    reales = _columnas(tabla)
    assert reales, f"no encontré {tabla} en las migraciones"
    assert reales <= PERMITIDAS[tabla], f"{tabla} tiene columnas nuevas sin revisar: {sorted(reales - PERMITIDAS[tabla])}"
    assert not [c for c in reales if PROHIBIDO.search(c)], f"{tabla}: columna con pinta de dato personal"


def test_CA4_las_filas_que_arma_el_backend_no_traen_columnas_fuera_de_lista(client, repo):
    """Lo que el backend inserta es un subconjunto de las columnas permitidas (si no, PostgREST rechazaría el insert)."""
    client.auto_volcar = False
    h = {"content-type": "text/plain", "user-agent": "Mozilla/5.0 Chrome/120"}
    client.post("/collect", content=json.dumps({"t": "pv", "path": "/", "session": "sesion-abcdef", "device": "mobile", "first": True}), headers=h)
    client.post("/collect", content=json.dumps({"t": "ev", "path": "/", "session": "sesion-abcdef", "event": "share", "detail": "copy"}), headers=h)
    client.post("/lead", json={"comercio_id": "00000000-0000-4000-8000-0000000000c1", "tipo": "red", "detalle": "tiktok", "sesion": "sesion-abcdef"})
    client.post("/lead", json={"comercio_id": "00000000-0000-4000-8000-0000000000c1", "tipo": "vista", "sesion": "sesion-abcdef"})
    lote = site_metrics.medidor.tomar_buffer()
    for tabla, filas in lote.items():
        assert filas
        for fila in filas:
            assert set(fila) <= PERMITIDAS[tabla], (tabla, set(fila) - PERMITIDAS[tabla])


def test_CA4_ni_la_ip_ni_el_ua_ni_el_query_quedan_guardados_ni_logueados(client, repo):
    comercio = "00000000-0000-4000-8000-0000000000c1"
    repo.seed_comercio(id=comercio, slug="rustico", nombre="Rústico", whatsapp="591700001")
    cab = {"user-agent": UA, "x-forwarded-for": IP, "origin": "http://localhost:3000", "referer": f"http://localhost:3000/buscar?q={Q}",
           "cookie": "sid=COOKIE-SECRETA"}
    with capture_logs() as logs:
        client.post("/collect", content=json.dumps({"t": "pv", "path": f"/buscar?q={Q}#x", "session": "sesion-abcdef", "device": "mobile",
                                                    "first": True, "referrer": f"https://www.google.com/search?q={Q}"}),
                    headers={**cab, "content-type": "text/plain"})
        client.post("/collect", content=json.dumps({"t": "ev", "path": f"/?q={Q}", "session": "sesion-abcdef", "event": "share", "detail": "copy"}),
                    headers={**cab, "content-type": "text/plain"})
        client.post("/visita", json={"ruta": f"/buscar?q={Q}", "sesion": "sesion-vieja01", "referido": f"https://google.com/?q={Q}"}, headers=cab)
        client.post("/lead", json={"comercio_id": comercio, "tipo": "whatsapp", "sesion": "sesion-abcdef"}, headers=cab)
        client.post("/lead", json={"comercio_id": comercio, "tipo": "vista", "sesion": "sesion-abcdef"}, headers=cab)
        client.post("/busquedas/log", json={"query": "pan"}, headers=cab)
        client.post("/csp-report", content=json.dumps({"csp-report": {"blocked-uri": f"https://x.example/?q={Q}",
                                                                     "violated-directive": "img-src"}}), headers=cab)
        client.post("/collect", content=json.dumps({"t": "pv", "path": "/", "session": "sesion-abcdef"}), headers={**cab, "user-agent": "Googlebot"})
    assert repo.visitas and repo.site_events and repo.leads and repo.busquedas
    volcado = json.dumps({"visitas": repo.visitas, "site_events": repo.site_events, "leads": repo.leads,
                          "busquedas": repo.busquedas, "bc": repo.busqueda_comercios}, default=str)
    for secreto in (IP, "QWERTY", "Secreto/9.9", "AgenteDePrueba", Q, "COOKIE-SECRETA", "?q="):
        assert secreto not in volcado, f"quedó guardado: {secreto}"
    assert not any(secreto in json.dumps(logs, default=str) for secreto in (IP, "QWERTY", "COOKIE-SECRETA", Q))
    # la ruta se guardó, pero limpia
    assert {v["ruta"] for v in repo.visitas} == {"/buscar"}
    # y el referido, sólo el host
    assert {v["referido"] for v in repo.visitas} == {"google.com"}


def test_la_ip_no_esta_en_la_deduplicacion_ni_en_los_techos(client):
    """El límite por minuto guarda la IP en memoria hasta que cambia la ventana (como cualquier limitador); la
    deduplicación y los techos del día usan un hash con la sal del día."""
    client.auto_volcar = False
    client.post("/lead", json={"comercio_id": "00000000-0000-4000-8000-0000000000c1", "tipo": "vista", "sesion": "sesion-abcdef"},
                headers={"x-forwarded-for": IP, "user-agent": "Mozilla/5.0 Chrome/120"})
    m = site_metrics.medidor
    assert m._techos and IP not in repr(m._techos) and IP not in repr(m._vistas) and IP not in repr(m._contactos)
    assert IP not in repr(m._buffer)
