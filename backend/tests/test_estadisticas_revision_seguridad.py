"""Revisión de seguridad de la medición v2 (docs/estadisticas-v2.md): una fila envenenada no tumba el lote, el
medidor no se puede apagar llenándolo, el voto de «no responde» es por red, y lo que llega de afuera se enmascara
o se sanea antes de guardarse o de llegar al log.

Hallazgos que cubre este archivo: 1 (FK y sustitutos sueltos, volcado que aísla), 2 (nada recorre el diccionario con
el lock, handlers fuera del event loop), 3 (techos y límites llenos), 4 (voto por red), 5 (límite lleno), 6 (log de
CSP), 7 (enmascarado), 8 (spam de referrer en «Mi comercio») y 9 (contactos sin `mapa`).
"""
import json
import threading
import uuid
from datetime import date

import pytest
from structlog.testing import capture_logs

from app.core import firmas
from app.core.ip import red_de_ip
from app.core.text import enmascarar_texto, limpiar_ref
from app.services import site_metrics
from app.services.site_metrics import Medidor, VentanaFija

C1 = "00000000-0000-4000-8000-0000000000c1"
C2 = "00000000-0000-4000-8000-0000000000c2"
SES = "sesion-abcdef12"
UA = "Mozilla/5.0 (Linux; Android 13; SM-A346M) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36"


@pytest.fixture(autouse=True)
def _reloj_quieto(monkeypatch):
    monkeypatch.setattr(site_metrics, "_reloj", lambda: 1_000_000.0)


@pytest.fixture
def cliente(client):
    client.auto_volcar = False
    return client


def _collect(client, cuerpo, **cabeceras):
    texto = cuerpo if isinstance(cuerpo, (str, bytes)) else json.dumps(cuerpo)
    return client.post("/collect", content=texto, headers={"content-type": "text/plain", "user-agent": UA, **cabeceras})


def _pv(**extra):
    return {"t": "pv", "path": "/buscar", "session": SES, "first": True, **extra}


def _lead(client, **cuerpo):
    return client.post("/lead", json={"comercio_id": C1, "tipo": "vista", **cuerpo}, headers={"user-agent": UA}).json()


# ═════════════════════════════════════ 1. una fila envenenada no tumba el lote
def test_un_comercio_inventado_no_toca_nada(cliente, repo):
    falso = str(uuid.uuid4())
    for tipo, extra in (("vista", {}), ("compartir", {"detalle": "copy"}), ("red", {"detalle": "instagram"}), ("whatsapp", {})):
        r = _lead(cliente, comercio_id=falso, tipo=tipo, sesion=SES, **extra)
        assert r == {"ok": False}
    m = site_metrics.medidor
    assert m.pendientes() == 0 and not m._vistas and not m._techos and not m._contactos and not m._pares_ip_comercio
    assert repo.leads == []


def test_un_comercio_dado_de_baja_tampoco(cliente, repo):
    repo.seed_comercio(id=str(uuid.uuid4()), slug="baja", nombre="Baja", activo=False)
    baja = next(i for i, c in repo.comercios.items() if c["slug"] == "baja")
    assert _lead(cliente, comercio_id=baja, sesion=SES) == {"ok": False}


def test_los_comercios_activos_se_cargan_una_vez_y_se_recargan_a_lo_sumo_una_vez_por_minuto(repo, monkeypatch):
    llamadas = []
    original = repo.ids_comercios_activos
    monkeypatch.setattr(repo, "ids_comercios_activos", lambda: (llamadas.append(1), original())[1])
    ahora = [1_000_000.0]
    monkeypatch.setattr(site_metrics, "_reloj", lambda: ahora[0])
    m = Medidor()
    assert m.comercio_activo(repo, C1) and m.comercio_activo(repo, C2) and len(llamadas) == 1       # cargó una vez
    nuevo = str(uuid.uuid4())
    for _ in range(50):                                                                              # ids al azar: sin recargar
        assert not m.comercio_activo(repo, str(uuid.uuid4()))
    assert len(llamadas) == 1
    repo.seed_comercio(id=nuevo, slug="nuevo", nombre="Nuevo")                                       # un comercio recién creado
    ahora[0] += 61                                                                                   # …se conoce a los 60 s
    assert m.comercio_activo(repo, nuevo) and len(llamadas) == 2
    ahora[0] += 301                                                                                  # y todo se refresca cada 5 min
    assert m.comercio_activo(repo, C1) and len(llamadas) == 3


