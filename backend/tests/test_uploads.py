import io
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from app.api.routes import database_session
from app.core.config import Settings
from app.core.errors import AppError
from app.main import create_app
from app.services.workbooks import store_workbook, validate_filename, validate_package
from conftest import xlsx_bytes


@pytest.fixture
def settings(tmp_path):
    return Settings(upload_dir=tmp_path / "uploads")


@pytest.mark.parametrize("name", ["../a.xlsx", "C:\\a.xlsx", "a.xlsm", "a.csv", ".xlsx", "a\x00.xlsx", "a.xlsx ", "CON.xlsx", "x" * 256 + ".xlsx", ""])
def test_unsafe_filenames(name):
    with pytest.raises(AppError) as error:
        validate_filename(name)
    assert error.value.code == "invalid_filename"


def test_valid_package(settings, package):
    path = settings.upload_dir.parent / "sample"
    path.write_bytes(package)
    validate_package(path, settings)


@pytest.mark.parametrize("content", [
    b"not a zip", xlsx_bytes({"xl/vbaProject.bin": "code"}),
    xlsx_bytes(workbook_type="application/vnd.ms-excel.sheet.macroEnabled.main+xml"),
    xlsx_bytes({"../escape": "x"}), xlsx_bytes({"xl/workbook.xml": "<broken"}),
    xlsx_bytes({"bomb": "0" * 100000}),
    xlsx_bytes({"_rels/.rels": "<Relationships/>"}),
    xlsx_bytes({"xl/workbook.xml": '<!DOCTYPE x [<!ENTITY e "bad">]><workbook>&e;</workbook>'}),
])
def test_reject_bad_packages(settings, content):
    path = settings.upload_dir.parent / "bad"
    path.write_bytes(content)
    with pytest.raises(AppError) as error:
        validate_package(path, settings)
    assert error.value.code == "invalid_xlsx"


@pytest.mark.parametrize("override", [{"max_archive_bytes": 100}, {"max_archive_entries": 2}])
def test_archive_limits(settings, package, override):
    settings = settings.model_copy(update=override)
    path = settings.upload_dir.parent / "archive"
    path.write_bytes(package)
    with pytest.raises(AppError):
        validate_package(path, settings)


def test_size_limit_cleans_file(settings, package):
    settings.max_upload_bytes = 10
    with pytest.raises(AppError) as error:
        store_workbook(io.BytesIO(package), "a.xlsx", Mock(), settings)
    assert error.value.status == 413
    assert list(settings.upload_dir.iterdir()) == []


@pytest.mark.parametrize("failure", ["flush", "commit"])
def test_database_failure_cleans_file(settings, package, failure):
    session = Mock()
    getattr(session, failure).side_effect = OperationalError("write", {}, Exception())
    with pytest.raises(OperationalError):
        store_workbook(io.BytesIO(package), "a.xlsx", session, settings)
    session.rollback.assert_called_once()
    assert list(settings.upload_dir.iterdir()) == []


def test_storage_failure_does_not_add_metadata(settings, package, monkeypatch):
    session = Mock()
    from pathlib import Path
    def fail(*args, **kwargs):
        raise OSError("storage failed")
    monkeypatch.setattr(Path, "open", fail)
    with pytest.raises(OSError):
        store_workbook(io.BytesIO(package), "a.xlsx", session, settings)
    session.add.assert_not_called()


def test_health_readiness_and_safe_errors(settings, package):
    app = create_app(settings)
    session = Mock()
    session.execute.side_effect = OperationalError("secret internal path", {}, Exception())
    app.dependency_overrides[database_session] = lambda: session
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        response = client.get("/api/ready")
        assert response.status_code == 503
        assert "secret" not in response.text
        session.execute.side_effect = None
        assert client.get("/api/ready").json() == {"status": "ready"}
        assert client.post("/api/workbooks", files={"file": ("a.csv", b"a")}).status_code == 400
        assert client.post("/api/workbooks", files={"file": ("a.xlsx", b"bad")}).status_code == 400
        assert client.get("/api/workbooks/not-a-uuid").status_code == 422
        assert client.get("/api/workbooks?limit=1000").status_code == 400
        session.get.return_value = None
        assert client.get("/api/workbooks/00000000-0000-0000-0000-000000000001").status_code == 404


def test_request_body_limit(settings):
    settings.max_upload_bytes = 10
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        response = client.post("/api/workbooks", files={"file": ("a.xlsx", b"x" * 70000)})
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "upload_too_large"


def test_non_postgres_configuration_rejected():
    with pytest.raises(ValueError):
        Settings(database_url="sqlite:///fallback.db")
