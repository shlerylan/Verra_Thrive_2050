from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import CheckConstraint, DateTime, String, BigInteger, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
from app.models.project import LEGACY_PROJECT_ID


class Workbook(Base):
    __tablename__ = "workbooks"
    __table_args__ = (CheckConstraint(
        "(module_id IS NULL AND module_version IS NULL AND file_role IS NULL) OR "
        "(module_id IS NOT NULL AND module_version IS NOT NULL AND file_role IS NOT NULL)",
        name="ck_workbook_module_context"
    ),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), index=True, default=LEGACY_PROJECT_ID)
    module_id: Mapped[str | None] = mapped_column(String(100))
    module_version: Mapped[str | None] = mapped_column(String(64))
    file_role: Mapped[str | None] = mapped_column(String(100))
    template_version: Mapped[str | None] = mapped_column(String(64))
    template_validation: Mapped[str | None] = mapped_column(String(32))
    original_filename: Mapped[str] = mapped_column(String(255))
    byte_size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    stored_file_id: Mapped[str] = mapped_column(String(36), unique=True)