def test_sin_base_no_se_acepta_ningun_comercio_y_no_se_martilla(repo, monkeypatch):
    llamadas = []

    def cae():
        llamadas.append(1)
        raise RuntimeError("base caída")
    monkeypatch.setattr(repo, "ids_comercios_activos", cae)
    m = Medidor()
    assert not any(m.comercio_activo(repo, str(uuid.uuid4())) for _ in range(30))
    assert len(llamadas) == 1                                                                         # un solo intento por ventana


def test_los_ids_se_paginan_con_el_cliente_de_postgrest_si_el_repo_no_tiene_el_metodo():
    class Res:
        def __init__(self, data):
            self.data = data

    class Tabla:
        def __init__(self):
            self.paginas = []

        def select(self, _c):
            return self

        def eq(self, *_a):
            return self

        def order(self, *_a):
            return self

        def range(self, a, b):
            self.paginas.append((a, b))
            return self

        def execute(self):
            a, _b = self.paginas[-1]
            n = 1000 if a == 0 else 3
            return Res([{"id": str(uuid.UUID(int=a + i + 1))} for i in range(n)])

    tabla = Tabla()

    class Repo:
        class _db:
            @staticmethod
            def table(_nombre):
                return tabla

    ids = site_metrics.ids_comercios_activos(Repo())
    assert len(ids) == 1003 and tabla.paginas == [(0, 999), (1000, 1999)]


def test_el_busqueda_id_sólo_vale_si_lo_emitió_el_backend(cliente, repo):
    ajeno = str(uuid.uuid4())
    repo.busquedas.append({"id": ajeno, "query": "x", "resultados": 0, "created_at": "2026-01-01T00:00:00+00:00"})   # existe, pero no lo emitimos
    r = _lead(cliente, tipo="whatsapp", busqueda_id=ajeno)
    assert r["ok"] and repo.leads[-1].get("busqueda_id") is None
    bid = cliente.post("/busquedas/log", json={"query": "zapatos", "resultados": 1}, headers={"user-agent": UA}).json()["busqueda_id"]
    r = _lead(cliente, tipo="whatsapp", busqueda_id=bid, sesion="sesion-otra01")
    assert r["ok"] and repo.leads[-1]["busqueda_id"] == bid


def test_el_busqueda_id_vence(monkeypatch):
    ahora = [1_000.0]
    monkeypatch.setattr(site_metrics, "_reloj", lambda: ahora[0])
    m = Medidor()
    bid = str(uuid.uuid4())
    m.recordar_busqueda(bid)
    assert m.busqueda_emitida(bid) == bid and m.busqueda_emitida(str(uuid.uuid4())) is None
    ahora[0] += site_metrics.TTL_BUSQUEDA_S + 1
    assert m.busqueda_emitida(bid) is None


def test_un_busqueda_id_inventado_en_una_vista_no_rompe_el_lote(cliente, repo):
    for i in range(5):
        _lead(cliente, sesion=f"sesion-{i:06d}", busqueda_id=str(uuid.uuid4()))
    guardadas = site_metrics.volcar(repo)
    assert guardadas == {"leads": 5} and all(l.get("busqueda_id") is None for l in repo.leads)


