"""Dax: «¿dónde consigo X?» mira también lo que los comercios tienen publicado.

Antes sólo buscaba en la ficha del comercio (nombre, rubro, subcategoría) y, si no
encontraba, decía «No encontré». Ahora: ofertas y novedades vigentes, lo que la IA
leyó de las fotos, apodos ("zapas"), estrella primero, y si no hay nada, el encargo
de URUKU. Todo sin modelo.
"""
import re
from datetime import datetime

import pytest

from app.core.config import settings
from app.services import asistente, sinonimos

MARTES_11 = datetime(2026, 9, 15, 11, 0)     # martes 11:00 (hoy = 2026-09-15)
MARTES_13 = datetime(2026, 9, 15, 13, 0)     # siesta: Lun-Sáb 8-12 y 14:30-20 está cerrado


@pytest.fixture(autouse=True)
def sin_modelo(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")


def _comercio(repo, cid, nombre, **extra):
    c = {"id": cid, "slug": cid.replace("com-", ""), "nombre": nombre, "activo": True,
         "subcategoria": "deportes", "direccion": "Calle Comercio 1", "horario": "Lun-Sáb 8:00-12:00 y 14:30-20:00",
         "whatsapp": "59170000001", "plan": "gratis", "prod_obs_human": "pelotas, camisetas", **extra}
    repo.comercios[cid] = c
    return c


def _oferta(repo, cid, titulo, **extra):
    n = len(repo.publicaciones) + 1
    p = {"id": f"pub-{n}", "comercio_id": cid, "tipo": "oferta", "titulo": titulo, "descripcion": None,
         "estado": "aprobado", "activo": True, "vence_el": None, **extra}
    repo.publicaciones.append(p)
    return p


def _preguntar(repo, texto, ahora=MARTES_11, **kw):
    return asistente.responder(repo, texto, ahora=ahora, **kw)


# ------------------------------------------------------------------ encuentra por la oferta

def test_encuentra_por_una_oferta_vigente_aunque_la_ficha_no_diga_nike(repo):
    _comercio(repo, "com-deportes-sur", "Deportes Sur")          # su ficha: pelotas y camisetas
    _oferta(repo, "com-deportes-sur", "Zapatillas Nike Bs 250")
    r = _preguntar(repo, "¿Dónde consigo zapatillas nike?")
    assert r.nivel == 0 and r.intent == "buscar" and not r.sin_respuesta
    assert "Deportes Sur" in r.texto
    assert "tiene la oferta «Zapatillas Nike Bs 250»" in r.texto
    assert "https://uruku.bo/comercios/deportes-sur" in r.texto       # la ficha
    assert "https://wa.me/59170000001" in r.texto                     # su WhatsApp
    assert "abierto" in r.texto.lower()                               # martes 11:00
    assert r.fuentes[0]["url"].endswith("/comercios/deportes-sur")


def test_otras_formas_de_preguntar_dondes(repo):
    _comercio(repo, "com-deportes-sur", "Deportes Sur")
    _oferta(repo, "com-deportes-sur", "Zapatillas Nike Bs 250")
    for pregunta in ("¿dónde puedo conseguir zapatillas nike?", "dónde se venden zapatillas nike",
                     "¿dónde encuentro zapatillas nike?", "quién vende zapatillas nike"):
        assert "Deportes Sur" in _preguntar(repo, pregunta).texto, pregunta


def test_lo_que_la_ia_leyo_de_la_foto_tambien_cuenta(repo):
    _comercio(repo, "com-deportes-sur", "Deportes Sur")
    _oferta(repo, "com-deportes-sur", "Liquidación de verano", terminos_ia="zapatillas deportivas, mochilas")
    r = _preguntar(repo, "dónde consigo mochilas")
    assert "Deportes Sur" in r.texto and "Liquidación de verano" in r.texto


def test_un_sinonimo_o_apodo_encuentra_lo_mismo(repo):
    _comercio(repo, "com-deportes-sur", "Deportes Sur")
    _oferta(repo, "com-deportes-sur", "Zapatillas Nike Bs 250")
    for pregunta in ("¿Dónde consigo zapas nike?", "dónde consigo zapas"):
        r = _preguntar(repo, pregunta)
        assert "Deportes Sur" in r.texto and not r.sin_respuesta, pregunta


def test_zapas_encuentra_a_la_zapateria_por_la_ficha(repo):
    _comercio(repo, "com-zap", "Zapatería Luz", subcategoria="calzado", prod_obs_human="zapatillas, botas")
    r = _preguntar(repo, "¿Dónde consigo zapas?")
    assert "Zapatería Luz" in r.texto and "vende calzado" in r.texto


def test_el_diccionario_de_la_base_tambien_se_usa(repo):
    _comercio(repo, "com-ropa", "Ropa Norte", subcategoria="ropa", prod_obs_human="jeans")
    _oferta(repo, "com-ropa", "Remeras de algodón Bs 60")
    repo.sinonimos["polera"] = "remera"
    r = _preguntar(repo, "dónde consigo poleras")
    assert "Ropa Norte" in r.texto


def test_plural_y_acentos(repo):
    _comercio(repo, "com-bici", "Ciclo Sur")
    _oferta(repo, "com-bici", "Bicicleta rodado 29 — OFERTA")
    assert "Ciclo Sur" in _preguntar(repo, "dónde consigo bicicletas").texto
    assert "Ciclo Sur" in _preguntar(repo, "dónde consigo BICÍCLETA").texto


# ------------------------------------------------------------------ lo que NO cuenta

def test_una_oferta_vencida_no_cuenta(repo):
    _comercio(repo, "com-deportes-sur", "Deportes Sur")
    _oferta(repo, "com-deportes-sur", "Zapatillas Nike Bs 250", vence_el="2026-09-14")
    r = _preguntar(repo, "dónde consigo zapatillas nike")
    assert r.sin_respuesta and "Deportes Sur" not in r.texto


def test_una_oferta_que_vence_hoy_todavia_cuenta(repo):
    _comercio(repo, "com-deportes-sur", "Deportes Sur")
    _oferta(repo, "com-deportes-sur", "Zapatillas Nike Bs 250", vence_el="2026-09-15")
    assert "Deportes Sur" in _preguntar(repo, "dónde consigo zapatillas nike").texto


@pytest.mark.parametrize("cambio", [
    {"estado": "pendiente"}, {"estado": "rechazado"}, {"estado": "cambios"},
    {"activo": False},                       # borrada (soft-delete)
    {"tipo": "video"},
])
def test_una_oferta_no_aprobada_o_borrada_no_cuenta(repo, cambio):
    _comercio(repo, "com-deportes-sur", "Deportes Sur")
    _oferta(repo, "com-deportes-sur", "Zapatillas Nike Bs 250", **cambio)
    r = _preguntar(repo, "dónde consigo zapatillas nike")
    assert r.sin_respuesta and "Deportes Sur" not in r.texto


def test_un_comercio_inactivo_o_suspendido_no_sale(repo):
    _comercio(repo, "com-baja", "Deportes Baja", activo=False)
    _oferta(repo, "com-baja", "Zapatillas Nike Bs 250")
    _comercio(repo, "com-susp", "Deportes Suspendido", suspendido=True)
    _oferta(repo, "com-susp", "Zapatillas Nike Bs 300")
    r = _preguntar(repo, "dónde consigo zapatillas nike")
    assert r.sin_respuesta
    assert "Deportes Baja" not in r.texto and "Deportes Suspendido" not in r.texto


def test_la_oferta_de_otra_ciudad_no_sale(repo):
    _comercio(repo, "com-tj", "Deportes Tarija", ciudad_slug="tarija")
    _oferta(repo, "com-tj", "Zapatillas Nike Bs 250")
    ciudad = {"slug": "bermejo", "nombre": "Bermejo", "guia_activa": True}
    assert _preguntar(repo, "dónde consigo zapatillas nike", ciudad=ciudad).sin_respuesta
    tarija = {"slug": "tarija", "nombre": "Tarija", "guia_activa": False}
    assert "Deportes Tarija" in _preguntar(repo, "dónde consigo zapatillas nike", ciudad=tarija).texto


# ------------------------------------------------------------------ sin resultados: el encargo

def test_sin_resultados_ofrece_el_encargo_y_el_buscador(repo):
    _comercio(repo, "com-deportes-sur", "Deportes Sur")
    r = _preguntar(repo, "¿dónde consigo un termo stanley?")
    assert r.nivel == 0 and r.intent == "buscar" and r.sin_respuesta
    assert "No encontré «termo stanley»" in r.texto
    assert "Podemos buscarlo por vos y guardártelo" in r.texto
    assert "67 671 888" in r.texto
    assert "https://wa.me/59167671888?text=" in r.texto
    assert "https://uruku.bo/buscar?q=termo+stanley" in r.texto


def test_sin_resultados_queda_anotada_como_sin_respuesta(client, repo):
    h = {"pregunta": "¿dónde consigo un termo stanley?", "sesion": "sesion-1"}
    j = client.post("/asistente/preguntar", json=h).json()
    assert j["sin_respuesta"] is True and "67 671 888" in j["texto"]
    assert repo.conversaciones[0]["sin_respuesta"] is True


def test_el_numero_publico_sale_de_la_configuracion(repo, monkeypatch):
    monkeypatch.setattr(settings, "wa_contacto_publico", "59170001234")
    r = _preguntar(repo, "dónde consigo un termo stanley")
    assert "70 001 234" in r.texto and "wa.me/59170001234" in r.texto
    monkeypatch.setattr(settings, "wa_contacto_publico", "")
    r = _preguntar(repo, "dónde consigo un termo stanley")
    assert "wa.me" not in r.texto and "buscador" in r.texto and r.sin_respuesta


def test_sin_resultados_no_tapa_al_saber_local(repo):
    """«¿qué días hay feria?» parece una búsqueda: si no hay locales, la contesta el saber local."""
    repo.upsert_saber_local({"pregunta": "¿Qué días hay feria?", "respuesta": "La feria es los jueves y domingos.",
                             "etiquetas": ["feria"], "activo": True})
    r = _preguntar(repo, "¿qué días hay feria?")
    assert r.intent == "saber_local" and "jueves" in r.texto


# ------------------------------------------------------------------ orden

def test_el_comercio_con_estrella_sale_antes_aunque_el_otro_este_abierto(repo):
    # El que no tiene estrella está ABIERTO (martes 11); el de estrella está en la siesta.
    _comercio(repo, "com-comun", "Deportes Común")
    _oferta(repo, "com-comun", "Zapatillas Nike Bs 250")
    _comercio(repo, "com-pro", "Deportes Pro", plan="destacado", plan_cortesia=True)
    _oferta(repo, "com-pro", "Zapatillas Nike Bs 300")
    r = _preguntar(repo, "dónde consigo zapatillas nike", ahora=MARTES_13)
    assert r.texto.index("Deportes Pro") < r.texto.index("Deportes Común")
    assert [f["nombre"] for f in r.fuentes] == ["Deportes Pro", "Deportes Común"]


def test_la_estrella_es_un_plan_pago_al_dia_no_un_plan_vencido(repo):
    _comercio(repo, "com-vencido", "Deportes Vencido", plan="destacado", paga_hasta="2026-08-01")
    _oferta(repo, "com-vencido", "Zapatillas Nike Bs 300")
    _comercio(repo, "com-aldia", "Deportes Al Día", plan="destacado", paga_hasta="2026-12-01")
    _oferta(repo, "com-aldia", "Zapatillas Nike Bs 300")
    _comercio(repo, "com-gratis", "Deportes Gratis")
    _oferta(repo, "com-gratis", "Zapatillas Nike Bs 300")
    r = _preguntar(repo, "dónde consigo zapatillas nike")
    assert r.texto.index("Deportes Al Día") < r.texto.index("Deportes Vencido")
    assert r.texto.index("Deportes Al Día") < r.texto.index("Deportes Gratis")


def test_sin_estrella_los_abiertos_van_antes(repo):
    _comercio(repo, "com-cerrado", "Deportes Cerrado", horario="Lun-Sáb 14:30-20:00")
    _oferta(repo, "com-cerrado", "Zapatillas Nike Bs 250")
    _comercio(repo, "com-abierto", "Deportes Abierto")
    _oferta(repo, "com-abierto", "Zapatillas Nike Bs 250")
    r = _preguntar(repo, "dónde consigo zapatillas nike")
    assert r.texto.index("Deportes Abierto") < r.texto.index("Deportes Cerrado")
    assert "cerrado" in r.texto.lower()


def test_la_estrella_de_la_busqueda_del_sitio_se_respeta(repo, monkeypatch):
    """Si el buscador del sitio ya trae `estrella`/`plan_orden`, no se recalcula."""
    _comercio(repo, "com-a", "Zapatería A", subcategoria="calzado", prod_obs_human="zapatillas")
    _comercio(repo, "com-b", "Zapatería B", subcategoria="calzado", prod_obs_human="zapatillas")
    original = repo.buscar_comercios
    monkeypatch.setattr(repo, "buscar_comercios", lambda *a, **k: [
        {**c, "estrella": c["id"] == "com-b", "plan_orden": 2 if c["id"] == "com-b" else 0}
        for c in original(*a, **k)])
    r = _preguntar(repo, "dónde consigo zapatillas")
    assert r.texto.index("Zapatería B") < r.texto.index("Zapatería A")


def test_maximo_cinco_resultados_y_sin_cifras(repo):
    for i in range(8):
        _comercio(repo, f"com-{i}", f"Deportes {i}")
        _oferta(repo, f"com-{i}", f"Zapatillas Nike modelo {i}")
    r = _preguntar(repo, "dónde consigo zapatillas nike")
    assert r.texto.count("• ") == 5 and len(r.fuentes) == 5
    # Cuántos locales hay es un dato del panel: ni «8» ni «más de» ni «resultados».
    assert not re.search(r"\b\d+ (comercios|locales|resultados|negocios)", r.texto)
    assert "8" not in r.texto.replace("59", "")
    assert "Más en el buscador" in r.texto


def test_nunca_precios_de_planes_ni_cifras_de_comercios(repo):
    _comercio(repo, "com-pro", "Deportes Pro", plan="pro", plan_cortesia=True)
    _oferta(repo, "com-pro", "Zapatillas Nike")
    r = _preguntar(repo, "dónde consigo zapatillas nike")
    assert "plan" not in r.texto.lower() and "400" not in r.texto and "140" not in r.texto


def test_si_el_comercio_no_tiene_whatsapp_no_se_inventa_uno(repo):
    _comercio(repo, "com-sinwa", "Deportes Sin WA", whatsapp=None)
    _oferta(repo, "com-sinwa", "Zapatillas Nike Bs 250")
    r = _preguntar(repo, "dónde consigo zapatillas nike")
    assert "Deportes Sin WA" in r.texto and "WhatsApp:" not in r.texto and "Ficha:" in r.texto


def test_los_servicios_siguen_igual(repo):
    """«¿Dónde hay un baño?» sigue siendo el rubro, no el texto."""
    repo.comercios["c-bano"] = {"id": "c-bano", "slug": "bano", "nombre": "Baño Plaza", "activo": True,
                                "rubro_slug": "banos", "subcategoria": "Baño público", "direccion": "Plaza"}
    r = _preguntar(repo, "¿dónde hay un baño?")
    assert r.intent == "buscar" and "Baño Plaza" in r.texto and "rubro=banos" in r.texto


def test_la_busqueda_se_hace_una_sola_vez_por_pregunta(repo, monkeypatch):
    _comercio(repo, "com-deportes-sur", "Deportes Sur")
    llamadas = []
    original = repo.list_ofertas_vigentes
    monkeypatch.setattr(repo, "list_ofertas_vigentes", lambda *a, **k: (llamadas.append(1), original(*a, **k))[1])
    _preguntar(repo, "dónde consigo un termo stanley")     # sin resultados: pasa por el Nivel 0 dos veces
    assert len(llamadas) == 1


def test_si_falla_la_lectura_de_ofertas_se_contesta_con_la_ficha(repo, monkeypatch):
    _comercio(repo, "com-zap", "Zapatería Luz", subcategoria="calzado", prod_obs_human="zapatillas")

    def _falla(*a, **k):
        raise RuntimeError("postgrest caído")
    monkeypatch.setattr(repo, "list_ofertas_vigentes", _falla)
    assert "Zapatería Luz" in _preguntar(repo, "dónde consigo zapatillas").texto


def test_el_modelo_ve_las_ofertas_que_coinciden(repo, monkeypatch):
    _comercio(repo, "com-deportes-sur", "Deportes Sur")
    _oferta(repo, "com-deportes-sur", "Zapatillas Nike Bs 250")
    monkeypatch.setattr(settings, "gemini_api_key", "x")
    prompts = []
    monkeypatch.setattr(asistente, "_gemini", lambda p: (prompts.append(p),
                        '{"respuesta": "Probá en Deportes Sur.", "seguro": true, "sugerencias": []}')[1])
    r = _preguntar(repo, "¿qué zapatillas nike me recomendás para correr?")
    assert r.nivel == 1 and "oferta vigente: Zapatillas Nike Bs 250" in prompts[0]


# ------------------------------------------------------------------ sinónimos

def test_variantes_de_apodos_y_equivalentes():
    assert sinonimos.variantes("zapas")[0] == "zapatilla"
    assert "teni" in sinonimos.variantes("zapatillas")            # singular, como el diccionario
    assert sinonimos.variantes("celu")[0] == "celular"
    assert sinonimos.variantes("zapatillas") and "zapas" not in sinonimos.variantes("zapatillas")
    assert sinonimos.variantes("heladera") == ["refrigerador"]
    assert sinonimos.variantes("cosa rara") == []
    assert sinonimos.variantes("polera", {"polera": "remera, camiseta"})[:2] == ["remera", "camiseta"]
    assert sinonimos.resolver_apodo("Compu") == "computadora" and sinonimos.resolver_apodo("mesa") is None


def test_zapa_no_trae_zapatos_ni_zapallos(repo):
    """El apodo se resuelve a una palabra entera: no es un prefijo suelto."""
    _comercio(repo, "com-verdu", "Verdulería", subcategoria="verduras", prod_obs_human="zapallos, papas")
    r = _preguntar(repo, "dónde consigo zapas")
    assert r.sin_respuesta and "Verdulería" not in r.texto


# ------------------------------------------------------------------ la consulta real (PostgREST)

class _Consulta:
    """Un cliente PostgREST de mentira que anota cada llamada de la cadena."""

    def __init__(self, filas):
        self.filas, self.llamadas = filas, []

    def __getattr__(self, nombre):
        def _llamar(*a, **k):
            self.llamadas.append((nombre, a, k))
            return self
        return _llamar

    def execute(self):
        from types import SimpleNamespace
        return SimpleNamespace(data=self.filas)


def _repo_supabase(filas, monkeypatch):
    from app.db.repository import SupabaseRepo
    repo = SupabaseRepo.__new__(SupabaseRepo)
    consulta = _Consulta(filas)
    repo._db = type("Db", (), {"table": lambda self, nombre: consulta.table(nombre)})()
    monkeypatch.setattr(SupabaseRepo, "get_ciudad_id", lambda self, slug: "ciu-1" if slug == "bermejo" else None)
    return repo, consulta


def test_la_consulta_pide_solo_lo_vigente_y_con_columnas_explicitas(monkeypatch):
    filas = [
        {"id": "p1", "titulo": "Zapatillas", "comercios": {"id": "c1", "nombre": "A", "suspendido": False}},
        {"id": "p2", "titulo": "Zapatillas", "comercios": {"id": "c2", "nombre": "B", "suspendido": True}},
    ]
    repo, q = _repo_supabase(filas, monkeypatch)
    out = repo.list_ofertas_vigentes("2026-09-15", "bermejo")
    assert [o["id"] for o in out] == ["p1"] and out[0]["comercio"]["nombre"] == "A" and "comercios" not in out[0]
    por_nombre = {}
    for nombre, args, kwargs in q.llamadas:
        por_nombre.setdefault(nombre, []).append((args, kwargs))
    assert por_nombre["table"][0][0] == ("publicaciones",)
    assert (("estado", "aprobado"), {}) in por_nombre["eq"] and (("activo", True), {}) in por_nombre["eq"]
    assert (("comercios.activo", True), {}) in por_nombre["eq"]
    assert (("comercios.ciudad_id", "ciu-1"), {}) in por_nombre["eq"]
    assert por_nombre["or_"][0][0] == ("vence_el.is.null,vence_el.gte.2026-09-15",)
    seleccion = por_nombre["select"][0][0][0]
    assert "*" not in seleccion and "codigo" not in seleccion
    assert "terminos_ia" in seleccion and "comercios!inner(" in seleccion


def test_una_ciudad_que_no_existe_no_trae_nada(monkeypatch):
    repo, q = _repo_supabase([{"id": "p1", "comercios": {"id": "c1"}}], monkeypatch)
    assert repo.list_ofertas_vigentes("2026-09-15", "atlantida") == [] and q.llamadas == []


# ── País contrario: «a Argentina» no es la entrada de «a Bolivia» (21/10/2026) ──
def test_traer_a_argentina_no_contesta_el_regimen_boliviano():
    from app.services import asistente
    filas = [
        {"pregunta": "¿Cuánto puedo traer a Bolivia sin pagar impuestos?",
         "respuesta": "Régimen de viajeros de la Aduana Nacional: hasta 1.000 dólares.", "etiquetas": ["aduana"]},
        {"pregunta": "¿Cuánto puedo llevar de vuelta a Argentina sin pagar?",
         "respuesta": "Según ARCA, por tierra la franquicia es de 300 dólares por mes.", "etiquetas": ["franquicia"]},
    ]
    fila, _ = asistente._mas_parecido(filas, "¿cuánto puedo traer a Argentina sin pagar impuestos?")
    assert fila and "ARCA" in fila["respuesta"]
    fila, _ = asistente._mas_parecido(filas, "¿cuánto puedo traer a Bolivia sin pagar impuestos?")
    assert fila and "1.000" in fila["respuesta"]
