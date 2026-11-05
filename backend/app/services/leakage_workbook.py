"""Version 0.2 table-based Leakage intake and a documented reference snapshot."""
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
import re

from app.services.templates import build_inputs_template, read_inputs_cells, NS
from app.core.errors import AppError

VERSION = '0.2.0'
BLANK_VERSION = '0.3.0'
AREA_FIELDS = ('Project area', 'Leakage mitigation area')
REFERENCE_AREAS = (16940.59967, 133089.4584)
DATA_YEARS = (-3, -2, -1, 0, 1, 2, 3, 4, 5)
SHEETS = ('Info', 'Parameters', 'Historical', 'Monitoring')
SOURCE = 'VCS5511_ARR_Brazil_Leakage_20260416-.xlsx'
FIELDS = (
    ('Commodity', 'text'), ('Production unit', 'text'), ('Project start year', 'year'),
    ('Annual growth rate r', 'decimal'), ('Share of displaced supply IS', 'decimal'),
    ('Share from new land NL', 'decimal'), ('Biomass carbon stock loss', 't C/ha'),
    ('Reference SOC stock', 't C/ha'), ('SOC land-use factor fLU', 'factor'),
    ('SOC management factor fMG', 'factor'), ('SOC input factor fIN', 'factor'),
)
HEADERS = {
    'Info': ('Topic', 'Details'),
    'Data': ('Relative year', 'Calendar year', 'Project area (head)', 'Mitigation area (head)', 'Expected new-land yield (head/ha)'),
    'Parameters': ('Parameter', 'Value', 'Unit', 'Source / note'),
    'Historical': ('Year', 'Project production', 'Mitigation production', 'Source / note'),
    'Monitoring': ('Year', 'Project production', 'Mitigation production', 'New-land yield', 'Source / note'),
}


def workbook_tables(*, example=False):
    """A fixed snapshot, never relabelled to make the reference-period check pass."""
    values = ['Cattle', 'head', 2022, .025, .75, .40, 35.455200000000005, 38, 1, .9, 1]
    sources = ['VCS5511_ARR!C11 (commodity label)', 'Historical Production Data!C7 (Heads)',
               'VCS5511_ARR!C5', 'VCS5511_ARR!D15', 'VCS5511_ARR!O15 formula: 0.75',
               'VCS5511_ARR!O15 formula: 0.4', 'VCS5511_ARR!Q15 cached value (20.4*1.58*1.1)',
               'VCS5511_ARR!W15', 'VCS5511_ARR!R15', 'VCS5511_ARR!S15', 'VCS5511_ARR!T15']
    historical = [[2020 + i, p, m, f'Historical Production Data!B{8+i}:C{8+i}; B{18+i}:C{18+i}']
                  for i, (p, m) in enumerate(zip((6417, 6086, 5311), (24915, 24141, 21919))) ]
    monitoring = [[2023 + i, 0, 40803, .35051887865076975,
                   f'VCS5511_ARR!A{15+i},G{15+i},K{15+i},N{15+i}; yield is cached formula output']
                  for i in range(5)]
    purpose = 'VCS5511 reference sample for workbook replay.'
    if example:
        values = ['Cattle', 'head', 2022, .025, .75, .40, 10, 20, 1, .8, 1]
        sources = ['Invented test input; not VCS5511 project evidence.'] * len(values)
        historical = [[year, 100, 200, 'Invented test data.'] for year in (2019, 2020, 2021)]
        monitoring = [[year, 0, 205, 2, 'Invented test data.' if year == 2023 else 'Illustrative assumption carried forward from 2023.']
                      for year in range(2023, 2028)]
        purpose = 'SYNTHETIC TEST EXAMPLE ONLY — expected 2023 leakage: 789.25 t CO2e.'
    info = [
        ['Template version', VERSION], ['Methodology', 'VM0047'], ['Methodology version', '1.0'],
        ['Rule module', 'VMD0054'], ['Rule module version', '1.0'], ['Purpose', purpose],
        ['How to fill', 'Each data sheet contains one table. Edit yellow cells only; titles, units and sources are locked to reduce accidental format changes. Do not add, remove or rename sheets, rows or columns.'],
        ['Reference source', SOURCE if not example else 'No source project: all values in this file are invented for testing.'],
        ['Reference-year issue', 'Source start year is 2022, but source historical years are 2020–2022. Upload the unchanged sample for arithmetic replay. Customer templates use the three complete calendar years before project start. Preserve source labels.' if not example else 'History 2019–2021 precedes the invented start year 2022.'],
        ['Reference evidence issue', 'Source K14:K19 contains the hard-coded mitigation production 40803 without linked underlying monitoring records. Carbon and soil inputs also require source review.' if not example else 'This example is for software testing only; it is not project evidence.'],
        ['Parameters', 'Commodity and production unit define all production entries. Growth and shares are decimals (0.025 = 2.5%). Biomass loss and reference soil organic carbon are t C/ha. fLU, fMG and fIN are dimensionless soil-carbon factors requiring applicable reference data.'],
        ['Historical', 'Enter exactly three complete years immediately before the start year. Production columns contain annual totals, not averages or per-hectare values. Longer crop rotations are outside this pilot.'],
        ['Monitoring', 'Enter one to five consecutive years starting the year after project start. Fill all four input columns in each used row; unused rows must be fully blank. The source year 2022 (t=0) is not included in this pilot monitoring table.'],
        ['Mitigation production', 'Annual total production on outside land used to maintain output displaced by the project. Enter total output, not its increase. If there is no mitigation area, explicitly enter 0 for all historical and used monitoring mitigation values. Unknown is not zero.'],
        ['Units and values', 'Use the same production unit throughout. For head, new-land yield is head/ha and must be positive. Type numeric values only, without units or formulas.'],
        ['Testing', 'Download the separate synthetic test example to try a valid upload. The 2023 result is 789.25 t CO2e. Changing Monitoring!C2 to 400 gives zero in 2023. Rows through 2027 are synthetic.'],
        ['Protection', 'Worksheet and workbook protection prevent accidental editing only; they are not a security control. The server checks structure, values and years independently.'],
        ['Official reference', 'https://verra.org/wp-content/uploads/2023/09/VMD0054_ARR-Leakage-Module_v1.0.pdf'],
    ]
    area_values = (250, 500) if example else REFERENCE_AREAS
    area_sources = ('Invented example area.',) * 2 if example else ('VCS5511_ARR!C4', 'VCS5511_ARR!C7')
    parameters = [[field, value, unit, source] for (field, unit), value, source in zip(FIELDS, values, sources)]
    parameters.extend([field, value, 'ha', source] for field, value, source in zip(AREA_FIELDS, area_values, area_sources))
    return {'Info': info, 'Parameters': parameters,
            'Historical': historical, 'Monitoring': monitoring}