@pytest.mark.parametrize("ruta", ["/\ud800", "/ok/\udfff/x", "/a\ud83d"])
def test_una_ruta_con_sustitutos_sueltos_se_descarta(cliente, repo, ruta):
    assert site_metrics.normalizar_ruta(ruta) is None
    cuerpo = json.dumps(_pv(path=ruta))                 # json.dumps lo escapa como \ud800: el parser lo devuelve suelto
    assert _collect(cliente, cuerpo).status_code == 204
    assert site_metrics.medidor.pendientes() == 0
    assert site_metrics.normalizar_ruta("/ñandú/café") == "/ñandú/café"           # el UTF-8 válido sigue pasando


def test_un_lote_con_una_fila_mala_guarda_las_demas(repo):
    """Una fila que la base rechaza se aísla partiendo el lote a la mitad: las otras 499 se guardan."""
    for i in range(500):
        site_metrics.medidor.encolar("leads", {"comercio_id": C1, "tipo": "vista", "sesion": f"s{i}"})
    site_metrics.medidor.encolar("leads", {"comercio_id": str(uuid.uuid4()), "tipo": "vista", "sesion": "mala"})   # FK rota
    site_metrics.medidor.encolar("leads", {"comercio_id": C2, "tipo": "vista", "sesion": "buena-al-final"})
    with capture_logs() as logs:
        guardadas = site_metrics.volcar(repo)
    assert guardadas == {"leads": 501}
    assert len(repo.leads) == 501 and "mala" not in {l.get("sesion") for l in repo.leads}
    assert any(l["sesion"] == "buena-al-final" for l in repo.leads)
    fallos = [l for l in logs if l["event"] == "site_metrics_flush_failed"]
    assert len(fallos) == 1 and fallos[0]["filas"] == 1


def test_varias_filas_malas_en_el_mismo_lote(repo):
    for i in range(40):
        fila = {"comercio_id": str(uuid.uuid4()) if i in (3, 17, 38) else C1, "tipo": "vista", "sesion": f"s{i}"}
        site_metrics.medidor.encolar("leads", fila)
    assert site_metrics.volcar(repo) == {"leads": 37} and len(repo.leads) == 37


def test_con_la_base_caida_el_aislamiento_no_hace_cientos_de_pedidos(repo):
    repo.insert_site_rows_falla = True
    intentos = []
    original = repo.insert_site_rows
    repo.insert_site_rows = lambda t, f: (intentos.append(1), original(t, f))[1]
    for i in range(500):
        site_metrics.medidor.encolar("visitas", {"dia": "2026-11-06", "ruta": "/", "sesion": f"s{i}"})
    assert site_metrics.volcar(repo) == {"visitas": 0}
    assert len(intentos) <= site_metrics.MAX_INTENTOS_AISLAR
    assert site_metrics.medidor.pendientes() == 0                 # se descarta: sin reintento infinito


# ═════════════════════════════════════ 2. nada recorre todo con el lock; los handlers no frenan el event loop
def test_las_vistas_vencidas_salen_por_orden_sin_recorrer_todo(monkeypatch):
    m = Medidor()
    for i in range(1000):
        m.vista_repetida(f"s{i}", "c", ahora=float(i))
    # a los 30 minutos (1800 s) las primeras ya vencieron: la próxima vista las saca desde el principio
    m.vista_repetida("nueva", "c", ahora=1000.0 + site_metrics.VENTANA_VISTA_S - 500)
    assert ("s0", "c") not in m._vistas and ("s999", "c") in m._vistas
    assert next(iter(m._vistas)) == ("s501", "c")           # sólo salieron las vencidas, ninguna de más
    assert not hasattr(m, "_podar_vistas")


def test_con_el_tope_lleno_sale_la_mas_vieja(monkeypatch):
    monkeypatch.setattr(site_metrics, "MAX_DEDUP", 100)
    m = Medidor()
    for i in range(150):
        m.vista_repetida(f"s{i}", "c", ahora=0.0)
    assert len(m._vistas) == 100 and ("s0", "c") not in m._vistas and ("s149", "c") in m._vistas


