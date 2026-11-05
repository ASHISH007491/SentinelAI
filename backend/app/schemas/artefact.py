"""Artefact response schema."""
from datetime import datetime

from pydantic import BaseModel


class ArtefactRead(BaseModel):
    id: int
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
