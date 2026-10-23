from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://thrive:local-development-only@localhost:5432/thrive"
    upload_dir: Path = Path(".local/uploads")
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    max_archive_bytes: int = Field(default=100 * 1024 * 1024, gt=0)
    max_archive_entries: int = Field(default=2000, gt=0)
    max_compression_ratio: int = Field(default=100, gt=0)

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        return value
