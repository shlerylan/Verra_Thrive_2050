from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import catalogue
from app.core.errors import AppError
from app.models.project import Project
from app.models.workbook import Workbook
from app.schemas.project import MethodologyAssignment, ProjectCreate


def get_project(session: Session, project_id: UUID, *, lock: bool = False) -> Project:
    statement = select(Project).where(Project.id == project_id)
    if lock:
        statement = statement.with_for_update()
    project = session.scalar(statement)
    if project is None:
        raise AppError(404, "project_not_found", "Project not found.")
    return project


def create_project(session: Session, data: ProjectCreate) -> Project:
    catalogue.validate_methodology(data.methodology_id, data.methodology_version)
    project = Project(**data.model_dump())
    session.add(project)
    session.flush()
    session.refresh(project)
    session.commit()
    return project


def assign_methodology(session: Session, project_id: UUID, data: MethodologyAssignment) -> Project:
    project = get_project(session, project_id, lock=True)
    catalogue.validate_methodology(data.methodology_id, data.methodology_version)
    changed = (project.methodology_id, project.methodology_version) != (data.methodology_id, data.methodology_version)
    if changed:
        contexts = session.execute(select(Workbook.module_id, Workbook.module_version).where(
            Workbook.project_id == project.id, Workbook.module_id.is_not(None)
        ).distinct()).all()
        for identifier, version in contexts:
            definition = next((item for item in catalogue.MODULES
                               if item.identifier == identifier and item.version == version), None)
            if definition is None or not definition.methodology_independent:
                raise AppError(409, "assignment_in_use", "This project has methodology-specific or unknown module associations. Keep its assignment to preserve their context; create another project for different rules.")
    project.methodology_id, project.methodology_version = data.methodology_id, data.methodology_version
    session.commit()
    return project


def validate_file_context(project: Project, module_id: str | None, module_version: str | None, role: str | None):
    if module_id is None and module_version is None and role is None:
        return
    if not all((module_id, module_version, role)):
        raise AppError(400, "incomplete_file_context", "Module identifier, version and file role must be provided together.")
    module = catalogue.require_module(project, module_id, module_version)
    if module.availability == "unavailable":
        raise AppError(409, "module_unavailable", module.availability_reason)
    if not any(item.identifier == role and ".xlsx" in item.permitted_formats for item in module.file_roles):
        raise AppError(400, "invalid_file_role", "Choose a configured XLSX file role for this module version.")