def test_los_handlers_de_medicion_toman_el_lock_fuera_del_event_loop(cliente, monkeypatch):
    from app.api import collect as collect_api

    hilos = {}
    original_leer = collect_api._leer_cuerpo

    async def leer(request, tope):
        hilos["loop"] = threading.get_ident()
        return await original_leer(request, tope)

    limitar = site_metrics.medidor.limitar
    procesar = site_metrics.procesar_collect
    monkeypatch.setattr(collect_api, "_leer_cuerpo", leer)
    monkeypatch.setattr(site_metrics.medidor, "limitar", lambda *a, **k: (hilos.setdefault("limitar", threading.get_ident()), limitar(*a, **k))[1])
    monkeypatch.setattr(site_metrics, "procesar_collect", lambda raw, **k: (hilos.setdefault("procesar", threading.get_ident()), procesar(raw, **k))[1])
    assert _collect(cliente, _pv()).status_code == 204
    assert hilos["limitar"] != hilos["loop"] and hilos["procesar"] != hilos["loop"]


# ═════════════════════════════════════ 3. los topes llenos no apagan los techos
def test_el_techo_por_ip_sigue_cortando_con_el_diccionario_lleno(monkeypatch):
    monkeypatch.setattr(site_metrics, "MAX_DEDUP", 50)
    m = Medidor()
    hoy = date(2026, 11, 6)
    assert [m.pasa_techo(hoy, "203.0.113.9", "c1", "whatsapp", 3) for _ in range(5)] == [True, True, True, False, False]
    for i in range(500):                                       # otros 500 (IP, comercio): el diccionario se llena y rota
        m.pasa_techo(hoy, f"198.51.100.{i % 250}", f"c{i}", "vista", 30)
    assert len(m._techos) <= 50 and len(m._pares_ip_comercio) <= 50
    # Con LRU el atacante puede hacer salir SU entrada vieja, pero no «pasar de largo»: lo que llena cuenta desde 1.
    viejo = [m.pasa_techo(hoy, "192.0.2.1", "c-viejo", "whatsapp", 2) for _ in range(4)]
    assert viejo == [True, True, False, False]


def test_una_ip_no_puede_tocar_mas_de_200_comercios_distintos_por_dia():
    m = Medidor()
    hoy = date(2026, 11, 6)
    ok = [m.pasa_techo(hoy, "203.0.113.9", f"c{i}", "vista", 30) for i in range(210)]
    assert ok[:200] == [True] * 200 and ok[200:] == [False] * 10
    assert m.pasa_techo(hoy, "203.0.113.9", "c0", "vista", 30) is True            # uno de los 200 de siempre: sigue
    assert m.pasa_techo(hoy, "203.0.113.10", "c999", "vista", 30) is True         # otra IP no se ve afectada
    assert m.pasa_techo(date(2026, 11, 7), "203.0.113.9", "c500", "vista", 30) is True   # al día siguiente, de cero


def test_el_contador_de_comercios_por_ip_baja_cuando_sale_un_par_por_lru(monkeypatch):
    monkeypatch.setattr(site_metrics, "MAX_DEDUP", 10)
    m = Medidor()
    hoy = date(2026, 11, 6)
    for i in range(25):
        m.pasa_techo(hoy, "203.0.113.9", f"c{i}", "vista", 30)
    assert sum(m._comercios_por_ip.values()) == len(m._pares_ip_comercio) <= 10


def test_los_contactos_recordados_tienen_tope_y_olvidan_el_mas_viejo(monkeypatch):
    monkeypatch.setattr(site_metrics, "MAX_DEDUP", 5)
    m = Medidor()
    hoy = date(2026, 11, 6)
    for i in range(8):
        m.recordar_contacto(hoy, f"s{i}", "c", "whatsapp", f"id{i}")
    assert len(m._contactos) == 5
    assert m.contacto_previo(hoy, "s7", "c", "whatsapp") == (True, "id7")              # el último no se olvida
    assert m.contacto_previo(hoy, "s0", "c", "whatsapp") == (False, None)