def blank_workbook_tables():
    info = [
        ['Template version', BLANK_VERSION], ['Methodology', 'VM0047'], ['Methodology version', '1.0'],
        ['Rule module', 'VMD0054'], ['Rule module version', '1.0'],
        ['Start here', 'Fill yellow cells only. Use whole calendar years and enter values rather than Excel formulas.'],
        ['Year 0', 'Enter the calendar year the project started in Parameters!B4. Year 0 is shown in Data for orientation. There is no Year 0 monitoring calculation in this pilot.'],
        ['Years -3 to -1', 'Enter the three calendar years before Year 0 and the historical cattle totals for both areas. Leave new-land yield blank on these rows.'],
        ['Years 1 to 5', 'Starting the year after Year 0, enter the calendar year and observed cattle totals for both areas. Fill at least Year 1, then consecutive years as records become available. Leave unused future rows blank.'],
        ['Mitigation area', 'Enter the total cattle count in the area receiving displaced production. Use zero only when supported, including when there is no mitigation area. Unknown is not zero.'],
        ['New-land yield', 'Enter the expected cattle supported per hectare if new land were brought into production. Use a positive, supported value. The app calculates hectares and emissions.'],
        ['Parameters', 'Use supported growth and land-carbon values. Growth and supply shares use decimals (0.025 = 2.5%). Enter both areas in hectares to display production density.'],
    ]
    return {'Info': info, 'Data': [[year, '', '', '', ''] for year in DATA_YEARS],
            'Parameters': [[field, value, unit, ''] for (field, unit), value in
                           zip(FIELDS, ['Cattle', 'head'] + [''] * 9)] +
                           [[field, '', 'ha', 'Optional for density charts'] for field in AREA_FIELDS]}


