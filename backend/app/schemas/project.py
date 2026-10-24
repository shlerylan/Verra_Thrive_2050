from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MethodologyAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    methodology_id: str | None = Field(default=None, min_length=1, max_length=100)
    methodology_version: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def require_pair(self):
        if (self.methodology_id is None) != (self.methodology_version is None):
            raise ValueError("Methodology identifier and version must be assigned together.")
        return self


class ProjectCreate(MethodologyAssignment):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)

    @field_validator("name", "description")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if any(ord(character) < 32 and character not in "\n\t" for character in value):
            raise ValueError("Use readable text without control characters.")
        return value

    @field_validator("name")
    @classmethod
    def nonempty_name(cls, value: str) -> str:
        if not value:
            raise ValueError("Project name is required.")
        return value


class ProjectMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str
    methodology_id: str | None
    methodology_version: str | None
    created_at: datetime


class ModuleSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    module_id: str = Field(min_length=1, max_length=100)
    module_version: str = Field(min_length=1, max_length=64)
