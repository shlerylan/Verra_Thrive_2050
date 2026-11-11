"""HTTP contracts and project-source checks, with only persistence substituted."""
import asyncio
import hashlib
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.routes import router, database_session
from app.core.errors import AppError
from app.models.project import Project
from app.services.leakage import leakage_template, parse_leakage_template, calculate_leakage


@pytest.fixture
def scenario_api(tmp_path):
    project_id, other_id, workbook_id = uuid4(), uuid4(), uuid4()
    path = tmp_path / str(uuid4())
    path.write_bytes(leakage_template(example=True))
    record = SimpleNamespace(
        id=workbook_id, project_id=project_id, stored_file_id=path.name,
        module_id='leakage-single-commodity', module_version='0.1.0',
        file_role='leakage-input-template', template_version='0.2.0',
        template_validation='passed', sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    projects = {identifier: SimpleNamespace(id=identifier, methodology_id='VM0047', methodology_version='1.0')
                for identifier in (project_id, other_id)}

    class Session:
        def scalar(self, statement):
            values = statement.compile().params
            if statement.column_descriptions[0]['entity'] is Project:
                return projects.get(next(iter(values.values())))
            # A regression that drops either scope condition fails this assertion.
            assert set(values) == {'id_1', 'project_id_1'}
            return record if values['id_1'] == workbook_id and values['project_id_1'] == project_id else None

    app = FastAPI()
    app.include_router(router)
    app.state.settings = SimpleNamespace(upload_dir=tmp_path)
    app.dependency_overrides[database_session] = lambda: Session()

    @app.exception_handler(AppError)
    async def error_handler(request, error):
        return JSONResponse(status_code=error.status, content={'error': {'code': error.code, 'message': error.message}})

    def post(project, suffix, payload):
        async def send():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                return await client.post(f'/api/projects/{project}/leakage/{suffix}', json=payload)
        return asyncio.run(send())
    return post, project_id, other_id, record, path


def test_scenario_http_matches_preview_and_overridden_workbook(scenario_api):
    from dataclasses import replace
    from decimal import Decimal
    post, project, other, record, path = scenario_api
    body = {'workbook_id': str(record.id)}
    preview = post(project, 'preview', body)
    assert preview.status_code == 200
    for row in preview.json()['annual_results']:
        response = post(project, 'scenario', {**body, 'year': row['year'],
                                             'mitigation_production': row['monitored_mitigation_production']})
        assert response.status_code == 200, response.text
        assert response.json()['result'] == row
        assert response.json()['source_sha256'] == record.sha256
    before = path.read_bytes()
    response = post(project, 'scenario', {**body, 'year': 2024, 'mitigation_production': 350})
    assert response.status_code == 200
    inputs = parse_leakage_template(path)
    changed = replace(inputs, monitored=tuple((year, mp, Decimal(350) if year == 2024 else omp, yield_per_ha)
                                             for year, mp, omp, yield_per_ha in inputs.monitored))
    assert response.json()['result'] == calculate_leakage(changed)['annual_results'][1]
    assert path.read_bytes() == before
    assert post(project, 'preview', body).json() == preview.json()


def test_scenario_rejects_wrong_project_missing_or_unvalidated_sources(scenario_api):
    post, project, other, record, path = scenario_api
    body = {'workbook_id': str(record.id), 'year': 2023, 'mitigation_production': 200}
    assert post(other, 'scenario', body).status_code == 404
    assert post(project, 'scenario', {**body, 'workbook_id': str(uuid4())}).status_code == 404
    for field, invalid in [('module_version', '9'), ('file_role', 'original-workbook'),
                           ('template_validation', None), ('template_version', '9')]:
        old = getattr(record, field)
        setattr(record, field, invalid)
        assert post(project, 'scenario', body).status_code == 409
        setattr(record, field, old)
    path.unlink()
    assert post(project, 'scenario', body).json()['error']['code'] == 'source_missing'


@pytest.mark.parametrize('changes', [
    {'year': 2030}, {'year': '2023'}, {'year': 2023.5},
    {'mitigation_production': -1}, {'mitigation_production': 'NaN'},
    {'mitigation_production': 'Infinity'}, {'mitigation_production': 1000000},
    {'unexpected': 123}, {'workbook_id': 'invalid'},
])
def test_scenario_rejects_invalid_inputs(scenario_api, changes):
    post, project, other, record, path = scenario_api
    body = {'workbook_id': str(record.id), 'year': 2023, 'mitigation_production': 200}
    assert post(project, 'scenario', {**body, **changes}).status_code == 422
