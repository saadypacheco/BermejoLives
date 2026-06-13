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

    model_config = {"populate_by_name": True}

    @property
    def phone(self) -> str:
        jid = self.from_ or ""
        return jid.split("@")[0]

    @property
    def wa_timestamp(self) -> datetime:
        if self.timestamp:
            return datetime.fromtimestamp(self.timestamp, tz=timezone.utc)
        return datetime.now(tz=timezone.utc)


class WahaEvent(BaseModel):
    event: str | None = None
    session: str | None = None
    payload: dict = {}
