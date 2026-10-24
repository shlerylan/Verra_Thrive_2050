from datetime import datetime, timezone
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_serializer


class WorkbookMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    module_id: str | None
    module_version: str | None
    file_role: str | None
    original_filename: str
    byte_size: int
    sha256: str
    uploaded_at: datetime
    status: Literal["stored"] = "stored"
    package_validation: Literal["basic_checks_passed"] = "basic_checks_passed"
    domain_validation: Literal["not_performed"] = "not_performed"

    @field_serializer("uploaded_at")
    def serialize_uploaded_at(self, value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