# ═════════════════════════════════════ 4. «no responde»: un votante es una red, no una sesión
def test_el_votante_depende_sólo_de_la_red_de_la_ip():
    a = firmas.votante_de("203.0.113.9", "sesion-1")
    assert a == firmas.votante_de("203.0.113.9", "sesion-2") == firmas.votante_de("203.0.113.9", None)
    assert a != firmas.votante_de("203.0.113.10", "sesion-1")                           # IPv4: exacta
    assert firmas.votante_de("2800:cb0:1:2::1", "x") == firmas.votante_de("2800:cb0:1:ff:abcd::7", "y")     # mismo /56
    assert firmas.votante_de("2800:cb0:1:2::1", "x") != firmas.votante_de("2800:cb0:1:100::1", "x")         # otro /56
    assert firmas.votante_de("::ffff:203.0.113.9", "x") == a                            # IPv4 mapeada = IPv4
    assert len(a) == 32 and "203.0.113.9" not in a


def test_red_de_ip():
    assert red_de_ip("203.0.113.9") == "203.0.113.9"
    assert red_de_ip(" 203.0.113.9 ") == "203.0.113.9"
    assert red_de_ip("2800:cb0:1:2::1") == "2800:cb0:1::"
    assert red_de_ip("basura") == "invalid" and red_de_ip(None) == "invalid"


def _lead_con_voto(client, repo, comercio, sesion, ip):
    from datetime import datetime, timedelta, timezone
    r = client.post("/lead", json={"comercio_id": comercio, "tipo": "whatsapp", "sesion": sesion},
                    headers={"user-agent": UA, "x-forwarded-for": ip}).json()
    next(l for l in repo.leads if l["id"] == r["id"])["created_at"] = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    return r


def test_cinco_sesiones_de_una_misma_ip_son_un_solo_votante(client, repo):
    repo.seed_comercio(id=C1, slug="c1", nombre="C1")
    client.auto_volcar = False
    respuestas = []
    for i in range(5):
        lead = _lead_con_voto(client, repo, C1, f"sesion-vot{i:03d}", "203.0.113.9")
        respuestas.append(client.post(f"/lead/{lead['id']}/respondio",
                                      json={"respondio": False, "token": lead["token"], "sesion": f"sesion-vot{i:03d}"},
                                      headers={"x-forwarded-for": "203.0.113.9"}).json())
    assert "ya" not in respuestas[0] and all(r.get("ya") is True for r in respuestas[1:])      # sólo el primero cuenta
    assert len({l["respondio_por"] for l in repo.leads if l.get("respondio") is not None}) == 1
    assert sum(1 for l in repo.leads if l.get("respondio") is False) == 1


def test_tres_redes_distintas_si_son_tres_votantes(client, repo):
    repo.seed_comercio(id=C1, slug="c1", nombre="C1")
    client.auto_volcar = False
    for i, ip in enumerate(("203.0.113.1", "203.0.113.2", "2800:cb0:1:2::5")):
        lead = _lead_con_voto(client, repo, C1, f"sesion-red{i:03d}", ip)
        r = client.post(f"/lead/{lead['id']}/respondio", json={"respondio": False, "token": lead["token"], "sesion": f"sesion-red{i:03d}"},
                        headers={"x-forwarded-for": ip})
        assert r.status_code == 200 and "ya" not in r.json()
    assert len({l["respondio_por"] for l in repo.leads if l.get("respondio") is not None}) == 3


# ═════════════════════════════════════ 5. límite lleno: se mide igual
def test_ventana_fija_llena_no_guarda_la_clave_pero_avisa():
    v = VentanaFija(limite=2, max_claves=1)
    assert v.check("a", 0.0) == "ok" and v.check("b", 1.0) == "full" and "b" not in v._cuentas


