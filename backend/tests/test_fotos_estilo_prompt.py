"""El prompt fijo de las fotos con IA (docs/fotos-estilo-uruku.md §2): versionado y sin datos del comercio."""
import hashlib

from app.services import fotos_estilo_prompt as p

#: version -> sha256 del texto completo (portada + galería). Si cambia una palabra del prompt, este test falla hasta que
#: se suba `PROMPT_VERSION` y se agregue la versión nueva acá (la vieja queda como historia).
HUELLAS = {
    "fotos-estilo-v1": "4308bbc61e6e3cc61975cd95908d7dabaf51e5e938be73bf3ad7de5782c8c4ff",
}


def _huella() -> str:
    texto = p.prompt("cover") + "\n---\n" + p.prompt("gallery")
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def test_el_sha256_del_prompt_esta_atado_a_la_version():
    assert p.PROMPT_VERSION in HUELLAS, "subiste la versión: agregá su huella a HUELLAS"
    assert _huella() == HUELLAS[p.PROMPT_VERSION], (
        "el texto del prompt cambió: subí PROMPT_VERSION (cada uso registra la versión con la que se hizo)")


def test_el_prompt_pide_lo_que_dijo_el_duenio():
    for target in ("cover", "gallery"):
        t = p.prompt(target)
        assert "Do NOT write any text, letters, numbers or logos" in t
        assert "same products" in t and "do not alter faces" in t
    assert "aspect 3:2" in p.prompt("cover") and "aspect 4:5" in p.prompt("gallery")
    assert "GALLERY" not in p.prompt("cover") and "COVER" not in p.prompt("gallery")


def test_el_prompt_no_lleva_datos_del_comercio_ni_formatos_de_plantilla():
    for target in ("cover", "gallery"):
        t = p.prompt(target)
        assert "{" not in t and "}" not in t            # sin huecos para rellenar con datos
    assert p.ASPECTO == {"cover": "3:2", "gallery": "4:5"}


def test_prompt_con_otro_target_es_error():
    import pytest
    with pytest.raises(ValueError):
        p.prompt("otro")


def test_las_instrucciones_para_chatgpt_son_el_mismo_prompt():
    i = p.instrucciones()
    assert i == {"version": p.PROMPT_VERSION, "cover": p.prompt("cover"), "gallery": p.prompt("gallery")}
