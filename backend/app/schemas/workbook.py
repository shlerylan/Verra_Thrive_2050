from datetime import datetime, timezone
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_serializer


class WorkbookMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    original_filename: str
    byte_size: int
    sha256: str
    uploaded_at: datetime
    status: Literal["stored"] = "stored"

    @field_serializer("uploaded_at")
    def serialize_uploaded_at(self, value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
