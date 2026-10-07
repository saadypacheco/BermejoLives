"""QA del rediseño del panel (docs/admin-rediseno.md): lo que el dev no cubrió.

Cubre los criterios de aceptación 1, 2, 3 y 6 en lo que se puede probar sin navegador
y los casos borde de `GET /admin/resumen`:

- tablero vacío, ciudad desconocida / rara / larguísima, base caída (503, sin filtrar el error);
- Reservalo caído de varias maneras (con el cliente REAL, no un doble);
- permisos: tokens vencidos, firmados mal, `alg: none`, tokens viejos sin `permisos`;
- ningún conteo con tope de 1000 (volúmenes reales en el espejo y revisión estática del SQL);
- el contrato backend <-> frontend (`ResumenAdmin`, badges del menú y filas del tablero);
- el inventario del menú (criterio 1) y que el panel no baja nada al entrar (criterio 3).

No toca código de producción.
"""
import base64
import json
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.core import auth
from app.core.config import settings
from app.main import app
from app.services import cargas, resumen_admin, vencimientos
from app.services.reservalo_sync import ReservaloSyncClient, get_reservalo_sync_client

HOY = date(2026, 10, 6)
RAIZ = Path(__file__).resolve().parents[2]
FRONT = RAIZ / "frontend"


# ───────────────────────────────────────────────────────────────── ayudas
def headers(token):
    return {"Authorization": f"Bearer {token}"}


def admin_h():
    return headers(auth.make_token("admin@uruku.bo", rol="admin"))


class ReservaloFalso:
    def __init__(self, pendientes=0):
        self.pendientes = pendientes

    def contar_consultas_pendientes(self, timeout=5.0):
        return self.pendientes


@pytest.fixture(autouse=True)
def _sin_red_ni_cache(monkeypatch):
    def cert(host, puerto=443, timeout=6.0):
        return {"host": host, "ok": True, "dias": 90, "estado": "ok"}

    monkeypatch.setattr(vencimientos, "vence_certificado", cert)
    vencimientos.limpiar_cache_certificados()
    monkeypatch.setattr(cargas, "hoy_bolivia", lambda ahora=None: HOY)
    yield
    vencimientos.limpiar_cache_certificados()


@pytest.fixture
def reservalo():
    return ReservaloFalso()


@pytest.fixture
def api(client, repo, reservalo):
    app.dependency_overrides[get_reservalo_sync_client] = lambda: reservalo
    return client


def pedir(api, ciudad=None, h=None, **params):
    if ciudad is not None:
        params["ciudad"] = ciudad
    return api.get("/admin/resumen", headers=h or admin_h(), params=params)


def _jwt(claims, secret=None, alg="HS256"):
    import jwt as pyjwt
    return pyjwt.encode(claims, secret or settings.jwt_secret, algorithm=alg)


# ─────────────────────────────────────────────────── 1. todo vacío / ciudad rara
def test_todo_vacio_da_ceros_y_30_dias_en_cero_no_error(api, repo):
    d = pedir(api).json()
    assert d["comercios"] == {k: 0 for k in d["comercios"]}
    assert all(v == 0 for v in d["pendientes"].values())
    assert d["actividad"]["visitas_7d"] == 0 and d["actividad"]["contactos_7d"] == 0
    serie = d["actividad"]["serie_30d"]
    assert len(serie) == 30
    assert serie[0]["dia"] == "2026-09-07" and serie[-1]["dia"] == "2026-10-06"
    assert all(f["altas"] == f["visitas"] == f["contactos"] == 0 for f in serie)
    # por_ciudad viene igual (las ciudades existen aunque no tengan comercios)
    assert {c["slug"] for c in d["por_ciudad"]} == {"bermejo", "santa-cruz"}


def test_sin_ciudades_activas_por_ciudad_es_lista_vacia(api, repo, monkeypatch):
    monkeypatch.setattr(repo, "list_ciudades", lambda: [])
    assert pedir(api).json()["por_ciudad"] == []


