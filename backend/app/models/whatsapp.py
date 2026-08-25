"""Modelos Pydantic del evento de WAHA (mismo bridge que mentorcomercial)."""
from datetime import datetime, timezone

from pydantic import BaseModel, Field


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
        if self.es_grupo:
            return (self.remitente_jid or "").split("@")[0]
        return (self.from_ or "").split("@")[0]

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
