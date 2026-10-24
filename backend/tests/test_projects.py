"""Real PostgreSQL tests in isolated schemas; synthetic catalogue entries are test-only."""
import os
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from app import catalogue
from app.core.config import Settings
from app.db.session import make_database
from app.main import create_app
from app.models.project import LEGACY_PROJECT_ID

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is not configured")


@pytest.fixture
def isolated_database(monkeypatch):
    url = os.environ["TEST_DATABASE_URL"]
    schema = "test_" + uuid4().hex
    engine, _ = make_database(url)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", isolated)
    try:
        yield isolated
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


@pytest.fixture
def client(isolated_database, tmp_path):
    command.upgrade(Config("alembic.ini"), "head")
    settings = Settings(database_url=isolated_database, upload_dir=tmp_path / "uploads")
    with TestClient(create_app(settings)) as client:
        yield client, settings


def test_migration_preserves_original_metadata(isolated_database):
    config = Config("alembic.ini")
    command.upgrade(config, "0001")
    engine, _ = make_database(isolated_database)
    identifier = uuid4()
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO workbooks (id, original_filename, byte_size, sha256, stored_file_id) "
                                "VALUES (:id, 'preserved.xlsx', 123, :checksum, :stored)"),
                           {"id": identifier, "checksum": "a" * 64, "stored": str(uuid4())})
        original = dict(connection.execute(text("SELECT * FROM workbooks WHERE id=:id"), {"id": identifier}).mappings().one())
    command.upgrade(config, "head")
    with engine.connect() as connection:
        migrated = dict(connection.execute(text("SELECT * FROM workbooks WHERE id=:id"), {"id": identifier}).mappings().one())
        assert {key: migrated[key] for key in original} == original
        assert migrated["project_id"] == LEGACY_PROJECT_ID
        assert migrated["module_id"] is None
    command.check(config)
    engine.dispose()


def test_project_creation_ownership_and_duplicates(client, package, monkeypatch):
    http, settings = client
    assert http.get("/api/ready").status_code == 200
    a = http.post("/api/projects", json={"name": "Project A", "description": "Test project"}).json()
    b = http.post("/api/projects", json={"name": "Project B"}).json()
    assert http.get(f'/api/projects/{a["id"]}').json() == a
    assert a in http.get("/api/projects").json()
    first = http.post(f'/api/projects/{a["id"]}/workbooks', files={"file": ("a.xlsx", package)})
    assert first.status_code == 201, first.text
    item = first.json()
    assert item["project_id"] == a["id"]
    assert item["domain_validation"] == "not_performed"
    assert item["package_validation"] == "basic_checks_passed"
    second = http.post(f'/api/projects/{a["id"]}/workbooks', files={"file": ("a.xlsx", package)}).json()
    assert second["id"] != item["id"] and second["sha256"] == item["sha256"]
    assert len(http.get(f'/api/projects/{a["id"]}/workbooks').json()) == 2
    assert http.get(f'/api/projects/{b["id"]}/workbooks').json() == []
    assert http.get(f'/api/projects/{b["id"]}/workbooks/{item["id"]}').status_code == 404
    assert http.get(f'/api/projects/{a["id"]}/workbooks/{item["id"]}').json() == item
    assert http.get(f'/api/workbooks/{item["id"]}').status_code == 404
    invalid = http.post(f'/api/projects/{uuid4()}/workbooks', files={"file": ("a.xlsx", package)})
    assert invalid.status_code == 404
    assert len(list(settings.upload_dir.iterdir())) == 2
    # Ownership and complete module context are enforced by PostgreSQL too.
    engine, _ = make_database(settings.database_url)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("UPDATE workbooks SET project_id=:missing WHERE id=:id"), {"missing": uuid4(), "id": item["id"]})
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("UPDATE workbooks SET module_id='partial' WHERE id=:id"), {"id": item["id"]})
    engine.dispose()

    # Methodology-independent utility files must not prevent later rule selection.
    fixture = catalogue.MethodologyVersion(identifier="test-rules", version="1", name="Synthetic rules", note="Test only.")
    monkeypatch.setattr(catalogue, "METHODOLOGIES", (fixture,))
    utility = http.post(f'/api/projects/{b["id"]}/workbooks', files={"file": ("intake.xlsx", package)},
                        data={"module_id": "workbook-intake", "module_version": "1.0.0", "file_role": "original-workbook"})
    assert utility.status_code == 201
    assignment = http.put(f'/api/projects/{b["id"]}/methodology', json={"methodology_id": "test-rules", "methodology_version": "1"})
    assert assignment.status_code == 200
    assert http.get(f'/api/projects/{b["id"]}').json()["methodology_version"] == "1"
    assert http.put(f'/api/projects/{b["id"]}/methodology', json={}).status_code == 200