def test_con_el_limite_lleno_igual_se_cuenta_la_visita(cliente, repo):
    cliente.auto_volcar = False
    site_metrics.medidor.limitadores["collect"].max_claves = 0               # todo diccionario nuevo nace lleno
    assert _collect(cliente, _pv()).status_code == 204
    assert site_metrics.volcar(repo) == {"visitas": 1}
    r = cliente.post("/visita", json={"ruta": "/buscar", "sesion": "sesion-vieja01", "primera": True}, headers={"user-agent": UA}).json()
    assert r["contada"] is True
    site_metrics.medidor.limitadores["lead"].max_claves = 0
    assert _lead(cliente, sesion="sesion-llena01")["ok"] is True and site_metrics.volcar(repo)["leads"] == 1
    site_metrics.medidor.limitadores["busqueda"].max_claves = 0
    assert "busqueda_id" in cliente.post("/busquedas/log", json={"query": "zapatos"}, headers={"user-agent": UA}).json()


# ═════════════════════════════════════ 6. el log de CSP no se puede falsificar
def _csp(**campos):
    return json.dumps({"csp-report": {"effective-directive": "script-src-elem", "blocked-uri": "https://cdn.ajeno.example/x.js",
                                      "disposition": "report", **campos}}).encode()


def test_csp_con_saltos_de_linea_y_basura_queda_como_otro():
    r = site_metrics.resumir_csp(_csp(**{"effective-directive": "script-src\nERROR admin_login ok=true", "blocked-uri": "evil\r\n[error] x",
                                         "disposition": "enforce\n2026-01-01 fake"}))
    assert r == {"directiva": "otro", "bloqueado": "otro", "disposicion": "otro"}


@pytest.mark.parametrize("blocked, esperado", [
    ("https://cdn.ajeno.example:8443/x.js?token=1", "cdn.ajeno.example"),
    ("inline", "inline"), ("eval", "eval"), ("data", "data"), ("blob", "blob"), ("wasm-eval", "wasm-eval"),
    ("data:image/png;base64,AAAA", "data"), ("blob:https://uruku.bo/1234", "blob"),
    ("evil.example", "evil.example"),
    ("javascript:alert(1)", "otro"), ("https://[::1", "otro"), ("ejemplo con espacios", "otro"), ("a%0Ab", "otro"),
    ("EVIL.EXAMPLE", "evil.example"), ("x" * 500, "otro"), ("https://ünï.example/", "otro"),
])
def test_csp_bloqueado_sólo_host_o_palabra_conocida(blocked, esperado):
    assert site_metrics.resumir_csp(_csp(**{"blocked-uri": blocked}))["bloqueado"] == esperado


def test_csp_directiva_y_disposicion_con_lista_blanca():
    assert site_metrics.resumir_csp(_csp(**{"effective-directive": "img-src 'self' https:"}))["directiva"] == "img-src"
    assert site_metrics.resumir_csp(_csp(**{"effective-directive": "x" * 41}))["directiva"] == "otro"
    assert site_metrics.resumir_csp(_csp(**{"effective-directive": "Script_Src"}))["directiva"] == "otro"
    assert site_metrics.resumir_csp(_csp(disposition="ENFORCE"))["disposicion"] == "enforce"
    assert site_metrics.resumir_csp(_csp(disposition=None))["disposicion"] == "otro"


def test_csp_se_agrega_por_directiva_y_host_y_sale_una_linea_por_minuto(cliente, monkeypatch):
    ahora = [1_000_000.0]
    monkeypatch.setattr(site_metrics, "_reloj", lambda: ahora[0])
    site_metrics.reiniciar()
    with capture_logs() as logs:
        for _ in range(20):
            assert cliente.post("/csp-report", content=_csp(), headers={"content-type": "application/csp-report"}).status_code == 204
        assert cliente.post("/csp-report", content=_csp(**{"blocked-uri": "inline"})).status_code == 204
        assert not [l for l in logs if l["event"] == "csp_violations"]           # todavía no pasó el minuto
        ahora[0] += 61
        assert cliente.post("/csp-report", content=_csp()).status_code == 204
    lineas = [l for l in logs if l["event"] == "csp_violations"]
    assert len(lineas) == 1                                                       # UNA línea, no una por reporte
    por = {(i["directiva"], i["bloqueado"]): i["n"] for i in lineas[0]["items"]}
    assert por == {("script-src-elem", "cdn.ajeno.example"): 21, ("script-src-elem", "inline"): 1}
    assert lineas[0]["total"] == 22


