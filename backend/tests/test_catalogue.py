from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from app import catalogue
from app.core.errors import AppError
from app.schemas.project import ProjectCreate
from app.services.projects import validate_file_context


def test_production_catalogue_makes_no_calculation_claims():
    assert [(item.identifier, item.version) for item in catalogue.METHODOLOGIES] == [("VM0047", "1.0")]
    assert all(item.availability != "calculation_ready" for item in catalogue.MODULES)
    intake = catalogue.MODULES[0]
    assert intake.kind == "utility" and intake.adapter_id is None
    assert intake.input_contract_version is None
    assert intake.expected_output_description is None
    pilot = catalogue.MODULES[1]
    assert pilot.availability == "prototype_calculation"
    assert pilot.compatible_methodologies[0].identifier == "VM0047"


def test_compatibility_is_exact_and_not_based_on_module_name(monkeypatch):
    module = catalogue.ModuleDefinition(
        identifier="test-only", version="1", name="Test fixture", description="Not a real methodology.",
        kind="calculation", availability="unavailable", availability_reason="Test only: not implemented.",
        compatible_methodologies=(catalogue.MethodologyReference(identifier="fixture", version="1"),),
    )
    monkeypatch.setattr(catalogue, "MODULES", (module,))
    project = SimpleNamespace(methodology_id="fixture", methodology_version="2")
    assert not catalogue.is_compatible(module, project)
    with pytest.raises(AppError) as error:
        catalogue.require_module(project, "test-only", "1")
    assert error.value.code == "incompatible_module"
    project.methodology_version = "1"
    with pytest.raises(AppError) as error:
        validate_file_context(project, "test-only", "1", "input")
    assert error.value.code == "module_unavailable"
    with pytest.raises(AppError):
        catalogue.require_module(project, "test-only", "2")
    with pytest.raises(ValidationError):
        catalogue.ModuleDefinition(**{**module.model_dump(), "availability": "calculation_ready"})


@pytest.mark.parametrize("data", [{"name": " "}, {"name": "A", "methodology_id": "fixture"},
                                  {"name": "A", "project_id": "injected"}])
def test_invalid_project_input(data):
    with pytest.raises(ValidationError):
        ProjectCreate(**data)


def test_file_roles_require_complete_context():
    project = SimpleNamespace(methodology_id=None, methodology_version=None)
    validate_file_context(project, None, None, None)
    with pytest.raises(AppError) as error:
        validate_file_context(project, "workbook-intake", None, None)
    assert error.value.code == "incomplete_file_context"
    with pytest.raises(AppError) as error:
        validate_file_context(project, "workbook-intake", "1.0.0", "invented-role")
    assert error.value.code == "invalid_file_role"
