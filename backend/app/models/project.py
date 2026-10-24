from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import CheckConstraint, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

LEGACY_PROJECT_ID = UUID("00000000-0000-0000-0000-000000000001")


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (CheckConstraint(
        "(methodology_id IS NULL) = (methodology_version IS NULL)", name="ck_project_methodology_pair"
    ),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    methodology_id: Mapped[str | None] = mapped_column(String(100))
    methodology_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
