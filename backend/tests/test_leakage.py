"""Arithmetic and input-contract tests; values are synthetic, not VCS claims."""
from io import BytesIO
from decimal import Decimal
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.core.config import Settings
from app.core.errors import AppError
from app.services.leakage import _legacy_leakage_template, leakage_template_version, LeakageInputs, calculate_leakage, leakage_template, parse_leakage_template
from app.services.workbooks import validate_package

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def filled_leakage_template(*, mitigation=40803, project=0, history_years=(2019, 2020, 2021), overrides=None) -> bytes:
    values = {'B8': 'Cattle', 'B9': 'head', 'B10': 2022, 'B14': 35.4552,
              'B15': 38, 'B16': 1, 'B17': 0.9, 'B18': 1}
    for row, year, produced, outside in zip(range(22, 25), history_years,
                                            (6417, 6086, 5311), (24915, 24141, 21919)):
        values.update({f'A{row}': year, f'B{row}': produced, f'C{row}': outside})
    values.update({'A28': 2023, 'B28': project, 'C28': mitigation, 'D28': 0.35051887865076975})
    values.update(overrides or {})
    output = BytesIO()
    with ZipFile(BytesIO(_legacy_leakage_template())) as source, ZipFile(output, 'w', ZIP_DEFLATED) as target:
        for name in source.namelist():
            data = source.read(name)
            if name == 'xl/worksheets/sheet1.xml':
                root = ElementTree.fromstring(data)
                sheet_data = root.find(NS + 'sheetData')
                rows = {int(row.get('r')): row for row in sheet_data}
                for address, value in values.items():
                    row_number = int(''.join(char for char in address if char.isdigit()))
                    row = rows.setdefault(row_number, ElementTree.Element(NS + 'row', {'r': str(row_number)}))
                    for existing in list(row):
                        if existing.get('r') == address:
                            row.remove(existing)
                    cell = ElementTree.Element(NS + 'c', {'r': address})
                    if isinstance(value, str):
                        cell.set('t', 'inlineStr')
                        ElementTree.SubElement(ElementTree.SubElement(cell, NS + 'is'), NS + 't').text = value
                    else:
                        ElementTree.SubElement(cell, NS + 'v').text = str(value)
                    row.append(cell)
                sheet_data[:] = [rows[number] for number in sorted(rows)]
                data = ElementTree.tostring(root, encoding='utf-8', xml_declaration=True)
            target.writestr(name, data)
    return output.getvalue()


def test_zero_is_caused_by_mitigation_exceeding_foregone_production(tmp_path):
    path = tmp_path / 'leakage.xlsx'
    path.write_bytes(filled_leakage_template())
    validate_package(path, Settings())
    inputs = parse_leakage_template(path)
    result = calculate_leakage(inputs)
    year = result['annual_results'][0]
    assert year['baseline_project_production'] == pytest.approx(5938 * 1.025)
    assert year['leakage_mitigation'] == pytest.approx(40803 - (24915 + 24141 + 21919) / 3 * 1.025)
    assert year['leakage_mitigation'] > year['foregone_production']
    assert year['production_subject_to_leakage'] == 0
    assert year['leakage_t_co2e'] == 0


def test_positive_leakage_follows_equations_six_to_ten(tmp_path):
    path = tmp_path / 'leakage.xlsx'
    path.write_bytes(filled_leakage_template(mitigation=0))
    inputs = parse_leakage_template(path)
    row = calculate_leakage(inputs)['annual_results'][0]
    assert row['production_subject_to_leakage'] > 0
    assert row['new_land_area_ha'] == pytest.approx(row['production_subject_to_leakage'] * 0.75 * 0.40 / 0.35051887865076975)
    assert row['carbon_stock_change_t_c_per_ha'] == pytest.approx(35.4552 + 38 * (1 - 0.9))
    assert row['leakage_t_co2e'] == pytest.approx(row['new_land_area_ha'] * row['carbon_stock_change_t_c_per_ha'] * 44 / 12)


def test_reference_years_must_precede_project_start(tmp_path):
    path = tmp_path / 'leakage.xlsx'
    path.write_bytes(filled_leakage_template(history_years=(2020, 2021, 2022)))
    with pytest.raises(AppError) as error:
        parse_leakage_template(path)
    assert error.value.code == 'invalid_leakage_inputs'
    assert {'Inputs!A22', 'Inputs!A23', 'Inputs!A24'} <= {item['cell'] for item in error.value.details}


