"""El tope de publicaciones guardadas y los precios que no se muestran.

Dos decisiones del 4/10/2026 (docs/planes-tope-publicaciones.md):

1. Un comercio guarda como máximo N publicaciones (70 por defecto, por plan).
   Cuando entra una más, la más vieja se archiva y SU FOTO SE BORRA DEL DISCO.
2. Los precios de los planes no se muestran: ni en los avisos ni en el asistente.

Lo que más se cuida acá es lo que NO puede pasar: que se borre un archivo que no
era de la publicación (una portada, la foto de otro, algo fuera del volumen de
fotos), y que un problema de limpieza le rompa la publicación al comerciante.
"""
import re
from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.services import asistente, difusion, ingest, planes

BASE_FOTOS = "https://api.test/fotos"


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _hoy(dias=0):
    return (date.today() + timedelta(days=dias)).isoformat()


class _Volumen:
    """El volumen de fotos en un tmp, con la URL pública que le corresponde."""

    def __init__(self, raiz):
        self.raiz = raiz

    def foto(self, relativa: str) -> tuple[str, "object"]:
        """Crea el archivo y devuelve (url pública, ruta en disco)."""
        ruta = self.raiz / relativa
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(b"jpg")
        return f"{BASE_FOTOS}/{relativa}", ruta


@pytest.fixture
def volumen(tmp_path, monkeypatch):
    raiz = tmp_path / "volumen"
    raiz.mkdir()
    monkeypatch.setattr(settings, "fotos_dir", str(raiz))
    monkeypatch.setattr(settings, "fotos_public_base_url", BASE_FOTOS)
    return _Volumen(raiz)


