"""Modelos Pydantic del evento de WAHA (mismo bridge que mentorcomercial)."""
from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _numero_de(jid: str | None, alternativo: str | None) -> str:
    """El teléfono detrás de un JID — incluso cuando WhatsApp lo esconde.

    EL @lid, QUE APAGABA TODAS LAS GUARDAS SIN DAR ERROR
    ====================================================
    WhatsApp está reemplazando el número de teléfono en los grupos por un
    identificador oculto: el remitente llega como `160138577080406@lid` en vez
    de `59175314737@c.us`. Se vio el 11/9 con el primer código de grupo en
    producción: el Samsung —que está en WA_NUMEROS_PROPIOS— no fue reconocido
    como propio, porque el "número" que se comparaba era el @lid.

    Eso apaga en silencio todo lo que mira el número: que los respaldos se
    ignoren, que un comercio confiable publique directo, que el explorador se
    reconozca. Ninguna de esas guardas da error; simplemente no matchean.

    WAHA manda el número real al lado, en `_data.key.participantAlt` (grupos) o
    `remoteJidAlt` (chat directo), con sufijo `@s.whatsapp.net`. Cuando el JID
    principal es un @lid, se usa ése.
    """
    principal = jid or ""
    if principal.endswith("@lid") and alternativo:
        principal = alternativo
    return principal.split("@")[0]


class WahaMessagePayload(BaseModel):
    id: str | None = None
    from_: str | None = Field(default=None, alias="from")   # jid del remitente
    from_me: bool = Field(default=False, alias="fromMe")
    body: str | None = None
    type: str = "text"
    timestamp: int | None = None
    has_media: bool = Field(default=False, alias="hasMedia")
    mime_type: str | None = Field(default=None, alias="mimetype")
    media_url: str | None = Field(default=None, alias="mediaUrl")
    location: dict | None = None          # ubicación compartida por WhatsApp
    participant: str | None = None        # en un grupo: quién de adentro escribió
    data: dict | None = Field(default=None, alias="_data")

    model_config = {"populate_by_name": True}

    @property
    def es_grupo(self) -> bool:
        """WhatsApp distingue los grupos por el sufijo del JID: las personas
        terminan en @c.us o @s.whatsapp.net, los grupos en @g.us."""
        return (self.from_ or "").endswith("@g.us")

    @property
    def phone(self) -> str:
        """El número de quien escribió, sea chat directo o grupo.

        En un chat 1-a-1, `from` ES el remitente. En un grupo, `from` es el
        grupo y el remitente viene aparte — si se usara `from` acá, el "número"
        sería el ID del grupo y no matchearía ningún comercio.
        """
        jid = self.remitente_jid if self.es_grupo else self.from_
        return _numero_de(jid, self._alternativo("remoteJidAlt" if not self.es_grupo
                                                  else "participantAlt"))

    def _alternativo(self, campo: str) -> str | None:
        key = (self.data or {}).get("key") or {}
        return key.get(campo) or None

    @property
    def remitente_jid(self) -> str | None:
        """El JID de quien escribió dentro del grupo.

        WAHA lo pone en `participant` con el motor WEBJS y adentro de
        `_data.key.participant` con NOWEB, que es el que corre en prod. Se
        miran los dos porque cambiar de motor no debería romper la ingesta.
        """
        if self.participant:
            return self.participant
        key = (self.data or {}).get("key") or {}
        return key.get("participant") or None

    @property
    def grupo_jid(self) -> str | None:
        return self.from_ if self.es_grupo else None

    @property
    def wa_timestamp(self) -> datetime:
        if self.timestamp:
            return datetime.fromtimestamp(self.timestamp, tz=timezone.utc)
        return datetime.now(tz=timezone.utc)


class WahaEvent(BaseModel):
    event: str | None = None
    session: str | None = None
    payload: dict = {}