def test_blank_template_never_calculates(tmp_path):
    path = tmp_path / 'leakage.xlsx'
    path.write_bytes(_legacy_leakage_template())
    with pytest.raises(AppError) as error:
        parse_leakage_template(path)
    assert error.value.code == 'invalid_leakage_inputs'
    assert 'Inputs!B14' in {item['cell'] for item in error.value.details}


def test_template_guidance_and_highlighted_inputs(tmp_path):
    path = tmp_path / 'template.xlsx'
    path.write_bytes(_legacy_leakage_template())
    validate_package(path, Settings())
    with ZipFile(path) as archive:
        book = ElementTree.fromstring(archive.read('xl/workbook.xml'))
        assert [sheet.get('name') for sheet in book.find(NS + 'sheets')] == ['Inputs', 'Instructions', 'Example']
        inputs = ElementTree.fromstring(archive.read('xl/worksheets/sheet1.xml'))
        cells = {cell.get('r'): cell for cell in inputs.iter(NS + 'c')}
        for address in ('B8', 'B10', 'B14', 'A22', 'C24', 'A28', 'D32'):
            assert cells[address].get('s') == '1'
            assert not ''.join(node.text or '' for node in cells[address].iter(NS + 't'))
        guide = archive.read('xl/worksheets/sheet2.xml').decode()
        assert 'Missing data is not zero.' in guide
        assert 'Inputs!B14' in guide
        assert 't C/ha' in guide
        assert '789.25 t CO2e' in archive.read('xl/worksheets/sheet3.xml').decode()


def test_documented_synthetic_example_has_the_stated_result(tmp_path):
    values = {'B14': 10, 'B15': 20, 'B16': 1, 'B17': 0.8, 'B18': 1, 'C28': 205, 'D28': 2}
    for row in range(22, 25):
        values.update({f'B{row}': 100, f'C{row}': 200})
    path = tmp_path / 'example.xlsx'
    path.write_bytes(filled_leakage_template(overrides=values))
    assert calculate_leakage(parse_leakage_template(path))['total_leakage_t_co2e'] == pytest.approx(789.25)
    values['C28'] = 400
    path.write_bytes(filled_leakage_template(overrides=values))
    assert calculate_leakage(parse_leakage_template(path))['total_leakage_t_co2e'] == 0


def test_older_single_sheet_leakage_templates_remain_accepted(tmp_path):
    from app.services.templates import build_inputs_template, read_inputs_cells
    path = tmp_path / 'older.xlsx'
    path.write_bytes(filled_leakage_template())
    cells, _ = read_inputs_cells(path, allowed_support_sheets=('Instructions', 'Example'))
    from app.services.templates import _cell
    rows = {}
    for address, value in cells.items():
        rows.setdefault(int(address[1:]), []).append(_cell(address, value))
    path.write_bytes(build_inputs_template(rows, freeze_row=7))
    assert calculate_leakage(parse_leakage_template(path))['total_leakage_t_co2e'] == 0


def test_official_vmd0054_appendix_one_rounded_example():
    # The publication rounds intermediate values; compare its year-five result within 1%.
    d = Decimal
    inputs = LeakageInputs('Cattle', 'head', 2022, d('0.025'), d('0.75'), d('0.40'),
        d('130.6'), d('60'), d('1'), d('0.7'), d('1'),
        (d('300'), d('330'), d('360')),
        (d('400'), d('420'), d('440')),
        ((2027, d('0'), d('536'), d('1.70')),))
    row = calculate_leakage(inputs)['annual_results'][0]
    assert row['t'] == 5
    assert row['leakage_t_co2e'] == pytest.approx(30048, rel=0.01)


def test_table_template_has_one_protected_table_per_sheet(tmp_path):
    path = tmp_path / 'reference.xlsx'
    path.write_bytes(leakage_template())
    validate_package(path, Settings())
    with ZipFile(path) as archive:
        book = ElementTree.fromstring(archive.read('xl/workbook.xml'))
        assert [s.get('name') for s in book.find(NS + 'sheets')] == ['Info', 'Parameters', 'Historical', 'Monitoring']
        assert book.find(NS + 'workbookProtection').get('lockStructure') == '1'
        for index in range(1, 5):
            sheet = ElementTree.fromstring(archive.read(f'xl/worksheets/sheet{index}.xml'))
            assert sheet.find(NS + 'tableParts').get('count') == '1'
            assert sheet.find(NS + 'sheetProtection').get('sheet') == '1'
            table = ElementTree.fromstring(archive.read(f'xl/tables/table{index}.xml'))
            assert table.get('ref').startswith('A1:')
        styles = ElementTree.fromstring(archive.read('xl/styles.xml'))
        assert styles.find(NS + 'cellXfs')[1].find(NS + 'protection').get('locked') == '0'


