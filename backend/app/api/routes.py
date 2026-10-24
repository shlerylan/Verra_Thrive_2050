from uuid import UUID
from fastapi import APIRouter, Depends, Form, Request, UploadFile
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.core.errors import AppError
from app.models.workbook import Workbook
from app.schemas.workbook import WorkbookMetadata
from app.schemas.project import MethodologyAssignment, ModuleSelection, ProjectCreate, ProjectMetadata
from app.models.project import LEGACY_PROJECT_ID, Project
from app.services.projects import assign_methodology, create_project, get_project, validate_file_context
from app import catalogue
from app.services.workbooks import store_workbook

router = APIRouter(prefix="/api")


def database_session(request: Request):
    with request.app.state.sessions() as session:
        yield session


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready(session: Session = Depends(database_session)):
    session.execute(text("SELECT 1"))
    # Also verify that migrations have created the expected table.
    session.execute(select(Workbook.id).limit(1))
    session.execute(select(Project.id).limit(1))
    return {"status": "ready"}


@router.post("/workbooks", response_model=WorkbookMetadata, status_code=201, deprecated=True)
def upload(request: Request, file: UploadFile, session: Session = Depends(database_session)):
    try:
        get_project(session, LEGACY_PROJECT_ID, lock=True)
        return store_workbook(file.file, file.filename, session, request.app.state.settings)
    finally:
        file.file.close()


@router.get("/workbooks", response_model=list[WorkbookMetadata], deprecated=True)
def list_workbooks(session: Session = Depends(database_session), offset: int = 0, limit: int = 50):
    if offset < 0 or not 1 <= limit <= 100:
        raise AppError(400, "invalid_pagination", "Offset must be nonnegative and limit must be between 1 and 100.")
    return session.scalars(select(Workbook).where(Workbook.project_id == LEGACY_PROJECT_ID).order_by(Workbook.uploaded_at.desc(), Workbook.id).offset(offset).limit(limit)).all()


@router.get("/workbooks/{workbook_id}", response_model=WorkbookMetadata, deprecated=True)
def metadata(workbook_id: UUID, session: Session = Depends(database_session)):
    record = session.get(Workbook, workbook_id)
    if record is None or record.project_id != LEGACY_PROJECT_ID:
        raise AppError(404, "not_found", "Workbook not found.")
    return record


def pagination(offset: int, limit: int):
    if offset < 0 or not 1 <= limit <= 100:
        raise AppError(400, "invalid_pagination", "Offset must be nonnegative and limit must be between 1 and 100.")


@router.get("/catalogue")
def module_catalogue():
    return {"methodologies": catalogue.METHODOLOGIES, "modules": catalogue.MODULES}


@router.post("/projects", response_model=ProjectMetadata, status_code=201)
def new_project(data: ProjectCreate, session: Session = Depends(database_session)):
    return create_project(session, data)


@router.get("/projects", response_model=list[ProjectMetadata])
def projects(offset: int = 0, limit: int = 50, session: Session = Depends(database_session)):
    pagination(offset, limit)
    return session.scalars(select(Project).order_by(Project.created_at.desc(), Project.id).offset(offset).limit(limit)).all()


@router.get("/projects/{project_id}", response_model=ProjectMetadata)
def project_details(project_id: UUID, session: Session = Depends(database_session)):
    return get_project(session, project_id)


@router.put("/projects/{project_id}/methodology", response_model=ProjectMetadata)
def methodology(project_id: UUID, data: MethodologyAssignment, session: Session = Depends(database_session)):
    return assign_methodology(session, project_id, data)


@router.get("/projects/{project_id}/modules", response_model=list[catalogue.ModuleDefinition])
def compatible_modules(project_id: UUID, session: Session = Depends(database_session)):
    project = get_project(session, project_id)
    return [module for module in catalogue.MODULES if catalogue.is_compatible(module, project)]


@router.post("/projects/{project_id}/workbooks", response_model=WorkbookMetadata, status_code=201)
def project_upload(project_id: UUID, request: Request, file: UploadFile,
                   module_id: str | None = Form(default=None, max_length=100),
                   module_version: str | None = Form(default=None, max_length=64),
                   file_role: str | None = Form(default=None, max_length=100),
                   session: Session = Depends(database_session)):
    try:
        # Serialize assignment changes with uploads so compatibility cannot change mid-write.
        project = get_project(session, project_id, lock=True)
        validate_file_context(project, module_id, module_version, file_role)
        return store_workbook(file.file, file.filename, session, request.app.state.settings,
                              project_id=project.id, module_id=module_id,
                              module_version=module_version, file_role=file_role)
    finally:
        file.file.close()


@router.get("/projects/{project_id}/workbooks", response_model=list[WorkbookMetadata])
def project_workbooks(project_id: UUID, offset: int = 0, limit: int = 50,
                      session: Session = Depends(database_session)):
    pagination(offset, limit)
    get_project(session, project_id)
    return session.scalars(select(Workbook).where(Workbook.project_id == project_id)
                           .order_by(Workbook.uploaded_at.desc(), Workbook.id).offset(offset).limit(limit)).all()


@router.get("/projects/{project_id}/workbooks/{workbook_id}", response_model=WorkbookMetadata)
def project_workbook_metadata(project_id: UUID, workbook_id: UUID, session: Session = Depends(database_session)):
    get_project(session, project_id)
    record = session.scalar(select(Workbook).where(Workbook.id == workbook_id, Workbook.project_id == project_id))
    if record is None:
        raise AppError(404, "not_found", "Workbook not found in this project.")
    return record


@router.post("/projects/{project_id}/inputs/review", status_code=409)
@router.post("/projects/{project_id}/runs", status_code=409)
def unavailable_calculation(project_id: UUID, data: ModuleSelection, session: Session = Depends(database_session)):
    project = get_project(session, project_id)
    module = catalogue.require_module(project, data.module_id, data.module_version)
    raise AppError(409, "calculation_unavailable",
                   "Input extraction, domain validation, calculation execution and results are not implemented for this module version. " + module.availability_reason)
