"""Reviewed code definitions, never user-provided executable code or formulas."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, model_validator
from app.core.errors import AppError


class MethodologyVersion(BaseModel):
    model_config = ConfigDict(frozen=True)
    identifier: str
    version: str
    name: str
    review_status: Literal["unreviewed", "reviewed"] = "unreviewed"
    note: str


class MethodologyReference(BaseModel):
    identifier: str
    version: str


class FileRole(BaseModel):
    identifier: str
    name: str
    description: str
    required: bool
    permitted_formats: tuple[Literal[".xlsx"], ...] = (".xlsx",)


class ModuleDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)
    identifier: str
    version: str
    name: str
    description: str
    kind: Literal["utility", "calculation"]
    availability: Literal["unavailable", "file_intake_only", "calculation_ready"]
    availability_reason: str
    compatible_methodologies: tuple[MethodologyReference, ...] = ()
    methodology_independent: bool = False
    file_roles: tuple[FileRole, ...] = ()
    adapter_id: str | None = None
    input_contract_version: str | None = None
    expected_output_description: str | None = None

    @model_validator(mode="after")
    def enforce_milestone_capabilities(self):
        if self.methodology_independent and self.kind != "utility":
            raise ValueError("Only utilities may be methodology-independent.")
        if self.availability == "calculation_ready":
            raise ValueError("Calculation-ready registration requires an execution implementation; none exists in this milestone.")
        if len({role.identifier for role in self.file_roles}) != len(self.file_roles):
            raise ValueError("File-role identifiers must be unique within a module version.")
        return self


# No official identifiers/versions or requirements have been supplied for review.
METHODOLOGIES: tuple[MethodologyVersion, ...] = ()
MODULES: tuple[ModuleDefinition, ...] = (
    ModuleDefinition(
        identifier="workbook-intake", version="1.0.0", name="Workbook Intake",
        description="A generic file-storage utility. It does not establish suitability for any methodology or calculation.",
        kind="utility", availability="file_intake_only", methodology_independent=True,
        availability_reason="Storage and basic XLSX package checks only. Extraction, domain-input validation and calculation are not implemented.",
        file_roles=(FileRole(identifier="original-workbook", name="Original workbook",
                            description="An optional original XLSX file for collection, not an official methodology requirement.", required=False),),
    ),
)


def validate_methodology(identifier: str | None, version: str | None):
    if identifier is None and version is None:
        return
    if not any(item.identifier == identifier and item.version == version for item in METHODOLOGIES):
        raise AppError(400, "unknown_methodology", "Choose an explicitly configured methodology version or leave it unassigned.")


def is_compatible(module: ModuleDefinition, project) -> bool:
    return module.methodology_independent or any(
        item.identifier == project.methodology_id and item.version == project.methodology_version
        for item in module.compatible_methodologies
    )


def require_module(project, identifier: str, version: str) -> ModuleDefinition:
    module = next((item for item in MODULES if item.identifier == identifier and item.version == version), None)
    if module is None:
        raise AppError(404, "unknown_module", "This module version is not configured.")
    if not is_compatible(module, project):
        raise AppError(409, "incompatible_module", "This module version is not compatible with the project's exact methodology version.")
    return module