@pytest.mark.parametrize("slug", ["no-existe", "BERMEJO", "bermejo ' OR 1=1 --", "bermejo; drop table comercios",
                                  "../../etc/passwd", "<script>alert(1)</script>", "ñandú", "%00", "a" * 80])
def test_ciudades_desconocidas_o_maliciosas_dan_ceros_y_200(api, repo, slug):
    repo.seed_comercio(nombre="A", activo=True, ciudad_id="ciu-1", verificado=True, horario="x")
    r = pedir(api, ciudad=slug)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["comercios"]["total"] == 0
    assert d["ciudad"] == slug.strip()
    # por_ciudad sigue trayendo todas, con sus números reales
    assert next(c for c in d["por_ciudad"] if c["slug"] == "bermejo")["total"] == 1


def test_ciudad_de_mas_de_80_caracteres_es_422_no_500(api):
    assert pedir(api, ciudad="a" * 81).status_code == 422


def test_ciudad_repetida_en_la_url_no_rompe(api):
    r = api.get("/admin/resumen?ciudad=bermejo&ciudad=santa-cruz", headers=admin_h())
    assert r.status_code == 200


def test_el_resumen_es_solo_GET(api):
    for m in ("post", "put", "delete", "patch"):
        assert getattr(api, m)("/admin/resumen", headers=admin_h()).status_code == 405


# ─────────────────────────────────────────────── 2. base caída / respuestas raras
@pytest.mark.parametrize("devuelve", [None, {}, [], "x", {"comercios": None, "por_ciudad": []},
                                      {"comercios": {}, "por_ciudad": None}, {"comercios": []}],
                         ids=["none", "vacio", "lista", "str", "comercios-null", "por_ciudad-null", "comercios-lista"])
def test_respuestas_raras_de_la_base_son_503_y_no_500(api, repo, monkeypatch, devuelve):
    monkeypatch.setattr(repo, "resumen_admin", lambda c, h: devuelve)
    r = api.get("/admin/resumen", headers=admin_h())
    assert r.status_code == 503, r.text


def test_503_no_filtra_el_error_interno(api, repo):
    repo.resumen_admin_falla = True        # RuntimeError("PGRST202: ... public.admin_resumen")
    r = pedir(api)
    assert r.status_code == 503
    assert "PGRST" not in r.text and "admin_resumen" not in r.text and "Traceback" not in r.text
    assert r.json() == {"detail": "No se pudo calcular el resumen. Probá de nuevo en un momento."}


def test_si_la_base_cae_pero_reservalo_responde_igual_es_503(api, repo, reservalo):
    repo.resumen_admin_falla = True
    reservalo.pendientes = 5
    assert pedir(api).status_code == 503


def test_numeros_ilegibles_de_la_base_son_null_no_cero(api, repo, monkeypatch):
    real = repo.resumen_admin

    def con_basura(c, h):
        d = real(c, h)
        d["pendientes"]["pagos"] = "muchos"
        d["pendientes"]["reclamos"] = True
        d["actividad"]["visitas_7d"] = 3.0
        return d

    monkeypatch.setattr(repo, "resumen_admin", con_basura)
    d = pedir(api).json()
    assert d["pendientes"]["pagos"] is None and d["pendientes"]["reclamos"] is None
    assert d["actividad"]["visitas_7d"] == 3


# ─────────────────────────────────────── 3. Reservalo caído, con el cliente REAL
def _con_cliente_real(monkeypatch, get):
    from app.services import reservalo_sync

    monkeypatch.setattr(reservalo_sync.settings, "tienda_api_url", "http://tienda.test")
    monkeypatch.setattr(reservalo_sync.settings, "admin_sync_secret", "s3cret")
    monkeypatch.setattr(reservalo_sync.httpx, "get", get)
    app.dependency_overrides[get_reservalo_sync_client] = lambda: ReservaloSyncClient()


class _Resp:
    def __init__(self, status=200, cuerpo=None, json_roto=False):
        self.status, self.cuerpo, self.json_roto = status, cuerpo, json_roto

    def raise_for_status(self):
        from app.services import reservalo_sync
        if self.status >= 400:
            raise reservalo_sync.httpx.HTTPStatusError("boom", request=None, response=None)

    def json(self):
        if self.json_roto:
            raise ValueError("no es json")
        return self.cuerpo