def test_csp_tope_de_claves_distintas_por_minuto(monkeypatch):
    monkeypatch.setattr(site_metrics, "MAX_CLAVES_CSP", 3)
    m = Medidor()
    for i in range(10):
        m.anotar_csp("img-src", f"host{i}.example", "report")
    filas = m.tomar_csp_si_toca(forzar=True)
    assert len(filas) == 4 and next(f for f in filas if f["bloqueado"] == "otro")["n"] == 7


def test_csp_el_volcado_periodico_tambien_emite_la_linea(repo, monkeypatch):
    ahora = [1_000_000.0]
    monkeypatch.setattr(site_metrics, "_reloj", lambda: ahora[0])
    site_metrics.reiniciar()
    site_metrics.registrar_csp(site_metrics.resumir_csp(_csp()))
    ahora[0] += 61
    with capture_logs() as logs:
        site_metrics.volcar(repo)                                                 # lo llama el bucle de 5 s
    assert len([l for l in logs if l["event"] == "csp_violations"]) == 1


# ═════════════════════════════════════ 7. enmascarado
@pytest.mark.parametrize("crudo, esperado", [
    ("71234567 zapatos", "# zapatos"),
    ("+591 712-34567 pan", "# pan"),
    ("llamame al 71 23 45 67 gracias", "llamame al # gracias"),
    ("(591) 71.234.567", "(#"),
    ("tel 712 345", "tel #"),
    ("tel 712 34", "tel 712 34"),                                  # 5 dígitos: no es un teléfono
    ("talle 38 y 40", "talle 38 y 40"),
    ("juan (at) gmail (dot) com", "[mail]"),
    ("juan [at] gmail [dot] com por favor", "[mail] por favor"),
    ("juan @ gmail . com", "[mail]"),
    ("JUAN.PEREZ@GMAIL.COM", "[mail]"),
    ("escribime a juan.perez@gmail.com por favor", "escribime a [mail] por favor"),
    ("mail a@b.co y 71234567", "mail [mail] y #"),
    ("  mucho    espacio  ", "mucho espacio"),
])
def test_enmascarar_texto(crudo, esperado):
    assert site_metrics.enmascarar_busqueda(crudo) == esperado


def test_el_ref_tambien_se_enmascara():
    assert limpiar_ref("volante-rustico") == "volante-rustico"
    assert limpiar_ref("qr-71234567") == "qr-n"
    assert limpiar_ref("qr-591 712-34567") == "qr-n"
    assert limpiar_ref("juan@gmail.com") == "mail"
    assert limpiar_ref("juan (at) gmail (dot) com") == "mail"
    assert limpiar_ref("Mesa-Bazar-24") == "mesa-bazar-24"
    assert limpiar_ref("   ") is None and limpiar_ref(None) is None and limpiar_ref("@@@") is None
    assert len(limpiar_ref("a" * 300)) == 64


def test_un_ref_con_telefono_llega_enmascarado_a_la_base(cliente, repo):
    _lead(cliente, origen="qr-71234567")
    _collect(cliente, _pv(ref="591 712-34567"))
    site_metrics.volcar(repo)
    assert repo.leads[-1]["origen"] == "qr-n" and repo.visitas[-1]["origen"] == "n"


def test_enmascarar_no_se_cuelga_con_entradas_patologicas():
    import time
    t0 = time.perf_counter()
    for crudo in ("a" * 200, "1 " * 100, "a@" * 100, "a.a.a.a.a.a@" * 16, "(at)" * 50, "1" * 200):
        enmascarar_texto(crudo)
    assert time.perf_counter() - t0 < 1.0


