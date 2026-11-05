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
    availability: Literal["unavailable", "file_intake_only", "prototype_calculation", "calculation_ready"]
    availability_reason: str
    compatible_methodologies: tuple[MethodologyReference, ...] = ()
    methodology_independent: bool = False
    file_roles: tuple[FileRole, ...] = ()
    adapter_id: str | None = None
    input_contract_version: str | None = None
    expected_output_description: str | None = None
    template_version: str | None = None

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
METHODOLOGIES: tuple[MethodologyVersion, ...] = (
    MethodologyVersion(identifier="VM0047", version="1.0",
                       name="Afforestation, Reforestation and Revegetation",
                       note="Official version reference. Project applicability and full calculation support remain under review."),
)
MODULES: tuple[ModuleDefinition, ...] = (
    ModuleDefinition(
        identifier="workbook-intake", version="1.0.0", name="Workbook Intake",
        description="A generic file-storage utility. It does not establish suitability for any methodology or calculation.",
        kind="utility", availability="file_intake_only", methodology_independent=True,
        availability_reason="Storage and basic XLSX package checks only. Extraction, domain-input validation and calculation are not implemented.",
        file_roles=(FileRole(identifier="original-workbook", name="Original workbook",
                            description="An optional original XLSX file for collection, not an official methodology requirement.", required=False),
                    FileRole(identifier="input-template", name="Completed intake template",
                             description="The downloadable generic input template; layout and entries are checked on upload.", required=False)),
        template_version="1.0.0",
    ),
    ModuleDefinition(
        identifier="leakage-single-commodity", version="0.1.0",
        name="VMD0054 Agricultural Leakage Pilot",
        description="One agricultural commodity, one project instance, and up to five monitoring years. Arithmetic preview only.",
        kind="calculation", availability="prototype_calculation",
        availability_reason="Input evidence, applicability, intensification effects and full VCS requirements need review before a verified calculation is available.",
        compatible_methodologies=(MethodologyReference(identifier="VM0047", version="1.0"),),
        file_roles=(FileRole(identifier="leakage-input-template", name="Completed Leakage template",
                             description="Versioned inputs for the single-commodity calculation preview.", required=True),),
        adapter_id="leakage-inputs-v0.1", input_contract_version="0.1.0",
        expected_output_description="Annual leakage arithmetic preview with source workbook checksum and limitations.",
        template_version="0.2.0",
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
