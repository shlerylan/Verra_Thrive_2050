from uuid import UUID
from fastapi import APIRouter, Depends, Request, UploadFile
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.core.errors import AppError
from app.models.workbook import Workbook
from app.schemas.workbook import WorkbookMetadata
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
    return {"status": "ready"}


@router.post("/workbooks", response_model=WorkbookMetadata, status_code=201)
def upload(request: Request, file: UploadFile, session: Session = Depends(database_session)):
    try:
        return store_workbook(file.file, file.filename, session, request.app.state.settings)
    finally:
        file.file.close()


@router.get("/workbooks", response_model=list[WorkbookMetadata])
def list_workbooks(session: Session = Depends(database_session), offset: int = 0, limit: int = 50):
    if offset < 0 or not 1 <= limit <= 100:
        raise AppError(400, "invalid_pagination", "Offset must be nonnegative and limit must be between 1 and 100.")
    return session.scalars(select(Workbook).order_by(Workbook.uploaded_at.desc(), Workbook.id).offset(offset).limit(limit)).all()


@router.get("/workbooks/{workbook_id}", response_model=WorkbookMetadata)
def metadata(workbook_id: UUID, session: Session = Depends(database_session)):
    record = session.get(Workbook, workbook_id)
    if record is None:
        raise AppError(404, "not_found", "Workbook not found.")
    return record
