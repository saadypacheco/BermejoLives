"""B1: visitas que llegan desde asistentes de IA (docs/visibilidad-buscadores-ia.md §3.11)."""
import pytest

from app.core.ai_sources import AI_SOURCES, classify_ai_source, summarize_ai_sources

CLAVES_DE_SIEMPRE = {"dias", "visitas", "personas", "por_dia", "top_rutas",
                     "top_referidos", "top_origenes", "embudo"}


@pytest.mark.parametrize("origen,referido,esperada", [
    ("chatgpt.com", None, "chatgpt"),
    (None, "chat.openai.com", "chatgpt"),
    (None, "perplexity.ai", "perplexity"),
    (None, "www.perplexity.ai", "perplexity"),
    (None, "gemini.google.com", "gemini"),
    (None, "bard.google.com", "gemini"),
    (None, "copilot.microsoft.com", "copilot"),
    ("bing.com/chat", None, "copilot"),
    (None, "claude.ai", "claude"),
    (None, "meta.ai", "meta_ai"),
    (None, "grok.com", "grok"),
    (None, "x.ai", "grok"),
    (None, "chat.deepseek.com", "deepseek"),
    (None, "chat.mistral.ai", "mistral"),
    ("mistral", None, "mistral"),            # utm_source sin TLD
    (None, "chat.mistral.ai", "mistral"),
    ("mistral", None, "mistral"),            # utm_source sin TLD
    (None, "you.com", "you"),
    (None, "phind.com", "phind"),
    (None, "duck.ai", "duckduckgo_ai"),
    ("https://ChatGPT.com/?utm_source=chatgpt.com", None, "chatgpt"),
    ("chatgpt", None, "chatgpt"),            # utm_source sin TLD
    ("perplexity", None, "perplexity"),
])
def test_reconoce_cada_asistente(origen, referido, esperada):
    assert classify_ai_source(origen, referido) == esperada


@pytest.mark.parametrize("origen,referido", [
    (None, None),
    ("", ""),
    (None, "google.com"),                    # AI Overviews caen acá: indistinguibles
    (None, "bing.com"),                      # Bing normal no es Copilot
    (None, "duckduckgo.com"),
    (None, "facebook.com"),
    (None, "x.com"),
    (None, "notchatgpt.com"),                # el sufijo exige límite de punto
    (None, "wix.ai"),
    ("volante-x", None),
    ("volante-x", "google.com"),
])
def test_lo_que_no_es_un_asistente_da_none(origen, referido):
    assert classify_ai_source(origen, referido) is None


def test_el_origen_manda_sobre_el_referido():
    assert classify_ai_source("claude.ai", "perplexity.ai") == "claude"
    assert classify_ai_source("volante-x", "perplexity.ai") == "perplexity"


def test_cubre_todos_los_asistentes_pedidos():
    assert set(AI_SOURCES) >= {"chatgpt", "perplexity", "gemini", "copilot", "claude",
                               "meta_ai", "grok", "deepseek", "mistral", "you", "phind", "duckduckgo_ai"}


def test_el_resumen_junta_visitas_personas_fichas_y_rutas():
    filas = [
        {"ruta": "/comercios/a", "sesion": "s1", "origen": "chatgpt.com"},
        {"ruta": "/comercios/b", "sesion": "s1", "origen": "chatgpt.com"},
        {"ruta": "/", "sesion": "s2", "referido": "chat.openai.com"},
        {"ruta": "/bermejo/ropa", "sesion": "s3", "referido": "perplexity.ai"},
        {"ruta": "/", "sesion": "s4", "referido": "google.com"},      # no cuenta
        {"ruta": "/", "sesion": "s5"},                                # no cuenta
    ]
    r = summarize_ai_sources(filas)
    assert [x["source"] for x in r] == ["chatgpt", "perplexity"]
    chat = r[0]
    assert chat["visits"] == 3 and chat["people"] == 2 and chat["business_views"] == 2
    assert [t["ruta"] for t in chat["top_routes"]] == ["/comercios/a", "/comercios/b", "/"]
    assert r[1] == {"source": "perplexity", "visits": 1, "people": 1, "business_views": 0,
                    "top_routes": [{"ruta": "/bermejo/ropa", "n": 1}]}


def test_el_resumen_corta_las_rutas_en_tres():
    filas = [{"ruta": f"/r{i}", "sesion": "s", "origen": "claude.ai"} for i in range(6)]
    assert len(summarize_ai_sources(filas)[0]["top_routes"]) == 3


def test_sin_visitas_de_ia_la_lista_va_vacia():
    assert summarize_ai_sources([]) == []


# ── de punta a punta: /visita -> /admin/visitas (repo de prueba) ────────────────
def test_endpoint_admin_visitas_trae_ai_sources_y_conserva_las_claves(client, repo, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    client.post("/visita", json={"ruta": "/comercios/x", "sesion": "sesion-aaa111",
                                 "origen": "chatgpt.com", "primera": True})
    client.post("/visita", json={"ruta": "/", "sesion": "sesion-bbb222",
                                 "referido": "perplexity.ai", "primera": True})
    client.post("/visita", json={"ruta": "/", "sesion": "sesion-ccc333", "referido": "google.com"})
    d = client.get("/admin/visitas", headers=h).json()
    assert CLAVES_DE_SIEMPRE <= set(d)
    por_fuente = {x["source"]: x for x in d["ai_sources"]}
    assert set(por_fuente) == {"chatgpt", "perplexity"}
    assert por_fuente["chatgpt"]["business_views"] == 1
    assert d["visitas"] == 3


# ── el resumen real sobre lo que devuelve la función SQL ────────────────────────
class _RepoConRpc:
    """Lo que devuelve `site_metrics_summary` (0193): filas YA agrupadas por la base."""

    def site_metrics_summary(self, desde, hasta, ciudad=None):
        return {
            "totals": {"pageviews": 3, "sessions": 3, "first_pages": 3},
            "ai_groups": [
                {"origen": "chatgpt.com", "referido": None, "n": 1, "people": 1, "fichas": 1},
                {"origen": None, "referido": "perplexity.ai", "n": 1, "people": 1, "fichas": 0},
                {"origen": None, "referido": "google.com", "n": 1, "people": 1, "fichas": 0},
            ],
            "ai_routes": [
                {"origen": "chatgpt.com", "referido": None, "ruta": "/comercios/a", "n": 1},
                {"origen": None, "referido": "perplexity.ai", "ruta": "/", "n": 1},
            ],
            "referrers_raw": [{"referido": "perplexity.ai", "origen": None, "n": 1},
                              {"referido": "google.com", "origen": None, "n": 1},
                              {"referido": None, "origen": "chatgpt.com", "n": 1}],
        }

    def last_visit_at(self):
        return None


def test_el_resumen_suma_ai_sources_sin_tocar_las_claves_de_siempre():
    from app.services import site_metrics
    r = site_metrics.resumen_del_sitio(_RepoConRpc(), 30)
    assert CLAVES_DE_SIEMPRE <= set(r)
    assert r["visitas"] == 3 and r["personas"] == 3
    assert {x["referido"] for x in r["top_referidos"]} == {"google.com", "perplexity.ai"}
    assert {x["source"]: x["visits"] for x in r["ai_sources"]} == {"chatgpt": 1, "perplexity": 1}
    assert {x["source"]: x["business_views"] for x in r["ai_sources"]} == {"chatgpt": 1, "perplexity": 0}
    assert {(x["kind"], x["name"]) for x in r["referrers"]} == {("ai", "chatgpt"), ("ai", "perplexity"), ("search", "google")}