@pytest.mark.parametrize("como", ["timeout", "conexion", "500", "401", "json-roto", "raiz-lista", "items-null", "items-string"])
def test_reservalo_caido_o_raro_deja_reclamos_en_null_y_el_resto_en_pie(client, repo, monkeypatch, como):
    from app.services import reservalo_sync
    repo.seed_comercio(nombre="A", activo=True, ciudad_id="ciu-1")
    repo.reclamos["r1"] = {"id": "r1", "estado": "pendiente"}

    def get(url, headers=None, params=None, timeout=None):
        if como == "timeout":
            raise reservalo_sync.httpx.ReadTimeout("lento")
        if como == "conexion":
            raise reservalo_sync.httpx.ConnectError("no responde")
        if como == "500":
            return _Resp(500)
        if como == "401":
            return _Resp(401)
        if como == "json-roto":
            return _Resp(200, json_roto=True)
        if como == "raiz-lista":
            return _Resp(200, [])
        if como == "items-null":
            return _Resp(200, {"items": None})
        return _Resp(200, {"items": "nada"})

    _con_cliente_real(monkeypatch, get)
    r = client.get("/admin/resumen", headers=admin_h())
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["pendientes"]["reclamos"] is None, como
    assert d["comercios"]["total"] == 1


def test_reservalo_con_consultas_se_suma_a_los_reclamos(client, repo, monkeypatch):
    repo.reclamos["r1"] = {"id": "r1", "estado": "pendiente"}
    repo.reclamos["r2"] = {"id": "r2", "estado": "respondido"}
    _con_cliente_real(monkeypatch, lambda *a, **k: _Resp(200, {"items": [{"estado": "pendiente"}] * 3 + [{"estado": "respondida"}]}))
    assert client.get("/admin/resumen", headers=admin_h()).json()["pendientes"]["reclamos"] == 4


def test_reservalo_lento_no_cuelga_el_tablero_el_timeout_es_corto(client, monkeypatch):
    visto = {}

    def get(url, headers=None, params=None, timeout=None):
        visto["timeout"] = timeout
        return _Resp(200, {"items": []})

    _con_cliente_real(monkeypatch, get)
    client.get("/admin/resumen", headers=admin_h())
    assert visto["timeout"] is not None and visto["timeout"] <= 5


def test_el_tablero_tarda_lo_de_la_mas_lenta_y_no_la_suma(api, repo, reservalo, monkeypatch):
    """Reservalo y los certificados van en paralelo con la base: 0.4 s + 0.4 s no deben dar >0.7 s."""
    def lento_reservalo(timeout=5.0):
        time.sleep(0.4)
        return 0

    def lento_certs(*a, **k):
        time.sleep(0.4)
        return 0

    reservalo.contar_consultas_pendientes = lento_reservalo
    monkeypatch.setattr(vencimientos, "alertas_de_certificados", lento_certs)
    t = time.monotonic()
    assert pedir(api).status_code == 200
    assert time.monotonic() - t < 0.75


def test_un_error_inesperado_midiendo_certificados_es_null_solo_en_vencimientos(api, repo, monkeypatch):
    repo.seed_comercio(nombre="A", activo=True, ciudad_id="ciu-1")

    def explota(host, puerto=443, timeout=6.0):
        raise OSError("DNS caído")

    monkeypatch.setattr(vencimientos, "vence_certificado", explota)
    vencimientos.limpiar_cache_certificados()
    r = pedir(api)
    assert r.status_code == 200
    d = r.json()
    assert d["pendientes"]["vencimientos"] is None and d["comercios"]["total"] == 1


