"""Template format and validation use synthetic inputs only."""
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

from app.core.config import Settings
from app.core.errors import AppError
from app.services.templates import workbook_intake_template, validate_intake_template
from app.services.workbooks import validate_package


def completed_template() -> bytes:
    output = BytesIO()
    with ZipFile(BytesIO(workbook_intake_template())) as source, ZipFile(output, "w", ZIP_DEFLATED) as target:
        for name in source.namelist():
            content = source.read(name)
            if name == "xl/worksheets/sheet1.xml":
                content = content.replace(b"</sheetData>",
                    b'<row r="7"><c r="A7" t="inlineStr"><is><t>Area</t></is></c>'
                    b'<c r="B7"><v>12</v></c><c r="C7" t="inlineStr"><is><t>ha</t></is></c>'
                    b'</row></sheetData>')
            target.writestr(name, content)
    return output.getvalue()


def test_template_is_valid_xlsx_and_requires_entries(tmp_path):
    path = tmp_path / "template.xlsx"
    path.write_bytes(workbook_intake_template())
    validate_package(path, Settings())
    with pytest.raises(AppError) as error:
        validate_intake_template(path)
    assert error.value.details == [{"cell": "Inputs!A7", "message": "Enter at least one field and value."}]
    path.write_bytes(completed_template())
    validate_package(path, Settings())
    validate_intake_template(path)


def test_wrong_version_and_missing_value_give_cell_locations(tmp_path):
    path = tmp_path / "template.xlsx"
    data = completed_template()
    output = BytesIO()
    with ZipFile(BytesIO(data)) as source, ZipFile(output, "w", ZIP_DEFLATED) as target:
        for name in source.namelist():
            content = source.read(name)
            if name == "xl/worksheets/sheet1.xml":
                content = content.replace(b"<t>1.0.0</t>", b"<t>9.0.0</t>", 1)
                content = content.replace(b'<c r="B7"><v>12</v></c>', b'')
            target.writestr(name, content)
    path.write_bytes(output.getvalue())
    with pytest.raises(AppError) as error:
        validate_intake_template(path)
    assert {item["cell"] for item in error.value.details} == {"Inputs!B3", "Inputs!B7"}
