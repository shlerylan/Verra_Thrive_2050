"""Versioned workbook-intake template and layout validation.

This utility collects labelled inputs for future review; it has no carbon rules.
"""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from defusedxml import ElementTree

from app.core.errors import AppError

MODULE_ID = "workbook-intake"
MODULE_VERSION = "1.0.0"
TEMPLATE_VERSION = "1.0.0"
FILE_ROLE = "input-template"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _cell(address: str, value: str) -> str:
    return f'<c r="{address}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'


def workbook_intake_template() -> bytes:
    rows = {
        1: [_cell("A1", "Thrive 2050 | Workbook Intake")],
        2: [_cell("A2", "Module ID"), _cell("B2", MODULE_ID)],
        3: [_cell("A3", "Module version"), _cell("B3", MODULE_VERSION)],
        4: [_cell("A4", "Template version"), _cell("B4", TEMPLATE_VERSION)],
        5: [_cell("A5", "Enter one labelled input per row. No calculation is performed.")],
        6: [_cell("A6", "Field"), _cell("B6", "Value"), _cell("C6", "Unit"), _cell("D6", "Source")],
    }
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             f'<worksheet xmlns="{NS[1:-1]}"><sheetViews><sheetView workbookViewId="0">'
             '<pane ySplit="6" topLeftCell="A7" activePane="bottomLeft" state="frozen"/>'
             '</sheetView></sheetViews><cols><col min="1" max="1" width="28" customWidth="1"/>'
             '<col min="2" max="2" width="24" customWidth="1"/>'
             '<col min="3" max="3" width="18" customWidth="1"/>'
             '<col min="4" max="4" width="36" customWidth="1"/></cols><sheetData>'
             + ''.join(f'<row r="{number}">{"".join(cells)}</row>' for number, cells in rows.items())
             + '</sheetData></worksheet>')
    parts = {
        '[Content_Types].xml': '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>',
        '_rels/.rels': '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>',
        'xl/workbook.xml': '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Inputs" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>',
        'xl/worksheets/sheet1.xml': sheet,
    }
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    return output.getvalue()


def validate_intake_template(path: Path) -> None:
    """Reject missing/mismatched versions and give source-cell errors for user input."""
    errors: list[dict] = []
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            for part in ('xl/workbook.xml', 'xl/_rels/workbook.xml.rels', 'xl/sharedStrings.xml'):
                if part in names and archive.getinfo(part).file_size > 2 * 1024 * 1024:
                    raise ValueError('Template XML exceeds the supported size.')
            if any(name.startswith('xl/externalLinks/') for name in names):
                errors.append({'cell': 'Inputs', 'message': 'External workbook links are not supported.'})
            workbook = ElementTree.fromstring(archive.read('xl/workbook.xml'))
            sheets = workbook.find(NS + 'sheets')
            if sheets is None or len(sheets) != 1 or sheets[0].get('name') != 'Inputs':
                raise ValueError('The Inputs sheet is missing or renamed.')
            relation_id = sheets[0].get(REL_NS + 'id')
            relationships = ElementTree.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
            relation = next(item for item in relationships if item.get('Id') == relation_id)
            target = relation.get('Target', '')
            if (relation.get('TargetMode') == 'External' or not relation.get('Type', '').endswith('/worksheet')
                    or '..' in target.split('/') or '\\' in target):
                raise ValueError('The Inputs sheet relationship is invalid.')
            sheet_path = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            if not sheet_path.startswith('xl/worksheets/'):
                raise ValueError('The Inputs sheet relationship is invalid.')
            if archive.getinfo(sheet_path).file_size > 2 * 1024 * 1024:
                raise ValueError('The Inputs sheet exceeds the supported size.')
            sheet = ElementTree.fromstring(archive.read(sheet_path))
            if sheet.tag != NS + 'worksheet':
                raise ValueError('The Inputs sheet is invalid.')
            shared = []
            if 'xl/sharedStrings.xml' in names:
                strings = ElementTree.fromstring(archive.read('xl/sharedStrings.xml'))
                shared = [''.join(node.text or '' for node in item.iter(NS + 't')) for item in strings]
            cells = {}
            for cell in sheet.iter(NS + 'c'):
                address = cell.get('r', '')
                if address in cells:
                    raise ValueError(f'Duplicate cell {address}.')
                if cell.find(NS + 'f') is not None:
                    errors.append({'cell': f'Inputs!{address}', 'message': 'Formulas are not accepted in this template.'})
                value = cell.find(NS + 'v')
                if cell.get('t') == 'inlineStr':
                    content = ''.join(node.text or '' for node in cell.iter(NS + 't'))
                elif cell.get('t') == 's' and value is not None:
                    content = shared[int(value.text)]
                else:
                    content = value.text if value is not None else ''
                cells[address] = content or ''
    except (KeyError, IndexError, ValueError, TypeError, ElementTree.ParseError) as exc:
        raise AppError(422, 'invalid_template', 'The workbook does not match the supported intake template.',
                       [{'cell': 'Inputs', 'message': str(exc)}]) from exc

    expected = {'B2': MODULE_ID, 'B3': MODULE_VERSION, 'B4': TEMPLATE_VERSION,
                'A6': 'Field', 'B6': 'Value', 'C6': 'Unit', 'D6': 'Source'}
    for address, value in expected.items():
        if cells.get(address) != value:
            errors.append({'cell': f'Inputs!{address}', 'message': f'Expected {value!r}.'})
    entered = 0
    for row in range(7, 207):
        values = [cells.get(f'{column}{row}', '').strip() for column in 'ABCD']
        if any(values):
            entered += 1
            if not values[0]:
                errors.append({'cell': f'Inputs!A{row}', 'message': 'Enter a field name.'})
            if not values[1]:
                errors.append({'cell': f'Inputs!B{row}', 'message': 'Enter a value.'})
    if not entered:
        errors.append({'cell': 'Inputs!A7', 'message': 'Enter at least one field and value.'})
    if any(cell[0] in 'ABCD' and cell[1:].isdigit() and int(cell[1:]) > 206 and value.strip()
           for cell, value in cells.items()):
        errors.append({'cell': 'Inputs!A207', 'message': 'This template accepts at most 200 input rows.'})
    if errors:
        raise AppError(422, 'invalid_template', 'Correct the listed template cells and upload again.', errors[:30])
