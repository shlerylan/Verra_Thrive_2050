"""Opt-in integration test: use an empty, disposable PostgreSQL database only."""
import hashlib
import os
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.db.session import make_database
from app.main import create_app
from app.models.workbook import Workbook


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not configured")
def test_postgres_upload_persistence_and_duplicates(tmp_path, package, monkeypatch):
    url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    settings = Settings(database_url=url, upload_dir=tmp_path / "uploads")
    engine, sessions = make_database(url)
    ids = []
    try:
        with TestClient(create_app(settings)) as client:
            assert client.get("/api/ready").status_code == 200
            for _ in range(2):
                response = client.post("/api/workbooks", files={"file": ("review.xlsx", package)})
                assert response.status_code == 201, response.text
                record = response.json()
                ids.append(record["id"])
                assert record["sha256"] == hashlib.sha256(package).hexdigest()
                assert record["byte_size"] == len(package)
                assert record["status"] == "stored"
                assert record["uploaded_at"].endswith("Z")
                assert client.get(f'/api/workbooks/{record["id"]}').json() == record
            assert ids[0] != ids[1]
            assert set(ids) <= {item["id"] for item in client.get("/api/workbooks").json()}
        # A new connection verifies that the HTTP transaction really committed.
        with sessions() as session:
            for identifier in ids:
                from uuid import UUID
                record = session.get(Workbook, UUID(identifier))
                assert record is not None
                assert (settings.upload_dir / record.stored_file_id).read_bytes() == package
    finally:
        with sessions.begin() as session:
            from uuid import UUID
            for identifier in ids:
                record = session.get(Workbook, UUID(identifier))
                if record:
                    session.delete(record)
        engine.dispose()