def table_workbook(*, example=False, blank=False) -> bytes:
    tables = blank_workbook_tables() if blank else workbook_tables(example=example)
    with ZipFile(BytesIO(build_inputs_template({}, freeze_row=1))) as seed:
        styles = ET.fromstring(seed.read('xl/styles.xml'))
    editable = styles.find(NS + 'cellXfs')[1]
    editable.set('applyProtection', '1')
    ET.SubElement(editable, NS + 'protection', {'locked': '0'})
    parts = {'xl/styles.xml': ET.tostring(styles, encoding='utf-8')}
    types = ['<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
             '<Default Extension="xml" ContentType="application/xml"/>',
             '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
             '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
    relbase = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
    relns = 'http://schemas.openxmlformats.org/package/2006/relationships'
    relations = [f'<Relationship Id="styles" Type="{relbase}styles" Target="styles.xml"/>']
    sheet_tags = []
    for index, (name, body) in enumerate(tables.items(), 1):
        headers = HEADERS[name]
        width = len(headers)
        end = f'{chr(64+width)}{len(body)+1}'
        rows = []
        for r, values in enumerate([headers, *body], 1):
            cells = []
            for c, value in enumerate(values, 1):
                can_edit = r > 1 and ((name == 'Parameters' and c == 2) or
                    (name == 'Historical' and c <= 3) or (name == 'Monitoring' and c <= 4) or
                    (name == 'Data' and ((2 <= r <= 4 and 2 <= c <= 4) or (6 <= r <= 10 and 2 <= c <= 5))))
                style = 2 if r == 1 else 1 if can_edit else 3
                address = f'{chr(64+c)}{r}'
                content = f'<v>{value}</v>' if isinstance(value, (float, int)) else f'<is><t>{escape(str(value))}</t></is>'
                kind = '' if isinstance(value, (float, int)) else ' t="inlineStr"'
                cells.append(f'<c r="{address}" s="{style}"{kind}>{content}</c>')
            height = 30 if r == 1 else 72 if name == 'Info' else 48
            rows.append(f'<row r="{r}" ht="{height}" customHeight="1">{"".join(cells)}</row>')
        widths = (30, 105) if name == 'Info' else (38, 22, 22, 72) if name == 'Parameters' else (16, 18, 24, 25, 38) if name == 'Data' else (16, 25, 25, 72) if name == 'Historical' else (16, 25, 25, 25, 72)
        cols = ''.join(f'<col min="{c}" max="{c}" width="{w}" customWidth="1"/>' for c, w in enumerate(widths, 1))
        parts[f'xl/worksheets/sheet{index}.xml'] = (
            f'<worksheet xmlns="{NS[1:-1]}" xmlns:r="{relbase[:-1]}">'
            f'<dimension ref="A1:{end}"/><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews>'
            f'<cols>{cols}</cols><sheetData>{"".join(rows)}</sheetData>'
            '<sheetProtection sheet="1" objects="1" scenarios="1" selectLockedCells="1" selectUnlockedCells="0"/>'
            '<tableParts count="1"><tablePart r:id="table1"/></tableParts></worksheet>')
        parts[f'xl/worksheets/_rels/sheet{index}.xml.rels'] = f'<Relationships xmlns="{relns}"><Relationship Id="table1" Type="{relbase}table" Target="../tables/table{index}.xml"/></Relationships>'
        columns = ''.join(f'<tableColumn id="{c}" name="{escape(label)}"/>' for c, label in enumerate(headers, 1))
        parts[f'xl/tables/table{index}.xml'] = f'<table xmlns="{NS[1:-1]}" id="{index}" name="Leakage{name}" displayName="Leakage{name}" ref="A1:{end}" totalsRowShown="0"><tableColumns count="{width}">{columns}</tableColumns><tableStyleInfo name="TableStyleMedium4" showRowStripes="0"/></table>'
        for part, content_type in [(f'worksheets/sheet{index}.xml', 'worksheet'), (f'tables/table{index}.xml', 'table')]:
            types.append(f'<Override PartName="/xl/{part}" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.{content_type}+xml"/>')
        sheet_tags.append(f'<sheet name="{name}" sheetId="{index}" r:id="rId{index}"/>')
        relations.append(f'<Relationship Id="rId{index}" Type="{relbase}worksheet" Target="worksheets/sheet{index}.xml"/>')
    parts['[Content_Types].xml'] = f'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">{"".join(types)}</Types>'
    parts['_rels/.rels'] = f'<Relationships xmlns="{relns}"><Relationship Id="rId1" Type="{relbase}officeDocument" Target="xl/workbook.xml"/></Relationships>'
    parts['xl/_rels/workbook.xml.rels'] = f'<Relationships xmlns="{relns}">{"".join(relations)}</Relationships>'
    parts['xl/workbook.xml'] = f'<workbook xmlns="{NS[1:-1]}" xmlns:r="{relbase[:-1]}"><workbookProtection lockStructure="1"/><bookViews><workbookView activeTab="0"/></bookViews><sheets>{"".join(sheet_tags)}</sheets></workbook>'
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    return output.getvalue()


def read_table_inputs(path, *, blank=False):
    errors, data = [], {}
    sheets = ('Info', 'Data', 'Parameters') if blank else SHEETS
    for name in sheets:
        cells, issues = read_inputs_cells(path, sheet_name=name, allowed_support_sheets=tuple(s for s in sheets if s != name))
        errors.extend(issues)
        for index, header in enumerate(HEADERS[name], 1):
            address = f'{chr(64+index)}1'
            if cells.get(address) != header:
                errors.append({'cell': f'{name}!{address}', 'message': f'Expected {header!r}. Do not move table columns.'})
        last_row = {'Info': 13 if blank else 19, 'Parameters': 14, 'Historical': 4, 'Monitoring': 6, 'Data': 10}[name]
        for address, value in cells.items():
            match = re.fullmatch(r'([A-Z])([1-9][0-9]*)', address)
            if not match or (value.strip() and (int(match[2]) > last_row or ord(match[1]) > 64 + len(HEADERS[name]))):
                errors.append({'cell': f'{name}!{address}', 'message': 'Enter data only inside the supplied table.'})
        data[name] = cells
    expected_info = [('Template version', BLANK_VERSION if blank else VERSION), ('Methodology', 'VM0047'), ('Methodology version', '1.0'), ('Rule module', 'VMD0054'), ('Rule module version', '1.0')]
    for row, (label, value) in enumerate(expected_info, 2):
        for col, expected in [('A', label), ('B', value)]:
            if data['Info'].get(f'{col}{row}') != expected:
                errors.append({'cell': f'Info!{col}{row}', 'message': f'Expected {expected!r}.'})
    cells = {'B2': 'VM0047', 'B3': '1.0', 'B4': 'VMD0054', 'B5': '1.0', 'B6': '0.1.0',
             'A21': 'Year', 'B21': 'Project production', 'C21': 'Mitigation-area production',
             'A27': 'Year', 'B27': 'Project production', 'C27': 'Mitigation-area production', 'D27': 'New-land yield (units/ha)'}
    addresses = {}
    for row, (field, unit) in enumerate(FIELDS, 2):
        for col, expected in [('A', field), ('C', unit)]:
            if data['Parameters'].get(f'{col}{row}') != expected:
                errors.append({'cell': f'Parameters!{col}{row}', 'message': f'Expected {expected!r}.'})
        old = f'B{row+6}'
        cells[old] = data['Parameters'].get(f'B{row}', '')
        addresses[old] = f'Parameters!B{row}'
    if blank:
        for row, year in enumerate(DATA_YEARS, 2):
            if data['Data'].get(f'A{row}') != str(year):
                errors.append({'cell': f'Data!A{row}', 'message': f'Expected relative year {year}.'})
        for address in ('E2', 'E3', 'E4', 'B5', 'C5', 'D5', 'E5'):
            if data['Data'].get(address, '').strip():
                errors.append({'cell': f'Data!{address}', 'message': 'Leave this cell blank.'})
    for name, start, count, cols in [('Historical', 22, 3, 'ABC'), ('Monitoring', 28, 5, 'ABCD')]:
        for index in range(count):
            for column, col in enumerate(cols):
                old = f'{col}{start+index}'
                sheet = 'Data' if blank else name
                address = f'{"BCDE"[column]}{index + (2 if start == 22 else 6)}' if blank else f'{col}{index+2}'
                cells[old] = data[sheet].get(address, '')
                addresses[old] = f'{sheet}!{address}'
    for row, field in enumerate(AREA_FIELDS, 13):
        if data['Parameters'].get(f'A{row}') not in (None, field) or data['Parameters'].get(f'C{row}') not in (None, 'ha'):
            errors.append({'cell': f'Parameters!A{row}', 'message': f'Expected {field} in hectares.'})
        old = f'B{row+6}'
        cells[old] = data['Parameters'].get(f'B{row}', '')
        addresses[old] = f'Parameters!B{row}'
    reference = False
    if not blank:
        reference = all(
            data[name].get(f'{chr(65 + column)}{row}', '') == str(value)
            for name, rows in workbook_tables().items() if name != 'Info'
            for row, values in enumerate(rows, 2)
            if name != 'Parameters' or row <= 12 or data[name].get(f'B{row}', '')
            for column, value in enumerate(values)
            if not isinstance(value, str) or name == 'Parameters' and column == 1
        )
    if errors:
        raise AppError(422, 'invalid_leakage_inputs', 'Keep the template tables unchanged and correct the listed cells.', errors[:40])
    return cells, addresses, reference