def test_unmodified_reference_replays_with_original_year_labels(tmp_path):
    from app.services.templates import read_inputs_cells
    from app.services.leakage_workbook import SHEETS
    path = tmp_path / 'reference.xlsx'
    path.write_bytes(leakage_template())
    def read(name):
        return read_inputs_cells(path, sheet_name=name, allowed_support_sheets=tuple(s for s in SHEETS if s != name))[0]
    parameters = read('Parameters')
    assert parameters['B4'] == '2022'
    assert float(parameters['B8']) == pytest.approx(35.4552)
    history = read('Historical')
    assert [history[f'A{r}'] for r in (2, 3, 4)] == ['2020', '2021', '2022']
    assert [history[f'B{r}'] for r in (2, 3, 4)] == ['6417', '6086', '5311']
    assert [history[f'C{r}'] for r in (2, 3, 4)] == ['24915', '24141', '21919']
    monitor = read('Monitoring')
    assert [monitor[f'C{r}'] for r in range(2, 7)] == ['40803'] * 5
    assert float(monitor['D2']) == pytest.approx(.35051887865076975)
    assert leakage_template_version(path) == '0.2.0'
    preview = calculate_leakage(parse_leakage_template(path))
    assert preview['reference_replay'] is True
    assert [row['year'] for row in preview['historical_production']] == [2020, 2021, 2022]
    assert preview['project_area_ha'] == pytest.approx(16940.59967)
    assert preview['total_leakage_t_co2e'] == 0



def test_separate_table_example_is_valid_and_has_the_documented_result(tmp_path):
    path = tmp_path / 'test-example.xlsx'
    path.write_bytes(leakage_template(example=True))
    validate_package(path, Settings())
    result = calculate_leakage(parse_leakage_template(path))
    assert result['annual_results'][0]['leakage_t_co2e'] == pytest.approx(789.25)
    assert [row['year'] for row in result['annual_results']] == list(range(2023, 2028))


def test_download_route_returns_reference_or_separate_test_example(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from uuid import uuid4
    from app.api import routes
    project = SimpleNamespace(methodology_id='VM0047', methodology_version='1.0')
    monkeypatch.setattr(routes, 'get_project', lambda *args: project)
    reference = routes.download_template(uuid4(), 'leakage-single-commodity', '0.1.0', example=False, session=object())
    example = routes.download_template(uuid4(), 'leakage-single-commodity', '0.1.0', example=True, session=object())
    assert 'VCS5511-reference-template-v0.2.0.xlsx' in reference.headers['content-disposition']
    assert 'synthetic-test-example-v0.2.0.xlsx' in example.headers['content-disposition']
    assert reference.body != example.body
    path = tmp_path / 'download.xlsx'
    path.write_bytes(example.body)
    assert calculate_leakage(parse_leakage_template(path))['annual_results'][0]['leakage_t_co2e'] == pytest.approx(789.25)


@pytest.mark.parametrize('replacement', [
    ('Project production', 'Moved production'),
    ('<v>205</v>', '<f>1+204</f><v>205</v>'),
    ('</sheetData>', '<row r="7"><c r="A7"><v>2024</v></c></row></sheetData>'),
])
def test_new_table_rejects_changed_columns_formulas_and_extra_rows(tmp_path, replacement):
    path = tmp_path / 'changed.xlsx'
    output = BytesIO()
    with ZipFile(BytesIO(leakage_template(example=True))) as original, ZipFile(output, 'w', ZIP_DEFLATED) as edited:
        for name in original.namelist():
            data = original.read(name)
            if name == 'xl/worksheets/sheet4.xml':
                data = data.replace(replacement[0].encode(), replacement[1].encode())
            edited.writestr(name, data)
    path.write_bytes(output.getvalue())
    with pytest.raises(AppError) as error:
        parse_leakage_template(path)
    assert all(item['cell'].startswith('Monitoring!') for item in error.value.details)