# ─────────────────────────────────────────────────────────────── 4. permisos
@pytest.mark.parametrize("quien,token,esperado", [
    ("admin", lambda: auth.make_token("a@x", rol="admin"), 200),
    ("moderador", lambda: auth.make_token("m@x", rol="moderador"), 200),
    ("publicador", lambda: auth.make_publicador_token("p@x"), 200),
    ("agente", lambda: auth.make_agente_token("ag@x", ciudad_slug="bermejo"), 403),
    ("agente-sin-ciudad", lambda: auth.make_agente_token("ag@x"), 403),
    ("comercio", lambda: auth.make_comercio_token("com-1", "c@x"), 403),
    ("comprador", lambda: auth.make_usuario_token("u-1", "59170000000"), 403),
    ("rol-desconocido", lambda: auth.make_token("z@x", rol="hacker"), 403),
])
def test_matriz_de_roles(api, quien, token, esperado):
    assert pedir(api, h=headers(token())).status_code == esperado, quien


def test_sin_cabecera_y_con_esquema_equivocado_es_401(api):
    assert api.get("/admin/resumen").status_code == 401
    assert api.get("/admin/resumen", headers={"Authorization": "Basic YTpi"}).status_code == 401
    assert api.get("/admin/resumen", headers={"Authorization": "Bearer "}).status_code in (401, 403)


def test_token_vencido_es_401(api):
    t = _jwt({"sub": "a@x", "email": "a@x", "rol": "admin", "exp": int(time.time()) - 10})
    assert pedir(api, h=headers(t)).status_code == 401


def test_token_firmado_con_otro_secreto_es_401(api):
    t = _jwt({"sub": "a@x", "rol": "admin", "permisos": ["*"], "exp": int(time.time()) + 600},
             secret="otro-secreto-distinto-de-32-bytes-minimo!!")
    assert pedir(api, h=headers(t)).status_code == 401


def test_token_alg_none_es_401(api):
    def b64(o):
        return base64.urlsafe_b64encode(json.dumps(o).encode()).rstrip(b"=").decode()
    t = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'rol': 'admin', 'permisos': ['*'], 'exp': int(time.time()) + 600})}."
    assert pedir(api, h=headers(t)).status_code == 401


def test_permisos_inyectados_en_un_token_de_comercio_firmado_bien_si_cuentan_pero_el_login_no_los_da(api):
    """El token es lo que manda (como en todo el backend). Un comercio NORMAL no lleva `permisos`."""
    import jwt as pyjwt
    t = auth.make_comercio_token("com-1", "c@x")
    claims = pyjwt.decode(t, settings.jwt_secret, algorithms=["HS256"])
    assert "permisos" not in claims


@pytest.mark.parametrize("claims,esperado", [
    ({"rol": "moderador"}, 200),                              # token viejo (sin el claim): cae en el rol
    ({"rol": "moderador", "permisos": []}, 403),              # rol vaciado desde Equipo: lista vacía = sin permisos
    ({"rol": "moderador", "permisos": None}, 200),            # null = «no viene»: cae en el rol
    ({"rol": "x", "permisos": ["panel"]}, 200),               # el cajón «panel»
    ({"rol": "x", "permisos": ["moderar", "comercios.cargar"]}, 200),
    ({"rol": "x", "permisos": ["comercios.cargar"]}, 403),
    ({"rol": "x", "permisos": ["xyz"]}, 403),                 # permiso que no existe en el catálogo
    ({"rol": "x", "permisos": ["*"]}, 200),
    ({"rol": "x", "permisos": "moderar"}, None),              # mal formado: no debe ser 500
], ids=["moderador-sin-claim", "moderador-lista-vacia", "moderador-null", "panel", "moderar+cargar", "solo-cargar", "inexistente", "comodin", "permisos-string"])
def test_formas_raras_del_claim_permisos(api, claims, esperado):
    t = _jwt({"sub": "q@x", "email": "q@x", "exp": int(time.time()) + 600, **claims})
    r = pedir(api, h=headers(t))
    if esperado is None:
        assert r.status_code < 500, r.text
    else:
        assert r.status_code == esperado, r.text


def test_un_rol_del_panel_con_otra_ciudad_igual_puede_pedir_cualquiera(api, repo):
    """La ciudad es un FILTRO, no un permiso (como el resto del panel): un moderador de Santa Cruz ve Bermejo."""
    repo.seed_comercio(nombre="A", activo=True, ciudad_id="ciu-1")
    t = auth.make_token("m@x", rol="moderador", ciudad_slug="santa-cruz")
    assert pedir(api, ciudad="bermejo", h=headers(t)).json()["comercios"]["total"] == 1


