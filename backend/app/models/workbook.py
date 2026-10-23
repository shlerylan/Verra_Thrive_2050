from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, String, BigInteger, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class Workbook(Base):
    __tablename__ = "workbooks"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    original_filename: Mapped[str] = mapped_column(String(255))
    byte_size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    stored_file_id: Mapped[str] = mapped_column(String(36), unique=True)