def test_methodology_filtering_roles_and_unavailable_actions(client, package, monkeypatch):
    http, settings = client
    fixture = catalogue.MethodologyVersion(identifier="test-rules", version="1", name="Synthetic test rules", note="Test fixture only.")
    fixture_v2 = fixture.model_copy(update={"version": "2"})
    module = catalogue.ModuleDefinition(
        identifier="test-module", version="1", name="Synthetic module", description="Test fixture only.",
        kind="calculation", availability="file_intake_only", availability_reason="No calculation implementation.",
        compatible_methodologies=(catalogue.MethodologyReference(identifier="test-rules", version="1"),),
        file_roles=(catalogue.FileRole(identifier="source", name="Source", description="Synthetic input.", required=True),),
    )
    unavailable = module.model_copy(update={"identifier": "not-built", "availability": "unavailable"})
    monkeypatch.setattr(catalogue, "METHODOLOGIES", (fixture, fixture_v2))
    monkeypatch.setattr(catalogue, "MODULES", (*catalogue.MODULES, module, unavailable))
    a = http.post("/api/projects", json={"name": "A"}).json()
    path = f'/api/projects/{a["id"]}'
    assert [item["identifier"] for item in http.get(path + "/modules").json()] == ["workbook-intake"]
    assert http.put(path + "/methodology", json={"methodology_id": "arbitrary", "methodology_version": "1"}).status_code == 400
    assignment = {"methodology_id": "test-rules", "methodology_version": "1"}
    assert http.put(path + "/methodology", json=assignment).status_code == 200
    assert {item["identifier"] for item in http.get(path + "/modules").json()} == {"workbook-intake", "test-module", "not-built"}
    upload = lambda data: http.post(path + "/workbooks", data=data, files={"file": ("a.xlsx", package)})
    assert upload({"module_id": "test-module"}).status_code == 400
    assert upload({"module_id": "test-module", "module_version": "9", "file_role": "source"}).status_code == 404
    assert upload({"module_id": "test-module", "module_version": "1", "file_role": "wrong"}).status_code == 400
    assert upload({"module_id": "not-built", "module_version": "1", "file_role": "source"}).status_code == 409
    v2 = {"methodology_id": "test-rules", "methodology_version": "2"}
    assert http.put(path + "/methodology", json=v2).status_code == 200
    assert upload({"module_id": "test-module", "module_version": "1", "file_role": "source"}).status_code == 409
    assert http.post(path + "/runs", json={"module_id": "test-module", "module_version": "1"}).status_code == 409
    assert http.put(path + "/methodology", json=assignment).status_code == 200
    stored = upload({"module_id": "test-module", "module_version": "1", "file_role": "source"})
    assert stored.status_code == 201, stored.text
    assert stored.json()["file_role"] == "source"
    assert len(list(settings.upload_dir.iterdir())) == 1
    assert http.put(path + "/methodology", json=v2).status_code == 409
    assert http.put(path + "/methodology", json=assignment).status_code == 200
    for endpoint in ("/runs", "/inputs/review"):
        response = http.post(path + endpoint, json={"module_id": "test-module", "module_version": "1"})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "calculation_unavailable"
    assert http.post("/api/projects", json={"name": "Bad", "methodology_id": "unknown", "methodology_version": "1"}).status_code == 400
    assert http.post("/api/projects", json={"name": " "}).status_code == 422
    monkeypatch.setattr(catalogue, "MODULES", (module,))
    unassigned = http.post("/api/projects", json={"name": "Unassigned"}).json()
    assert http.get(f'/api/projects/{unassigned["id"]}/modules').json() == []