def _pub(repo, comercio, minutos, imagen_url=None, estado="aprobado", **extra):
    """Una publicación creada hace `minutos` minutos DESDE UN PUNTO FIJO: a más
    minutos, más nueva. El orden de inserción no tiene por qué coincidir."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return repo.insert_publicacion_directa({
        "comercio_id": comercio["id"], "tipo": "oferta", "titulo": f"of {minutos}",
        "estado": estado, "imagen_url": imagen_url,
        "created_at": (base + timedelta(minutes=minutos)).isoformat(), **extra})


def _comercio(repo, plan="publica", **kw):
    return repo.seed_comercio(slug="local", nombre="Local", plan=plan, **kw)


def _activas(repo, comercio):
    return [p for p in repo.publicaciones
            if p["comercio_id"] == comercio["id"] and p["activo"]]


# ═══════════════════════════════════════════════ archivar al pasar el tope

def test_con_70_activas_y_una_mas_queda_en_70_y_la_mas_vieja_se_archiva_con_su_foto(repo, volumen):
    """Criterio 1 de la spec, con los números reales: 70 activas, entra la 71."""
    c = _comercio(repo)
    url_vieja, ruta_vieja = volumen.foto("local/ofertas/vieja.jpg")
    url_nueva, ruta_nueva = volumen.foto("local/ofertas/nueva.jpg")
    vieja = _pub(repo, c, 0, url_vieja)
    for i in range(1, 70):
        _pub(repo, c, i)
    _pub(repo, c, 70, url_nueva)             # la 71: la que acaba de entrar
    assert len(_activas(repo, c)) == 71

    assert planes.archivar_excedentes(repo, c) == 1

    assert len(_activas(repo, c)) == 70
    assert vieja["activo"] is False          # la fila queda: soft-delete
    assert not ruta_vieja.exists()           # la foto, no
    assert ruta_nueva.exists()               # la nueva no se toca


def test_archiva_por_created_at_y_no_por_orden_de_insercion(repo, volumen):
    """La base devuelve por `created_at`; la que se insertó última puede ser la
    más vieja (una carga tardía, un reintento). Archivar la última insertada
    sacaría del feed lo que el comerciante acaba de mandar."""
    repo.upsert_plan("publica", {"publicaciones_guardadas": 3})
    c = _comercio(repo)
    nuevas = [_pub(repo, c, m) for m in (50, 40, 30)]
    la_mas_vieja = _pub(repo, c, 1)          # insertada ÚLTIMA, pero es la más vieja

    assert planes.archivar_excedentes(repo, c) == 1

    assert la_mas_vieja["activo"] is False
    assert all(p["activo"] for p in nuevas)


def test_si_el_tope_baja_se_archivan_todas_las_que_sobran_de_una_vez(repo, volumen):
    repo.upsert_plan("publica", {"publicaciones_guardadas": 2})
    c = _comercio(repo)
    pubs = [_pub(repo, c, m) for m in range(5)]

    assert planes.archivar_excedentes(repo, c) == 3

    assert [p["activo"] for p in pubs] == [False, False, False, True, True]


def test_cuentan_todos_los_estados_no_solo_las_aprobadas(repo, volumen):
    """Todas ocupan disco: una pendiente o una rechazada también tiene su foto."""
    repo.upsert_plan("publica", {"publicaciones_guardadas": 2})
    c = _comercio(repo)
    rechazada = _pub(repo, c, 1, estado="rechazado")
    pendiente = _pub(repo, c, 2, estado="pendiente")
    aprobada = _pub(repo, c, 3, estado="aprobado")

    assert planes.archivar_excedentes(repo, c) == 1
    assert rechazada["activo"] is False
    assert pendiente["activo"] and aprobada["activo"]


def test_las_ya_archivadas_y_las_de_otro_comercio_no_cuentan(repo, volumen):
    """Multi-tenant: el tope de un comercio no se llena con lo de otro."""
    repo.upsert_plan("publica", {"publicaciones_guardadas": 2})
    c = _comercio(repo)
    otro = repo.seed_comercio(slug="otro", nombre="Otro", plan="publica")
    for m in range(10):
        _pub(repo, otro, m)
    archivada = _pub(repo, c, 0)
    archivada["activo"] = False
    _pub(repo, c, 1)
    _pub(repo, c, 2)

    assert planes.archivar_excedentes(repo, c) == 0
    assert len(_activas(repo, otro)) == 10   # al otro no se le tocó nada


def test_el_tope_es_por_plan(repo, volumen):
    repo.upsert_plan("publica", {"publicaciones_guardadas": 1})
    repo.upsert_plan("pro", {"publicaciones_guardadas": 5})
    chico = _comercio(repo, plan="publica")
    grande = repo.seed_comercio(slug="grande", nombre="G", plan="pro")
    for m in range(3):
        _pub(repo, chico, m)
        _pub(repo, grande, m)

    assert planes.archivar_excedentes(repo, chico) == 2
    assert planes.archivar_excedentes(repo, grande) == 0


# ═══════════════════════════════════════════════ sin tope = no se archiva

def test_con_tope_null_no_se_archiva_nada(repo, volumen):
    """Criterio 3: NULL es "sin tope", no "cero"."""
    repo.upsert_plan("publica", {"publicaciones_guardadas": None})
    c = _comercio(repo)
    url, ruta = volumen.foto("local/ofertas/x.jpg")
    _pub(repo, c, 0, url)
    for m in range(1, 200):
        _pub(repo, c, m)

    assert planes.archivar_excedentes(repo, c) == 0
    assert len(_activas(repo, c)) == 200
    assert ruta.exists()


def test_un_tope_cero_o_negativo_no_vacia_el_comercio(repo, volumen):
    """La base lo impide con un CHECK; si aun así llegara, archivar contra un 0
    dejaría archivada la publicación que acaba de entrar."""
    repo.upsert_plan("publica", {"publicaciones_guardadas": 0})
    c = _comercio(repo)
    _pub(repo, c, 0)
    assert planes.archivar_excedentes(repo, c) == 0
    assert len(_activas(repo, c)) == 1


# ═══════════════════════════════════════════════ qué archivos se borran

def _con_tope_uno(repo):
    repo.upsert_plan("publica", {"publicaciones_guardadas": 1})
    return _comercio(repo)


def test_una_foto_con_url_externa_nunca_se_borra(repo, volumen):
    """Criterio 2. Un producto de la tienda, un link: no es nuestro. Aunque en
    el disco haya un archivo con el mismo nombre, no se toca."""
    c = _con_tope_uno(repo)
    _, ruta_homonima = volumen.foto("local/ofertas/x.jpg")
    _pub(repo, c, 0, "https://otro-sitio.com/fotos/local/ofertas/x.jpg")
    _pub(repo, c, 1)

    assert planes.archivar_excedentes(repo, c) == 1
    assert ruta_homonima.exists()


def test_una_url_que_solo_se_parece_a_la_base_no_cuenta_como_propia(repo, volumen):
    """`.../fotos-viejas/...` empieza igual que `.../fotos` y no es lo mismo."""
    c = _con_tope_uno(repo)
    _, ruta = volumen.foto("local/ofertas/x.jpg")
    _pub(repo, c, 0, "https://api.test/fotos-viejas/local/ofertas/x.jpg")
    _pub(repo, c, 1)

    assert planes.archivar_excedentes(repo, c) == 1
    assert ruta.exists()


def test_una_foto_que_otra_publicacion_activa_sigue_usando_no_se_borra(repo, volumen):
    """Criterio 2. Borrarla rompería la foto de la que sigue mostrándola."""
    c = _con_tope_uno(repo)
    url, ruta = volumen.foto("local/ofertas/compartida.jpg")
    vieja = _pub(repo, c, 0, url)
    _pub(repo, c, 1, url)                    # la nueva reutiliza la misma foto

    assert planes.archivar_excedentes(repo, c) == 1
    assert vieja["activo"] is False
    assert ruta.exists()


def test_una_foto_que_usa_otro_comercio_tampoco_se_borra(repo, volumen):
    c = _con_tope_uno(repo)
    otro = repo.seed_comercio(slug="otro", nombre="Otro", plan="publica")
    url, ruta = volumen.foto("local/ofertas/prestada.jpg")
    _pub(repo, c, 0, url)
    _pub(repo, otro, 0, url)
    _pub(repo, c, 1)

    planes.archivar_excedentes(repo, c)
    assert ruta.exists()


def test_si_la_otra_que_usaba_la_foto_ya_estaba_archivada_si_se_borra(repo, volumen):
    """"Otra activa": una archivada no la muestra, no hay a quién romperle nada."""
    c = _con_tope_uno(repo)
    url, ruta = volumen.foto("local/ofertas/x.jpg")
    _pub(repo, c, 0, url)
    previa = _pub(repo, c, 1, url)
    previa["activo"] = False
    _pub(repo, c, 2)

    assert planes.archivar_excedentes(repo, c) == 1
    assert not ruta.exists()


@pytest.mark.parametrize("relativa", [
    "local/ofertas/../../../secreto.jpg",        # `..` a secas
    "local/ofertas/%2e%2e/%2e%2e/%2e%2e/secreto.jpg",   # codificado: llega a disco igual
    "../secreto.jpg",
    "local/ofertas/..%2f..%2f..%2fsecreto.jpg",
    "local\\ofertas\\..\\..\\..\\secreto.jpg",   # separadores de Windows
])
def test_una_ruta_con_punto_punto_no_sale_del_directorio_de_fotos(repo, volumen, tmp_path, relativa):
    """La URL la escribe, en el peor caso, un comerciante (el `imagen_url` del
    panel es texto libre). Lo que se pegue ahí no puede apuntar fuera del
    volumen: un `..` que llegue a `unlink` borra cualquier archivo del servidor."""
    secreto = tmp_path / "secreto.jpg"
    secreto.write_bytes(b"no me toques")
    c = _con_tope_uno(repo)
    _pub(repo, c, 0, f"{BASE_FOTOS}/{relativa}")
    _pub(repo, c, 1)

    assert planes.archivar_excedentes(repo, c) == 1     # se archiva igual
    assert secreto.exists()


def test_un_enlace_simbolico_que_apunta_afuera_no_se_sigue(repo, volumen, tmp_path):
    secreto = tmp_path / "afuera.jpg"
    secreto.write_bytes(b"no me toques")
    carpeta = volumen.raiz / "local" / "ofertas"
    carpeta.mkdir(parents=True)
    try:
        (carpeta / "enlace.jpg").symlink_to(secreto)
    except (OSError, NotImplementedError):
        pytest.skip("este sistema no deja crear enlaces simbólicos")
    c = _con_tope_uno(repo)
    _pub(repo, c, 0, f"{BASE_FOTOS}/local/ofertas/enlace.jpg")
    _pub(repo, c, 1)

    planes.archivar_excedentes(repo, c)
    assert secreto.exists()


def test_la_portada_y_las_fotos_de_galeria_no_se_borran_aunque_esten_bajo_la_base(repo, volumen):
    """El `imagen_url` de una publicación hecha desde el panel es texto libre: el
    comerciante puede pegar la URL de su portada. Borrarla al archivar la
    publicación dejaría su ficha con una foto rota. Sólo se borra lo que nace
    de una publicación: `<slug>/ofertas/<archivo>`."""
    c = _con_tope_uno(repo)
    url, ruta = volumen.foto("local/portada123.jpg")
    _pub(repo, c, 0, url)
    _pub(repo, c, 1)

    planes.archivar_excedentes(repo, c)
    assert ruta.exists()


def test_un_archivo_que_ya_no_existe_no_es_un_error(repo, volumen):
    c = _con_tope_uno(repo)
    vieja = _pub(repo, c, 0, f"{BASE_FOTOS}/local/ofertas/fantasma.jpg")
    _pub(repo, c, 1)

    assert planes.archivar_excedentes(repo, c) == 1
    assert vieja["activo"] is False


def test_una_url_no_canonica_archiva_la_publicacion_pero_no_borra_la_foto(repo, volumen):
    """La guarda de «otra publicación la usa» compara la URL tal cual. Una
    variante (`?`, `#`, `%xx`) no coincidiría con la de otra fila, así que con
    una variante no se borra nada: la publicación se archiva igual."""
    for sufijo in ("?v=2", "#a"):
        repo.publicaciones.clear()
        c = _con_tope_uno(repo)
        url, ruta = volumen.foto("local/ofertas/x.jpg")
        vieja = _pub(repo, c, 0, url + sufijo)
        _pub(repo, c, 1)

        assert planes.archivar_excedentes(repo, c) == 1
        assert vieja["activo"] is False
        assert ruta.exists(), sufijo


def test_un_comercio_no_puede_hacer_borrar_la_foto_de_la_oferta_de_otro(repo, volumen):
    """El ataque: el comercio A le pone a su publicación más vieja la URL de una
    oferta del comercio B, apenas modificada para que no coincida con la de B, y
    publica una más. Antes eso borraba la foto de B, que seguía publicada."""
    repo.upsert_plan("publica", {"publicaciones_guardadas": 1})
    url_b, ruta_b = volumen.foto("otro/ofertas/abc.jpg")
    b = repo.seed_comercio(slug="otro", nombre="Otro", plan="publica")
    _pub(repo, b, 0, url_b)
    a = _comercio(repo)

    for variante in (url_b, url_b + "?x=1", url_b.replace("otro/", "otro%2F"), url_b + "#a"):
        vieja = _pub(repo, a, 0, variante)
        _pub(repo, a, 1)
        planes.archivar_excedentes(repo, a)
        assert vieja["activo"] is False
        assert ruta_b.exists(), variante


def test_una_foto_de_producto_bajo_una_carpeta_ofertas_no_se_borra(repo, volumen):
    """Un comercio con slug «ofertas» guarda sus productos en
    `productos/ofertas/…`: la forma tiene que ser exactamente
    `<slug>/ofertas/<archivo>`, con el slug del comercio."""
    repo.upsert_plan("publica", {"publicaciones_guardadas": 1})
    c = repo.seed_comercio(slug="ofertas", nombre="Ofertas", plan="publica")
    url, ruta = volumen.foto("productos/ofertas/p.jpg")
    _pub(repo, c, 0, url)
    _pub(repo, c, 1)

    planes.archivar_excedentes(repo, c)
    assert ruta.exists()


def test_bajar_mucho_el_tope_archiva_de_a_poco(repo):
    """Un 7 tipeado en vez de 70 no puede borrar 63 fotos de una. Se archivan
    como máximo 5 por publicación nueva y el comercio llega al tope de a poco."""
    repo.upsert_plan("publica", {"publicaciones_guardadas": 7})
    c = _comercio(repo)
    for m in range(70):
        _pub(repo, c, m)

    assert planes.archivar_excedentes(repo, c) == 5
    assert len(_activas(repo, c)) == 65


# ═══════════════════════════════════════════════ archivar nunca rompe

def test_si_falla_archivar_no_lanza_y_no_se_borra_la_foto(repo, volumen, monkeypatch):
    """La publicación sigue activa, así que su foto tiene que seguir en el disco."""
    c = _con_tope_uno(repo)
    url, ruta = volumen.foto("local/ofertas/x.jpg")
    vieja = _pub(repo, c, 0, url)
    _pub(repo, c, 1)

    def _explota(pub_id):
        raise RuntimeError("la base se cayó")
    monkeypatch.setattr(repo, "archivar_publicacion", _explota)

    assert planes.archivar_excedentes(repo, c) == 0      # no lanza
    assert vieja["activo"] is True
    assert ruta.exists()


def test_si_falla_leer_las_activas_no_lanza(repo, monkeypatch):
    c = _con_tope_uno(repo)

    def _explota(comercio_id):
        raise RuntimeError("timeout")
    monkeypatch.setattr(repo, "publicaciones_activas_de", _explota)

    assert planes.archivar_excedentes(repo, c) == 0


def test_si_falla_borrar_el_archivo_la_publicacion_igual_queda_archivada(repo, volumen, monkeypatch):
    from pathlib import Path

    c = _con_tope_uno(repo)
    url, _ = volumen.foto("local/ofertas/x.jpg")
    vieja = _pub(repo, c, 0, url)
    _pub(repo, c, 1)

    def _sin_permiso(self, missing_ok=False):
        raise PermissionError("sin permiso")
    monkeypatch.setattr(Path, "unlink", _sin_permiso)

    assert planes.archivar_excedentes(repo, c) == 1
    assert vieja["activo"] is False


def test_si_falla_descartar_la_difusion_igual_se_borra_la_foto(repo, volumen, monkeypatch):
    """Los pasos son independientes: uno que falla no deja a los otros sin hacer."""
    c = _con_tope_uno(repo)
    url, ruta = volumen.foto("local/ofertas/x.jpg")
    _pub(repo, c, 0, url)
    _pub(repo, c, 1)

    def _explota(*a, **k):
        raise RuntimeError("cola caída")
    monkeypatch.setattr(repo, "descartar_difusion_de", _explota)

    assert planes.archivar_excedentes(repo, c) == 1
    assert not ruta.exists()


def test_un_fallo_al_archivar_no_rompe_la_publicacion_por_whatsapp(repo, monkeypatch):
    """La publicación nueva sale igual: el comerciante no ve un error por un
    problema de limpieza, y no manda la misma oferta dos veces."""
    monkeypatch.setattr(ingest, "_avisar", lambda chat, texto: True)

    def _explota(comercio_id):
        raise RuntimeError("la base se cayó")
    monkeypatch.setattr(repo, "publicaciones_activas_de", _explota)
    c = _comercio(repo, confiable=True)
    repo.vincular_grupo_comercio("120363@g.us", c["id"], "G", "admin", "test")

    r = ingest.handle_message({"event": "message", "session": "default", "payload": {
        "id": "m1", "from": "120363@g.us", "participant": "59170000009@c.us",
        "body": "oferta nueva", "type": "text", "fromMe": False}}, repo)

    assert r["captured"] is True
    assert len(repo.publicaciones) == 1


# ═══════════════════════════════════════════════ la cola de difusión

def test_una_archivada_que_estaba_en_la_cola_de_difusion_se_descarta_con_motivo(repo, volumen):
    """Criterio 6."""
    c = _con_tope_uno(repo)
    vieja = _pub(repo, c, 0)
    otra_cosa = _pub(repo, c, 1)
    # Directo a la cola: `difusion.encolar` filtra los destinos por plan y por la
    # llave de WAHA, y acá lo que se prueba es el descarte, no esa elección.
    repo.encolar_difusion(vieja["id"], ["facebook", "instagram"])
    repo.encolar_difusion(otra_cosa["id"], ["facebook"])
    assert len(repo.difusion_pendientes(50)) == 3

    planes.archivar_excedentes(repo, c)

    de_la_vieja = [f for f in repo.difusion if f["publicacion_id"] == vieja["id"]]
    assert de_la_vieja and all(f["estado"] == "omitido" for f in de_la_vieja)
    assert all("archivada" in f["motivo"] for f in de_la_vieja)
    # la que NO se archivó sigue esperando su turno
    de_la_otra = [f for f in repo.difusion if f["publicacion_id"] == otra_cosa["id"]]
    assert de_la_otra and all(f["estado"] == "pendiente" for f in de_la_otra)


def test_lo_que_ya_se_envio_no_se_reescribe(repo, volumen):
    """Una fila 'enviado' es historia: dice qué salió y cuándo."""
    c = _con_tope_uno(repo)
    vieja = _pub(repo, c, 0)
    repo.encolar_difusion(vieja["id"], ["facebook"])
    repo.difusion[0].update({"estado": "enviado", "motivo": None})
    _pub(repo, c, 1)

    planes.archivar_excedentes(repo, c)
    assert repo.difusion[0]["estado"] == "enviado"


def test_un_reintento_a_mano_de_una_archivada_no_la_publica_en_las_redes(repo, volumen, monkeypatch):
    """La fila quedó en error antes de archivarse; alguien aprieta 'reintentar'.
    La publicación sigue 'aprobado' pero archivada: no puede salir."""
    monkeypatch.setattr(difusion, "configurado", lambda d: True)
    enviados = []
    monkeypatch.setattr(difusion, "enviar", lambda d, t, i: enviados.append(d))
    c = _con_tope_uno(repo)
    vieja = _pub(repo, c, 0)
    repo.encolar_difusion(vieja["id"], ["facebook"])
    repo.difusion[0]["estado"] = "error"
    _pub(repo, c, 1)
    planes.archivar_excedentes(repo, c)

    r = difusion.procesar(repo, repo.difusion[0])

    assert r["estado"] == "omitido"
    assert enviados == []


# ═══════════════════════════════════════════════ se aplica en TODOS los caminos

@pytest.fixture
def espia(monkeypatch):
    """Cuenta las veces que cada camino llama al archivado, sin ejecutarlo."""
    llamadas = []
    monkeypatch.setattr(planes, "archivar_excedentes",
                        lambda repo, comercio: llamadas.append(comercio["id"]) or 0)
    return llamadas


def test_la_ingesta_por_whatsapp_aplica_el_tope(repo, volumen):
    repo.upsert_plan("publica", {"publicaciones_guardadas": 3})
    c = _comercio(repo, confiable=True)
    viejas = [_pub(repo, c, m) for m in range(3)]
    repo.vincular_grupo_comercio("120363@g.us", c["id"], "G", "admin", "test")

    ingest.handle_message({"event": "message", "session": "default", "payload": {
        "id": "m1", "from": "120363@g.us", "participant": "59170000009@c.us",
        "body": "oferta nueva", "type": "text", "fromMe": False}}, repo)

    assert len(_activas(repo, c)) == 3
    assert viejas[0]["activo"] is False


def test_el_explorador_tambien_aplica_el_tope(repo, volumen, monkeypatch):
    """El disco es el mismo: lo que sube URUKU también lo llena."""
    monkeypatch.setattr(settings, "wa_numeros_explorador", "59170000555", raising=False)
    repo.upsert_plan("gratis", {"publicaciones_guardadas": 2})
    c = repo.seed_comercio(id="com-e1", slug="am", nombre="A&M", codigo="AQP5", plan="gratis")
    viejas = [_pub(repo, c, m) for m in range(2)]

    ingest.handle_message({"event": "message", "session": "obs@c.us", "payload": {
        "id": "wa-e1", "from": "59170000555@c.us", "fromMe": False,
        "body": "URUKU-AQP5 zapatilla Bs 180", "type": "text", "timestamp": 1700000000}}, repo)

    assert len(_activas(repo, c)) == 2
    assert viejas[0]["activo"] is False


def test_el_explorador_no_paga_cuota_ni_se_le_cobra_al_comercio(repo, volumen, monkeypatch):
    """La cuota y el cobro son de cuando publica el comercio, no URUKU."""
    monkeypatch.setattr(settings, "wa_numeros_explorador", "59170000555", raising=False)
    c = repo.seed_comercio(id="com-e1", slug="am", nombre="A&M", codigo="AQP5", plan="publica")
    for m in range(30):                       # pasada la cuota de 25
        _pub(repo, c, m)
    antes = len(repo.publicaciones)

    ingest.handle_message({"event": "message", "session": "obs@c.us", "payload": {
        "id": "wa-e2", "from": "59170000555@c.us", "fromMe": False,
        "body": "URUKU-AQP5 remera Bs 90", "type": "text", "timestamp": 1700000000}}, repo)

    assert len(repo.publicaciones) == antes + 1
    assert repo.cargos_extra == []


def test_publicar_desde_la_cuenta_aplica_el_tope(client, repo, volumen):
    from tests.conftest import comercio_token

    repo.upsert_plan("publica", {"publicaciones_guardadas": 2})
    c = repo.seed_comercio(id="com-t", slug="t", nombre="T", plan="publica", confiable=True)
    viejas = [_pub(repo, c, m) for m in range(2)]

    r = client.post("/comercio/publicar", json={"tipo": "oferta", "titulo": "nueva"},
                    headers=_h(comercio_token("com-t")))

    assert r.status_code == 200, r.text
    assert len(_activas(repo, c)) == 2
    assert viejas[0]["activo"] is False


def test_destacar_un_producto_aplica_el_tope_pero_no_la_cuota(client, repo, volumen):
    from tests.conftest import comercio_token

    repo.upsert_plan("publica", {"publicaciones_guardadas": 2})
    c = repo.seed_comercio(id="com-t", slug="t", nombre="T", plan="publica", whatsapp="591700")
    h = _h(comercio_token("com-t"))
    ref_id = client.post("/comercio/productos", headers=h,
                         data={"titulo": "Remera", "precio": "120", "moneda": "ARS",
                               "categoria_slug": "ropa"}).json()["producto_ref"]["id"]
    # pasado de la cuota mensual (25) y con el tope pasado por una
    for m in range(26):
        _pub(repo, c, m)

    r = client.post(f"/comercio/productos/{ref_id}/destacar", headers=h)

    assert r.status_code == 200, r.text         # destacar no tiene cuota
    assert repo.cargos_extra == []              # y su costo es otro: no es el extra
    activas = _activas(repo, c)
    # El destacado no cuenta para el tope ni se archiva: lleva un costo que se
    # cobra con la suscripción. Las ofertas comunes bajan de a 5 hacia el tope.
    assert any(p.get("producto_ref_id") == ref_id for p in activas)
    assert len([p for p in activas if not p.get("producto_ref_id")]) == 21


def test_un_destacado_de_producto_nunca_se_archiva(repo):
    repo.upsert_plan("publica", {"publicaciones_guardadas": 1})
    c = _comercio(repo)
    destacado = _pub(repo, c, 0, producto_ref_id="ref-1", costo=1000, cobrado=False)
    _pub(repo, c, 1)
    _pub(repo, c, 2)

    planes.archivar_excedentes(repo, c)
    assert destacado["activo"] is True


def test_el_video_del_alta_de_campo_llama_al_tope(client, repo, espia):
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="JPEG")
    buf.seek(0)
    token = client.post("/auth/campo/login", json={
        "email": "agente@bermejolive.com", "password": "campo1234"}).json()["access_token"]

    r = client.post("/campo/comercio", headers=_h(token),
                    data={"nombre": "Gomería X", "whatsapp": "59170002222",
                          "rubro_slugs": ["gomeria"], "modalidad": "minorista",
                          "lat": "-22.7361", "lng": "-64.3433",
                          "video_url": "https://www.tiktok.com/@x/video/1"},
                    files={"foto": ("t.jpg", buf, "image/jpeg")})

    assert r.status_code == 200, r.text
    assert len(espia) == 1                      # una vez, por el comercio recién creado
    assert any(p["tipo"] == "video" for p in repo.publicaciones)


# ═══════════════════════════════════════════════ cuota en /comercio/publicar

def _publicar_n(repo, comercio, n, **kw):
    for i in range(n):
        repo.insert_publicacion_directa({
            "comercio_id": comercio["id"], "tipo": "oferta", "titulo": f"of {i}",
            "estado": "aprobado", "created_at": _hoy(0), **kw})


def _post_publicar(client, comercio_id, **extra):
    from tests.conftest import comercio_token

    return client.post("/comercio/publicar",
                       json={"tipo": "oferta", "titulo": "una más", **extra},
                       headers=_h(comercio_token(comercio_id)))


def test_publicar_pasada_la_cuota_sale_cobra_y_trae_el_aviso(client, repo):
    """Criterio 4. La respuesta lleva el aviso: con WAHA en sólo lectura es el
    único canal por el que el comerciante se entera."""
    c = repo.seed_comercio(id="com-q", slug="q", nombre="Q", plan="publica", confiable=True)
    _publicar_n(repo, c, 25)

    r = _post_publicar(client, "com-q")

    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["ok"] is True and cuerpo["estado"] == "aprobado"
    assert "Bs 5" in cuerpo["aviso"] and "Destacado" in cuerpo["aviso"]
    assert len(repo.cargos_extra) == 1
    assert repo.cargos_extra[0]["monto"] == 5
    # el cargo se ata a la publicación que acaba de salir
    assert repo.cargos_extra[0]["publicacion_id"] == cuerpo["publicacion"]["id"]


def test_publicar_dentro_de_la_cuota_no_cobra_y_el_aviso_es_null(client, repo):
    c = repo.seed_comercio(id="com-q", slug="q", nombre="Q", plan="publica", confiable=True)
    _publicar_n(repo, c, 3)

    r = _post_publicar(client, "com-q")

    assert r.status_code == 200, r.text
    assert r.json()["aviso"] is None
    assert repo.cargos_extra == []


def test_publicar_pasada_la_cuota_en_un_plan_sin_extras_da_402_con_el_aviso(client, repo):
    repo.upsert_plan("publica", {"permite_extras": False})
    c = repo.seed_comercio(id="com-q", slug="q", nombre="Q", plan="publica", confiable=True)
    _publicar_n(repo, c, 25)
    antes = len(repo.publicaciones)

    r = _post_publicar(client, "com-q")

    assert r.status_code == 402
    assert "Destacado" in r.json()["detail"]     # el error EXPLICA: dice qué hacer
    assert len(repo.publicaciones) == antes      # no se creó nada
    assert repo.cargos_extra == []


def test_publicar_con_el_periodo_vencido_da_402_y_explica(client, repo):
    c = repo.seed_comercio(id="com-v", slug="v", nombre="V", plan="gratis",
                           created_at=_hoy(-200))

    r = _post_publicar(client, "com-v")

    assert r.status_code == 402
    detalle = r.json()["detail"]
    assert "sigue en el mapa" in detalle and "Publica" in detalle
    assert repo.publicaciones == []


def test_un_fallo_al_cobrar_no_rompe_publicar(client, repo, monkeypatch):
    def _explota(*a, **k):
        raise RuntimeError("la base se cayó")
    monkeypatch.setattr(repo, "registrar_cargo_extra", _explota)
    c = repo.seed_comercio(id="com-q", slug="q", nombre="Q", plan="publica", confiable=True)
    _publicar_n(repo, c, 25)

    r = _post_publicar(client, "com-q")

    assert r.status_code == 200, r.text
    assert r.json()["aviso"]


def test_un_fallo_al_archivar_no_rompe_publicar(client, repo, monkeypatch):
    def _explota(comercio_id):
        raise RuntimeError("la base se cayó")
    monkeypatch.setattr(repo, "publicaciones_activas_de", _explota)
    repo.seed_comercio(id="com-q", slug="q", nombre="Q", plan="publica", confiable=True)

    r = _post_publicar(client, "com-q")

    assert r.status_code == 200, r.text
    assert len(repo.publicaciones) == 1


# ═══════════════════════════════════════════════ sin precios de planes

def _precios_de_planes(repo) -> list[str]:
    """Cada precio de plan escrito como podría aparecer en un texto: 70, 1250 y
    1.250. (El Bs 5 de la publicación extra NO es un precio de plan: se muestra.)"""
    salida = set()
    for p in repo.planes.values():
        n = float(p["precio_mes"])
        if n <= 0:
            continue
        entero = int(n)
        salida |= {str(entero), f"{entero:,}".replace(",", "."), f"{entero:,}"}
    return sorted(salida)


def _contiene_precio(texto: str, precios: list[str]) -> list[str]:
    return [p for p in precios if re.search(rf"(?<![\d.,]){re.escape(p)}(?![\d.,])", texto)]


def test_ningun_aviso_contiene_el_precio_de_un_plan(repo):
    """Criterio 5. Se prueba contra TODOS los planes como "el de arriba", en las
    tres consecuencias posibles y con el plan de arriba con cuota y sin ella."""
    precios = _precios_de_planes(repo)
    assert precios                                # el test no puede pasar en vacío
    repo.upsert_plan("empleado_ia", {"publicaciones_mes": None})
    textos = []
    for plan in repo.list_planes():
        for consecuencia in ("cobrar", "bloquear", "vencido"):
            for siguiente in (None, *repo.list_planes()):
                est = {"plan": {**plan, "permite_extras": consecuencia != "bloquear"},
                       "cuota": plan.get("publicaciones_mes") or 1,
                       "consecuencia": consecuencia}
                textos.append(planes.texto_de_aviso(est, siguiente))
    assert len(textos) > 100
    for t in textos:
        assert _contiene_precio(t, precios) == [], t


def test_el_aviso_si_dice_el_precio_de_la_publicacion_extra(repo):
    """Lo que va a pagar si sigue: no avisarle sería cobrarle de sorpresa."""
    c = repo.seed_comercio(slug="x", nombre="X", plan="publica")
    _publicar_n(repo, c, 25)
    est = planes.estado(repo, c)
    assert "Bs 5" in planes.texto_de_aviso(est, planes.plan_siguiente(repo, est["plan"]))


def test_el_asistente_lista_los_planes_sin_precios(repo):
    precios = _precios_de_planes(repo)
    r = asistente._nivel0_planes(repo)

    assert r.intent == "faq_planes"
    assert "Pro" in r.texto and "Publica" in r.texto          # nombre y descripción
    assert "Tu negocio digitalizado" in r.texto
    assert _contiene_precio(r.texto, precios) == [], r.texto
    assert "Bs" not in r.texto and "/mes" not in r.texto
    assert "/planes" in r.texto                               # y cómo consultar


def test_el_asistente_no_dice_ni_gratis_porque_es_un_precio(repo):
    r = asistente._nivel0_planes(repo)
    assert "— gratis" not in r.texto


# ═══════════════════════════════════════════════ Admin › Planes

def test_el_panel_guarda_publicaciones_guardadas_y_la_lista_lo_devuelve(client, repo, admin_token):
    """Criterio 7."""
    r = client.put("/admin/planes/publica", json={"publicaciones_guardadas": 120},
                   headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert repo.get_plan("publica")["publicaciones_guardadas"] == 120
    assert r.json()["plan"]["publicaciones_guardadas"] == 120

    lista = client.get("/admin/planes", headers=_h(admin_token)).json()["items"]
    assert next(p for p in lista if p["slug"] == "publica")["publicaciones_guardadas"] == 120


def test_el_panel_puede_dejar_un_plan_sin_tope_con_null(client, repo, admin_token):
    """`null` es "sin tope", un valor válido: no es lo mismo que "no lo toqué"."""
    r = client.put("/admin/planes/publica", json={"publicaciones_guardadas": None},
                   headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert repo.get_plan("publica")["publicaciones_guardadas"] is None


def test_editar_otro_campo_no_toca_el_tope(client, repo, admin_token):
    """Sin la clave en el cuerpo, el tope queda como estaba (no se pisa con null)."""
    r = client.put("/admin/planes/publica", json={"precio_mes": 75}, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert repo.get_plan("publica")["publicaciones_guardadas"] == 70


@pytest.mark.parametrize("valor", [0, -5])
def test_el_panel_rechaza_un_tope_que_no_es_mayor_que_cero(client, repo, admin_token, valor):
    r = client.put("/admin/planes/publica", json={"publicaciones_guardadas": valor},
                   headers=_h(admin_token))
    assert r.status_code == 422
    assert repo.get_plan("publica")["publicaciones_guardadas"] == 70


def test_el_panel_sigue_pudiendo_editar_el_precio_aunque_no_se_muestre(client, repo, admin_token):
    """Los precios siguen en la base y se editan en Admin › Planes."""
    r = client.put("/admin/planes/publica", json={"precio_mes": 99}, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert float(repo.get_plan("publica")["precio_mes"]) == 99