# ───────────────────────────────────────────── 5. nada con tope de 1000
def test_conteos_por_encima_de_1000_salen_enteros(api, repo):
    for i in range(1500):
        repo.comercios[f"b{i}"] = {"id": f"b{i}", "activo": True, "ciudad_id": "ciu-1", "verificado": i % 2 == 0,
                                   "horario": "" if i % 3 == 0 else "8 a 18", "whatsapp": "5", "portada_url": "x",
                                   "created_at": "2026-10-06T15:00:00+00:00"}
    for i in range(1200):
        repo.comercios[f"s{i}"] = {"id": f"s{i}", "activo": True, "ciudad_id": "ciu-santa-cruz", "verificado": True,
                                   "paga_hasta": "2026-10-07"}
    for i in range(1300):
        repo.publicaciones.append({"id": f"p{i}", "estado": "pendiente", "activo": True})
    for i in range(1100):
        repo.pagos[f"g{i}"] = {"id": f"g{i}", "estado": "pendiente", "comercio_id": "x"}
    for i in range(1050):
        repo.reclamos[f"r{i}"] = {"id": f"r{i}", "estado": "pendiente"}
    for i in range(1020):
        repo.solicitudes_numero[f"n{i}"] = {"id": f"n{i}", "estado": "pendiente"}
    for i in range(1010):
        repo.wa_inbox[f"w{i}"] = {"resultado": "sin_comercio", "created_at": "2026-10-06T15:00:00+00:00"}
    repo.visitas.extend({"dia": "2026-10-06", "ciudad_slug": "bermejo"} for _ in range(1500))
    repo.leads.extend({"comercio_id": "b1", "tipo": "whatsapp", "created_at": "2026-10-06T15:00:00+00:00"} for _ in range(1100))

    d = pedir(api).json()
    assert d["comercios"]["total"] == 2700 and d["comercios"]["verificados"] == 750 + 1200
    assert d["comercios"]["sin_verificar"] == 750 and d["comercios"]["sin_horario"] == 500 + 1200
    p = d["pendientes"]
    assert (p["publicaciones"], p["pagos"], p["reclamos"], p["cambio_numero"], p["recepcion_sin_comercio"]) == (1300, 1100, 1050, 1020, 1010)
    assert p["suscripciones"] == 1200 and p["comercios_sin_verificar"] == 750
    assert d["actividad"]["visitas_7d"] == 1500 and d["actividad"]["contactos_7d"] == 1100
    assert d["actividad"]["serie_30d"][-1]["visitas"] == 1500
    assert {c["slug"]: c["total"] for c in d["por_ciudad"]} == {"bermejo": 1500, "santa-cruz": 1200}


def test_ni_el_servicio_ni_el_repo_ni_el_sql_ponen_tope_ni_bajan_filas():
    fuentes = {
        "servicio": (RAIZ / "backend/app/services/resumen_admin.py").read_text(encoding="utf-8"),
        "sql supabase": (RAIZ / "supabase/migrations/0139_admin_resumen.sql").read_text(encoding="utf-8"),
    }
    repo_py = (RAIZ / "backend/app/db/repository.py").read_text(encoding="utf-8")
    inicio = repo_py.index("def resumen_admin(self, ciudad_slug")
    fuentes["repo real"] = repo_py[inicio: repo_py.index("def list_cargas_de_agentes", inicio)]
    for nombre, src in fuentes.items():
        sin_comentarios = "\n".join(l for l in src.splitlines() if not l.strip().startswith(("--", "#")))
        assert not re.search(r"\blimit\b|\.limit\(|\.range\(|\.table\(|\.select\(", sin_comentarios, re.I), nombre


def test_sql_selfhost_y_supabase_son_identicos_byte_a_byte():
    a = (RAIZ / "supabase/migrations/0139_admin_resumen.sql").read_bytes()
    b = (RAIZ / "selfhost/postgres-init/0139_admin_resumen.sql").read_bytes()
    assert a == b