# ═════════════════════════════════════ 8. spam de referrer en «Mi comercio»
class _RepoOrigenes:
    def __init__(self, filas):
        self.filas = filas

    def comercio_lead_counts(self, _c, _d):
        return {}

    def comercio_origins(self, _c, _d):
        return self.filas


def _origenes(filas):
    r = site_metrics.metricas_de_comercio(_RepoOrigenes(filas), C1, 30)
    return {(o["kind"], o["name"]): o["n"] for o in r["origenes_30d"]}


def test_un_host_desconocido_con_menos_de_3_sesiones_se_junta_en_otros():
    filas = [
        {"origen": None, "referido": "spam-pastillas.example", "n": 40, "sesiones": 1},       # un solo bot con 40 páginas vistas
        {"origen": None, "referido": "otro-spam.example", "n": 2, "sesiones": 2},
        {"origen": None, "referido": "blog-amigo.example", "n": 5, "sesiones": 4},            # 4 personas: se nombra
        {"origen": None, "referido": "l.facebook.com", "n": 1, "sesiones": 1},                # conocidos: siempre
        {"origen": None, "referido": "mail.google.com", "n": 1, "sesiones": 1},
        {"origen": None, "referido": "www.google.com", "n": 1, "sesiones": 1},
    ]
    assert _origenes(filas) == {("other", "blog-amigo.example"): 4, ("other", "otros"): 3, ("social", "facebook"): 1,
                                ("other", "gmail"): 1, ("search", "google"): 1}


def test_sin_la_columna_sesiones_se_usa_n_como_antes():
    assert _origenes([{"origen": None, "referido": "chico.example", "n": 2}]) == {("other", "otros"): 2}
    assert _origenes([{"origen": None, "referido": "grande.example", "n": 3}]) == {("other", "grande.example"): 3}


def test_en_mi_comercio_sólo_son_qr_los_conocidos():
    filas = [{"origen": "volante-rustico", "referido": None, "n": 4, "sesiones": 4},
             {"origen": "mesa-rustico", "referido": None, "n": 3, "sesiones": 3},
             {"origen": "ficha-rustico", "referido": None, "n": 2, "sesiones": 2},
             {"origen": "visita-mi-nuevo-negocio-gratis", "referido": None, "n": 9, "sesiones": 9},
             {"origen": "oferta-xyz", "referido": None, "n": 1, "sesiones": 1},
             {"origen": "ig", "referido": None, "n": 2, "sesiones": 2}]
    assert _origenes(filas) == {("qr", "volante"): 4, ("qr", "mesa"): 3, ("qr", "ficha"): 2, ("other", "otros"): 10,
                                ("social", "instagram"): 2}


def test_el_panel_del_admin_sigue_viendo_todo():
    assert site_metrics.clasificar_llegada("visita-mi-nuevo-negocio", None) == ("other", "qr_visita")


# ═════════════════════════════════════ 9. «te escribieron o llamaron» sin el mapa
def _com_headers(cid):
    from tests.conftest import comercio_token
    return {"Authorization": f"Bearer {comercio_token(comercio_id=cid)}"}


def test_contactos_30d_y_7d_no_cuentan_el_mapa(client, repo):
    repo.seed_comercio(id=C1, slug="rustico", nombre="Rústico", whatsapp="591700001")
    client.auto_volcar = False
    for tipo, extra in (("whatsapp", {}), ("telefono", {}), ("mapa", {}), ("mapa", {"sesion": "sesion-m00002"}),
                        ("compartir", {"detalle": "copy"}), ("red", {"detalle": "tiktok"}), ("vista", {})):
        client.post("/lead", json={"comercio_id": C1, "tipo": tipo, "sesion": "sesion-m00001", **extra}, headers={"user-agent": UA})
    site_metrics.volcar(repo)
    d = client.get("/comercio/metricas", headers=_com_headers(C1)).json()
    assert d["contactos_30d"] == 2 and d["contactos_7d"] == 2
    assert d["como_llegar_30d"] == 2                                   # el mapa tiene su cifra aparte
