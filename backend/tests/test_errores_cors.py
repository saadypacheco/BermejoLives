"""Un error 500 tiene que llegar como 500, no disfrazado de problema de CORS.

FastAPI monta el handler de excepciones POR FUERA del CORSMiddleware, así que
las respuestas 500 salen sin cabeceras CORS y el navegador las reporta como
"blocked by CORS policy". El error real queda invisible y se termina buscando un
problema de configuración que no existe — nos costó dos diagnósticos errados.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db.repository import get_repo
from app.main import app

ORIGEN = "https://uruku.bo"


@pytest.fixture
def client_500(repo):
    """TestClient que DEVUELVE el 500 en vez de re-lanzar la excepción, que es
    lo que hace un navegador real."""
    app.dependency_overrides[get_repo] = lambda: repo
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _romper(repo):
    return patch.object(repo, "list_todos_comercios", side_effect=RuntimeError("boom"))


def test_el_500_conserva_las_cabeceras_cors(client_500, repo, admin_token):
    with patch("app.main._cors_origins", return_value=[ORIGEN]), _romper(repo):
        r = client_500.get("/moderacion/comercios?todos=true",
                           headers={"Authorization": f"Bearer {admin_token}", "Origin": ORIGEN})

    assert r.status_code == 500
    assert r.headers.get("access-control-allow-origin") == ORIGEN, (
        "sin esta cabecera el navegador muestra un error de CORS y esconde el 500"
    )


def test_no_se_habilita_un_origen_no_permitido(client_500, repo, admin_token):
    with patch("app.main._cors_origins", return_value=[ORIGEN]), _romper(repo):
        r = client_500.get("/moderacion/comercios?todos=true",
                           headers={"Authorization": f"Bearer {admin_token}",
                                    "Origin": "https://sitio-ajeno.com"})

    assert r.status_code == 500
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_sin_origin_no_agrega_nada(client_500, repo, admin_token):
    """Llamadas server-to-server o por curl: no hay origen que reflejar."""
    with patch("app.main._cors_origins", return_value=[ORIGEN]), _romper(repo):
        r = client_500.get("/moderacion/comercios?todos=true",
                           headers={"Authorization": f"Bearer {admin_token}"})

    assert r.status_code == 500
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}