def test_el_numero_de_la_migracion_no_choca_con_otra():
    nums = [p.name[:4] for p in (RAIZ / "supabase/migrations").glob("*.sql")]
    assert nums.count("0139") == 1
    nums2 = [p.name[:4] for p in (RAIZ / "selfhost/postgres-init").glob("*.sql")]
    assert nums2.count("0139") == 1


# ───────────────────────────────── 6. contrato backend <-> frontend (criterios 2 y 6)
def _tipo_resumen_admin():
    src = (FRONT / "lib/api.ts").read_text(encoding="utf-8")
    ini = src.index("export type ResumenAdmin = {")
    fin = src.index("export async function getResumenAdmin", ini)
    return src[ini:fin]


def _claves_de(bloque_tipo, nombre):
    """Las claves de `nombre: { ... }` dentro del tipo (hasta la llave que cierra)."""
    i = bloque_tipo.index(f"{nombre}: {{")
    j = i + len(nombre) + 3
    prof, k = 1, j
    while prof:
        prof += {"{": 1, "}": -1}.get(bloque_tipo[k], 0)
        k += 1
    cuerpo = bloque_tipo[j:k - 1]
    quitado = re.sub(r"//[^\n]*|/\*.*?\*/", "", cuerpo, flags=re.S)
    return set(re.findall(r"^\s*(\w+)\??:", quitado, flags=re.M))


def test_ResumenAdmin_del_front_tiene_las_mismas_claves_que_responde_el_backend(api, repo):
    repo.seed_comercio(nombre="A", activo=True, ciudad_id="ciu-1")
    d = pedir(api).json()
    t = _tipo_resumen_admin()
    assert _claves_de(t, "comercios") == set(d["comercios"])
    assert _claves_de(t, "pendientes") == set(d["pendientes"])
    assert _claves_de(t, "actividad") == set(d["actividad"])
    assert set(d["actividad"]["serie_30d"][0]) == {"dia", "altas", "visitas", "contactos"}
    assert set(d["por_ciudad"][0]) == {"slug", "nombre", "total", "sin_verificar", "sin_horario"}
    assert set(d) == {"ciudad", "comercios", "por_ciudad", "pendientes", "actividad"}


def test_cada_badge_y_cada_fila_del_tablero_apunta_a_un_pendiente_que_existe(api):
    d = pedir(api).json()["pendientes"]
    shell = (FRONT / "components/admin/admin-shell.tsx").read_text(encoding="utf-8")
    dash = (FRONT / "components/admin/dashboard.tsx").read_text(encoding="utf-8")
    campos = set(re.findall(r'campo:\s*"(\w+)"', shell))
    claves = set(re.findall(r'clave:\s*"(\w+)"', dash))
    assert campos and claves
    assert campos <= set(d), campos - set(d)
    assert claves == set(d), (claves ^ set(d))     # el tablero muestra los 8 pendientes, ni uno menos


# ─────────────── 7. criterio 1: el inventario (las 23 pestañas de antes + Inicio + Calles)
PESTANAS_DE_ANTES = {
    # id nuevo: (permiso que pedía la pestaña vieja, hoy)
    "negocios": None,            # era `comercios`
    "lugares": "lugares", "adornos": "lugares", "catalogo": "datos", "rubros": "rubros",
    "revision-rubros": "rubros", "whatsapp": "whatsapp", "difusion": "difusion", "demanda": "datos",
    "ayuda": "ayuda", "equipo": "equipo", "compradores": "datos", "planes": "planes", "importados": "datos",
    "cargas": "equipo", "publicaciones": None, "suscripciones": None, "pagos": None, "monitoreo": None,
    "kpis": None, "reclamos": None, "cambio-numero": None, "vencimientos": None,
}


def _secciones_ts():
    src = (FRONT / "components/admin/secciones.ts").read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r'\{\s*id:\s*"([\w-]+)",[^}]*?\}', src):
        permiso = re.search(r'permiso:\s*"(\w+)"', m.group(0))
        out[m.group(1)] = permiso.group(1) if permiso else None
    return out


