"""La foto que llega por WhatsApp tiene que terminar en disco propio.

En este canal la foto ES la oferta: una publicación aprobada con la imagen rota
ocupa el lugar de una buena en el feed. Y las dos formas de romperla son mudas
—la ingesta sigue, la oferta se crea— así que se fijan acá.
"""
from app.services import wa_media


def test_el_host_del_mediaurl_se_reescribe_al_que_el_backend_alcanza(monkeypatch):
    """WAHA arma el mediaUrl con SU host. Sin WHATSAPP_FILES_URL seteado
    publica `localhost:3000`, que para el backend es su propio localhost: no
    encuentra nada y la oferta entra sin imagen, en silencio."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "waha_base_url", "http://waha:3000", raising=False)
    assert wa_media._url_alcanzable("http://localhost:3000/api/files/x.jpg") == \
        "http://waha:3000/api/files/x.jpg"


def test_si_ya_apunta_bien_no_se_toca(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "waha_base_url", "http://waha:3000", raising=False)
    url = "http://waha:3000/api/files/x.jpg"
    assert wa_media._url_alcanzable(url) == url


def test_sin_base_configurada_se_deja_como_vino(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "waha_base_url", "", raising=False)
    url = "http://localhost:3000/api/files/x.jpg"
    assert wa_media._url_alcanzable(url) == url


def test_descargar_sin_url_no_rompe():
    assert wa_media.descargar_media(None) is None
    assert wa_media.descargar_media("") is None


def test_lo_que_no_es_imagen_no_frena_la_publicacion(monkeypatch):
    """Un sticker raro o un archivo cualquiera no es un error del sistema: es un
    mensaje que no traía foto publicable. La publicación entra sin imagen."""
    monkeypatch.setattr(wa_media, "descargar_media", lambda _u: b"esto no es un jpg")
    assert wa_media.guardar_imagen_publicacion("mendo", "http://waha:3000/x.bin") is None
