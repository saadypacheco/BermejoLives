"""La fecha de la cotización es la de las tasas que se usan, no la de filas vacías."""
from app.services import asistente


class _Repo:
    def list_cotizaciones(self):
        return [
            {"clave": "brl_bob", "valor": None, "actualizado_en": "2026-09-22T12:38:07+00:00"},
            {"clave": "pen_bob", "valor": None, "actualizado_en": "2026-09-22T12:38:07+00:00"},
            {"clave": "usd_bob", "valor": 11.7, "actualizado_en": "2026-10-20T11:41:23+00:00"},
            {"clave": "ars_bob", "valor": 7.3, "actualizado_en": "2026-10-20T11:41:28+00:00"},
            {"clave": "usd_ars", "valor": 1580, "actualizado_en": "2026-10-20T11:41:32+00:00"},
        ]


def test_filas_vacias_de_otras_fronteras_no_envejecen_la_cotizacion():
    t = asistente._tasas(_Repo())
    assert t["actualizado_en"].startswith("2026-10-20")