def test_el_menu_tiene_las_23_pestanas_de_antes_con_el_mismo_permiso_mas_inicio_y_calles():
    menu = _secciones_ts()
    assert len(PESTANAS_DE_ANTES) == 23
    for sid, permiso in PESTANAS_DE_ANTES.items():
        assert sid in menu, f"falta la sección {sid}"
        assert menu[sid] == permiso, f"{sid}: permiso {menu[sid]!r} en vez de {permiso!r}"
    assert menu.get("inicio") is None and menu.get("calles") is None
    assert set(menu) == set(PESTANAS_DE_ANTES) | {"inicio", "calles"}


def test_el_tipo_SeccionAdmin_y_el_menu_coinciden():
    src = (FRONT / "components/admin/secciones.ts").read_text(encoding="utf-8")
    ini = src.index("export type SeccionAdmin =")
    tipo = src[ini: src.index(";", ini)]
    assert set(re.findall(r'"([\w-]+)"', tipo)) == set(_secciones_ts())


def test_cada_seccion_tiene_su_rama_de_render_en_page_tsx():
    page = (FRONT / "app/admin/page.tsx").read_text(encoding="utf-8")
    for sid in _secciones_ts():
        if sid == "inicio":
            assert 'seccion === "inicio"' in page
        else:
            assert f'seccion === "{sid}"' in page, f"la sección {sid} está en el menú pero no se dibuja"


def test_cada_rama_de_render_pide_el_mismo_permiso_que_el_menu():
    """El menú oculta; la guarda de la URL (`permitida`) usa el mismo `permiso` de secciones.ts."""
    page = (FRONT / "app/admin/page.tsx").read_text(encoding="utf-8")
    assert "const permitida = !defActual.permiso || puedo(defActual.permiso);" in page
    ramas = re.findall(r'\{(permitida && )?seccion === "([\w-]+)"', page)
    sin_guarda = [s for g, s in ramas if not g and s != "inicio"]
    assert not sin_guarda, f"se dibujan sin mirar el permiso: {sin_guarda}"


# ───────────────────────── 8. criterio 3: al entrar no se baja nada más que el resumen
def test_page_tsx_no_baja_listas_al_entrar():
    page = (FRONT / "app/admin/page.tsx").read_text(encoding="utf-8")
    # la lista pesada se pide en un solo lugar (el loader perezoso) y los rubros en otro
    assert page.count("listTodosComercios()") == 1
    panel = page[page.index("function AdminPanel()"):]
    panel = panel[: panel.index("\nfunction ", 10)]
    assert panel.count("getRubros()") == 1 and panel.count("listTodosComercios()") == 1
    assert "getVencimientos" not in page
    # el efecto que corre con la sesión sólo pide el resumen
    efecto = page[page.index("if (!authed || !ciudadLista) return;"):]
    efecto = efecto[: efecto.index("}, [authed, ciudadLista, pedirResumen]);")]
    assert "pedirResumen(false)" in efecto
    assert not re.search(r"\b(cargar\w+|load\w*|list\w+|get\w+)\(", efecto.replace("pedirResumen(false)", ""))
    # y no quedó ningún useEffect de montaje que cargue datos
    entrada = page[page.index("if (getToken()) setAuthed(true);"):]
    entrada = entrada[: entrada.index("}, []);")]
    assert "cargar" not in entrada and "load" not in entrada


def test_cada_seccion_con_datos_los_pide_al_abrirse():
    page = (FRONT / "app/admin/page.tsx").read_text(encoding="utf-8")
    bloque = page[page.index("switch (seccion) {"): page.index("default: break;")]
    esperado = {
        "negocios": "cargarComercios", "calles": "cargarComercios", "monitoreo": "cargarEstadisticas",
        "importados": "cargarRubros", "publicaciones": "cargarPendientes", "suscripciones": "cargarSuscripciones",
        "pagos": "cargarPagos", "kpis": "cargarKpis", "reclamos": "cargarReclamos", "cambio-numero": "cargarSolicitudes",
    }
    for sid, fn in esperado.items():
        m = re.search(rf'case "{sid}":([^\n]*)', bloque)
        assert m and fn in m.group(1), sid
