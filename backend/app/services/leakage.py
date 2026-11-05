"""VMD0054 v1.0 single-commodity agricultural leakage arithmetic pilot.

This is a bounded calculation preview, not a verified VCS result. It excludes
fuelwood, multiple commodities, grouped instances, and evidence assessment.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zipfile import ZipFile
from defusedxml import ElementTree

from app.core.errors import AppError
from app.services.templates import _cell, build_inputs_template, read_inputs_cells, NS
from app.services.leakage_workbook import BLANK_VERSION, REFERENCE_AREAS, VERSION, table_workbook, read_table_inputs

MODULE_ID = "leakage-single-commodity"
MODULE_VERSION = "0.1.0"
TEMPLATE_VERSION = VERSION
LEGACY_TEMPLATE_VERSION = '0.1.0'
FILE_ROLE = "leakage-input-template"
METHODOLOGY_ID = "VM0047"
METHODOLOGY_VERSION = "1.0"
RULE_MODULE_ID = "VMD0054"
RULE_MODULE_VERSION = "1.0"
CO2_PER_C = Decimal(44) / Decimal(12)


def leakage_template(*, example: bool = False, blank: bool = False) -> bytes:
    return table_workbook(example=example, blank=blank)


def _legacy_leakage_template() -> bytes:
    rows: dict[int, list[str]] = {
        1: [_cell('A1', 'Thrive 2050 | Agricultural Leakage Pilot')],
        2: [_cell('A2', 'Methodology'), _cell('B2', METHODOLOGY_ID)],
        3: [_cell('A3', 'Methodology version'), _cell('B3', METHODOLOGY_VERSION)],
        4: [_cell('A4', 'Rule module'), _cell('B4', RULE_MODULE_ID)],
        5: [_cell('A5', 'Rule module version'), _cell('B5', RULE_MODULE_VERSION)],
        6: [_cell('A6', 'Template version'), _cell('B6', LEGACY_TEMPLATE_VERSION)],
        7: [_cell('A7', 'Start with Instructions. Fill yellow cells; Example is synthetic test data only.')],
        8: [_cell('A8', 'Commodity'), _cell('C8', 'Example: cattle')],
        9: [_cell('A9', 'Production unit'), _cell('C9', 'Example: head')],
        10: [_cell('A10', 'Project start year')],
        11: [_cell('A11', 'Annual growth rate r'), _cell('B11', '0.025'), _cell('C11', 'Default: 0.025')],
        12: [_cell('A12', 'Share of displaced supply IS'), _cell('B12', '0.75'), _cell('C12', 'Agricultural default: 0.75')],
        13: [_cell('A13', 'Share from new land NL'), _cell('B13', '0.40'), _cell('C13', 'Agricultural default: 0.40')],
        14: [_cell('A14', 'Biomass carbon stock loss (t C/ha)')],
        15: [_cell('A15', 'Reference SOC stock (t C/ha)')],
        16: [_cell('A16', 'SOC land-use factor fLU')],
        17: [_cell('A17', 'SOC management factor fMG')],
        18: [_cell('A18', 'SOC input factor fIN')],
        19: [_cell('A19', 'If no mitigation area exists, enter 0 in all mitigation production cells.')],
        20: [_cell('A20', 'Historical production: three years before project start')],
        21: [_cell('A21', 'Year'), _cell('B21', 'Project production'), _cell('C21', 'Mitigation-area production')],
        26: [_cell('A26', 'Monitored production: enter consecutive years, up to five')],
        27: [_cell('A27', 'Year'), _cell('B27', 'Project production'), _cell('C27', 'Mitigation-area production'),
             _cell('D27', 'New-land yield (units/ha)')],
        34: [_cell('A34', 'Preview only. Source evidence, eligibility, carrying capacity and other GHG effects require review.')],
    }
    for address in [*(f'B{row}' for row in range(8, 19)),
                    *(f'{col}{row}' for row in range(22, 25) for col in 'ABC'),
                    *(f'{col}{row}' for row in range(28, 33) for col in 'ABCD')]:
        row_number = int(address[1:])
        row = rows.setdefault(row_number, [])
        index = next((i for i, cell in enumerate(row) if f'r="{address}"' in cell), None)
        if index is None:
            row.append(_cell(address, '', style=1))
        else:
            row[index] = row[index].replace('s="0"', 's="1"')
        row.sort(key=lambda cell: cell.split('r="')[1].split('"')[0].rstrip('0123456789'))
    return build_inputs_template(dict(sorted(rows.items())), freeze_row=7,
                                 support_sheets=leakage_guides())


def leakage_guides() -> dict[str, dict[int, list[str]]]:
    """Human guidance is separate from the blank, authoritative Inputs sheet."""
    instructions = [
        ('START HERE', 'Where to fill', 'What to enter / where to find it', 'Example / unit'),
        ('1. Read first', 'Instructions / Example', 'Read this guide, then inspect the synthetic Example sheet. Only Inputs is used for calculation. Example values are not project evidence.', 'Keep all sheet names unchanged.'),
        ('2. Fill inputs', 'Yellow cells on Inputs', 'Enter numbers or text directly. Keep headings and B2:B6 unchanged. No formulas or external workbook links; paste values only. Do not type units inside number cells.', 'Save as .xlsx, then upload.'),
        ('Commodity', 'Inputs!B8', 'One agricultural product or livestock category. Use the same definition throughout the workbook.', 'Cattle (test example)'),
        ('Production unit', 'Inputs!B9', 'The unit of annual production. Project and mitigation production must use the same unit. Yield must use this unit per hectare.', 'head; or tonnes'),
        ('Start year', 'Inputs!B10', 'Project-instance start year, from the project documents. This pilot takes the three complete calendar years before it as history.', '2022 -> history 2019, 2020, 2021'),
        ('Growth rate r', 'Inputs!B11', 'Annual production growth as a decimal. The template supplies 0.025. Change only with appropriate methodological support.', '0.025 means 2.5% per year.'),
        ('Supply share IS', 'Inputs!B12', 'Share of displaced supply met by increased production elsewhere. Agricultural default supplied: 0.75. Supporting evidence for alternatives needs review.', '0.75 means 75%; not 75.'),
        ('New-land share NL', 'Inputs!B13', 'Share of increased production met by expanding agricultural land. Agricultural default supplied: 0.40.', '0.40 means 40%; not 40.'),
        ('Biomass carbon loss', 'Inputs!B14', 'Biomass carbon stock lost per hectare when new land is converted to agriculture. Obtain supported land-carbon estimates. This is not total project biomass or CO2 emissions.', 't C/ha; no default supplied'),
        ('Reference soil carbon', 'Inputs!B15', 'SOC means soil organic carbon. Reference stock per hectare for the relevant soil/climate, from documented reference data.', 't C/ha; no default supplied'),
        ('Land-use factor fLU', 'Inputs!B16', 'Soil-carbon factor for the resulting land use. Obtain a factor applicable to the land, climate and accounting conditions.', 'Dimensionless; no default supplied'),
        ('Management factor fMG', 'Inputs!B17', 'Soil-carbon factor for the relevant agricultural management practice. Use supported data, not an estimated percentage.', 'Dimensionless; no default supplied'),
        ('Input factor fIN', 'Inputs!B18', 'Soil-carbon factor for organic inputs/residue management. This combines with fLU and fMG to estimate soil-carbon change.', 'Dimensionless; no default supplied'),
        ('3. Historical years', 'Inputs!A22:A24', 'Enter exactly the three years before B10 in ascending order. Do not include the project start year. Longer crop rotations are outside this pilot.', 'If B10 = 2022: 2019, 2020, 2021'),
        ('Historical project output', 'Inputs!B22:B24', 'Annual production on the land that becomes the project area. Use production records for each historical year, not the three-year average.', 'Same production unit as B9'),
        ('Historical mitigation output', 'Inputs!C22:C24', 'Annual historical production on the leakage mitigation area. This is outside land used to maintain production displaced by the project; eligibility needs separate review.', 'Same production unit as B9'),
        ('4. Monitoring years', 'Inputs!A28:A32', 'Enter one to five consecutive monitoring years starting the year after B10. Fill all four columns in each used row. Leave unused rows entirely blank.', 'Start 2022 -> first row 2023'),
        ('Monitored project output', 'Inputs!B28:B32', 'Actual annual production remaining on the project area after project start, from monitoring records.', 'Same production unit as B9'),
        ('Monitored mitigation output', 'Inputs!C28:C32', 'Actual total annual production on the mitigation area. Enter total production, not the increase; the platform calculates the increase relative to baseline.', 'Same production unit as B9'),
        ('New-land yield', 'Inputs!D28:D32', 'Annual production per hectare on newly converted agricultural land. Use supported yield data representative of that land. Must be greater than zero.', 'If B9 = head: head/ha'),
        ('No mitigation area?', 'C22:C24 and used C28:C32', 'If no mitigation area exists, explicitly enter 0 for historical and monitored mitigation production. Otherwise enter actual supported production.', 'Missing data is not zero.'),
        ('Unknown carbon inputs?', 'Inputs!B14:B18', 'Obtain the necessary land/soil study or methodological reference before calculating a project result. The Example sheet is only for testing the application.', 'Do not substitute test values.'),
        ('Before upload', 'Inputs', 'Check units, years and sources. Do not insert/delete rows or move input cells. A blank template cannot calculate. Keep evidence records separately for review.', 'Upload as Completed Leakage template.'),
        ('Official reference', 'VMD0054 v1.0', 'Agricultural leakage arithmetic preview only. Project eligibility, mitigation evidence and other required emissions are outside the pilot.', 'https://verra.org/wp-content/uploads/2023/09/VMD0054_ARR-Leakage-Module_v1.0.pdf'),
    ]
    example = [
        ('SYNTHETIC EXAMPLE', 'Copy destination', 'Test value(s)', 'Meaning'),
        ('Test only', 'Inputs is still blank', 'These invented values demonstrate the upload flow. They are not VCS5511 data or evidence for any project.', 'Copy only when testing.'),
        ('Commodity', 'Inputs!B8', 'Cattle', 'One commodity'),
        ('Unit', 'Inputs!B9', 'head', 'Use head/ha for yield'),
        ('Start year', 'Inputs!B10', '2022', 'History precedes this year'),
        ('Growth', 'Inputs!B11', '0.025', 'Keep supplied default for test'),
        ('Supply share', 'Inputs!B12', '0.75', 'Keep supplied default for test'),
        ('New-land share', 'Inputs!B13', '0.40', 'Keep supplied default for test'),
        ('Biomass loss', 'Inputs!B14', '10', 'Invented t C/ha'),
        ('Reference SOC', 'Inputs!B15', '20', 'Invented t C/ha'),
        ('fLU', 'Inputs!B16', '1', 'Invented factor'),
        ('fMG', 'Inputs!B17', '0.8', 'Invented factor'),
        ('fIN', 'Inputs!B18', '1', 'Invented factor'),
        ('Historical row 1', 'Inputs!A22:C22', '2019 | 100 | 200', 'Year | project output | mitigation output'),
        ('Historical row 2', 'Inputs!A23:C23', '2020 | 100 | 200', 'Enter each value in its own cell.'),
        ('Historical row 3', 'Inputs!A24:C24', '2021 | 100 | 200', 'Enter each value in its own cell.'),
        ('Monitoring row 1', 'Inputs!A28:D28', '2023 | 0 | 205 | 2', 'Year | project output | mitigation output | yield'),
        ('Unused rows', 'Inputs!A29:D32', 'Leave entirely blank', 'One monitoring year in this test'),
        ('Expected preview', '2023', '789.25 t CO2e', 'Baseline project output 102.5; mitigation baseline 205; net mitigation 0; new land 15.375 ha.'),
        ('Zero-result test', 'Change Inputs!C28 only', '400', 'Expected leakage: 0. Increased mitigation production covers the production loss.'),
    ]
    return {name: {number: [_cell(f'{col}{number}', value, style=2 if number == 1 else 3)
                           for col, value in zip('ABCD', entries)]
                   for number, entries in enumerate(data, 1)}
            for name, data in [('Instructions', instructions), ('Example', example)]}


def _number(cells: dict[str, str], address: str, errors: list[dict], *,
            minimum: Decimal | None = None, maximum: Decimal | None = Decimal('1e12')) -> Decimal | None:
    raw = cells.get(address, '').strip()
    try:
        value = Decimal(raw)
        if not value.is_finite():
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        errors.append({'cell': f'Inputs!{address}', 'message': 'Enter a finite number.'})
        return None
    if minimum is not None and value < minimum:
        errors.append({'cell': f'Inputs!{address}', 'message': f'Value must be at least {minimum}.'})
    if maximum is not None and value > maximum:
        errors.append({'cell': f'Inputs!{address}', 'message': f'Value must be at most {maximum}.'})
    return value


def _year(cells: dict[str, str], address: str, expected: int, errors: list[dict]) -> None:
    value = _number(cells, address, errors)
    if value is not None and value != expected:
        errors.append({'cell': f'Inputs!{address}', 'message': f'Expected year {expected}.'})


@dataclass(frozen=True)
class LeakageInputs:
    commodity: str
    unit: str
    start_year: int
    growth_rate: Decimal
    increased_supply_share: Decimal
    new_land_share: Decimal
    biomass_carbon_loss: Decimal
    reference_soc: Decimal
    land_use_factor: Decimal
    management_factor: Decimal
    input_factor: Decimal
    historical_project: tuple[Decimal, Decimal, Decimal]
    historical_mitigation: tuple[Decimal, Decimal, Decimal]
    monitored: tuple[tuple[int, Decimal, Decimal, Decimal], ...]
    project_area: Decimal | None = None
    mitigation_area: Decimal | None = None
    reference: bool = False


def leakage_template_version(path: Path) -> str:
    with ZipFile(path) as archive:
        if archive.getinfo('xl/workbook.xml').file_size > 2 * 1024 * 1024:
            raise AppError(422, 'invalid_template', 'Template XML exceeds the supported size.')
        sheets = ElementTree.fromstring(archive.read('xl/workbook.xml')).find(NS + 'sheets')
        names = {sheet.get('name') for sheet in sheets} if sheets is not None else set()
        if 'Info' in names:
            return BLANK_VERSION if 'Data' in names else VERSION
        return LEGACY_TEMPLATE_VERSION


def parse_leakage_template(path: Path) -> LeakageInputs:
    version = leakage_template_version(path)
    if version in (VERSION, BLANK_VERSION):
        cells, addresses, reference = read_table_inputs(path, blank=version == BLANK_VERSION)
        try:
            return _parse_leakage_cells(cells, [], reference=reference)
        except AppError as exc:
            for issue in exc.details or []:
                old = issue['cell'].removeprefix('Inputs!')
                issue['cell'] = addresses.get(old, 'Parameters!B8:B12' if ':' in old else old)
            raise
    cells, errors = read_inputs_cells(path, allowed_support_sheets=('Instructions', 'Example'))
    return _parse_leakage_cells(cells, errors)


def _parse_leakage_cells(cells, errors, *, reference=False) -> LeakageInputs:
    expected = {'B2': METHODOLOGY_ID, 'B3': METHODOLOGY_VERSION,
                'B4': RULE_MODULE_ID, 'B5': RULE_MODULE_VERSION, 'B6': LEGACY_TEMPLATE_VERSION,
                'A21': 'Year', 'B21': 'Project production', 'C21': 'Mitigation-area production',
                'A27': 'Year', 'B27': 'Project production', 'C27': 'Mitigation-area production',
                'D27': 'New-land yield (units/ha)'}
    for address, value in expected.items():
        if cells.get(address) != value:
            errors.append({'cell': f'Inputs!{address}', 'message': f'Expected {value!r}.'})
    commodity = cells.get('B8', '').strip()
    unit = cells.get('B9', '').strip()
    for address, value in [('B8', commodity), ('B9', unit)]:
        if not value or len(value) > 100:
            errors.append({'cell': f'Inputs!{address}', 'message': 'Enter a name of at most 100 characters.'})
    start = _number(cells, 'B10', errors)
    valid_start = start is not None and 1900 <= start <= 2200 and start == start.to_integral_value()
    if start is not None and not valid_start:
        errors.append({'cell': 'Inputs!B10', 'message': 'Enter a calendar year between 1900 and 2200.'})
    start_year = int(start) if valid_start else 0
    growth = _number(cells, 'B11', errors, minimum=Decimal('-1'))
    supply = _number(cells, 'B12', errors, minimum=Decimal(0), maximum=Decimal(1))
    new_land = _number(cells, 'B13', errors, minimum=Decimal(0), maximum=Decimal(1))
    biomass = _number(cells, 'B14', errors, minimum=Decimal(0))
    soc_ref = _number(cells, 'B15', errors, minimum=Decimal(0))
    f_lu = _number(cells, 'B16', errors, minimum=Decimal(0))
    f_mg = _number(cells, 'B17', errors, minimum=Decimal(0))
    f_in = _number(cells, 'B18', errors, minimum=Decimal(0))
    history_project = []
    history_mitigation = []
    for index, row in enumerate(range(22, 25)):
        if start_year and not reference:
            _year(cells, f'A{row}', start_year - 3 + index, errors)
        history_project.append(_number(cells, f'B{row}', errors, minimum=Decimal(0)))
        history_mitigation.append(_number(cells, f'C{row}', errors, minimum=Decimal(0)))
    monitored = []
    gap = False
    for index, row in enumerate(range(28, 33)):
        addresses = [f'{col}{row}' for col in 'ABCD']
        if not any(cells.get(address, '').strip() for address in addresses):
            gap = True
            continue
        if gap:
            errors.append({'cell': f'Inputs!A{row}', 'message': 'Monitoring years must be consecutive.'})
        if start_year:
            _year(cells, f'A{row}', start_year + index + 1, errors)
        project = _number(cells, f'B{row}', errors, minimum=Decimal(0))
        mitigation = _number(cells, f'C{row}', errors, minimum=Decimal(0))
        yield_per_ha = _number(cells, f'D{row}', errors, minimum=Decimal('0.000000000001'))
        monitored.append((start_year + index + 1, project, mitigation, yield_per_ha))
    if not monitored:
        errors.append({'cell': 'Inputs!A28', 'message': 'Enter at least one monitoring year.'})
    for row in (25, 33):
        if any(cells.get(f'{column}{row}', '').strip() for column in 'ABCD'):
            errors.append({'cell': f'Inputs!A{row}', 'message': 'Extra historical or monitoring rows are not supported.'})
    if any(value.strip() for address, value in cells.items()
           if address[1:].isdigit() and int(address[1:]) > 34):
        errors.append({'cell': 'Inputs!A35', 'message': 'Only five monitoring years are supported.'})
    project_area = (_number(cells, 'B19', errors, minimum=Decimal('0.000000000001'))
                    if cells.get('B19', '').strip() else None)
    mitigation_area = (_number(cells, 'B20', errors, minimum=Decimal('0.000000000001'))
                       if cells.get('B20', '').strip() else None)
    if reference:
        project_area, mitigation_area = (Decimal(str(area)) for area in REFERENCE_AREAS)
    if errors:
        raise AppError(422, 'invalid_leakage_inputs', 'Correct the listed Leakage template cells.', errors[:40])
    return LeakageInputs(commodity, unit, start_year, growth, supply, new_land, biomass,
                         soc_ref, f_lu, f_mg, f_in, tuple(history_project),
                         tuple(history_mitigation), tuple(monitored), project_area, mitigation_area, reference)


def calculate_leakage(inputs: LeakageInputs) -> dict:
    """Apply VMD0054 v1.0 Equations 1-10 to one agricultural commodity."""
    bp_zero = sum(inputs.historical_project) / Decimal(3)
    obp_zero = sum(inputs.historical_mitigation) / Decimal(3)
    soc_change = inputs.reference_soc * (
        Decimal(1) - inputs.land_use_factor * inputs.management_factor * inputs.input_factor)
    carbon_stock_change = inputs.biomass_carbon_loss + soc_change
    if carbon_stock_change < 0:
        raise AppError(422, 'invalid_carbon_stock', 'Combined biomass and soil carbon stock change must not be negative.',
                       [{'cell': 'Inputs!B14:B18', 'message': 'Review carbon stock inputs and factors.'}])
    years = []
    total_leakage = Decimal(0)
    for year, mp, omp, yield_per_ha in inputs.monitored:
        t = year - inputs.start_year
        baseline_project = bp_zero * (Decimal(1) + inputs.growth_rate) ** t
        foregone = baseline_project - mp
        baseline_mitigation = obp_zero * (Decimal(1) + inputs.growth_rate) ** t
        mitigation = omp - baseline_mitigation
        subject_to_leakage = max(foregone - mitigation, Decimal(0))
        new_land_area = subject_to_leakage * inputs.increased_supply_share * inputs.new_land_share / yield_per_ha
        leakage = new_land_area * carbon_stock_change * CO2_PER_C
        total_leakage += leakage
        years.append({
            'year': year, 't': t,
            'monitored_project_production': float(mp),
            'monitored_mitigation_production': float(omp),
            'new_land_per_production_unit': float(inputs.increased_supply_share * inputs.new_land_share / yield_per_ha),
            'baseline_project_production': float(baseline_project),
            'foregone_production': float(foregone),
            'baseline_mitigation_production': float(baseline_mitigation),
            'leakage_mitigation': float(mitigation),
            'production_subject_to_leakage': float(subject_to_leakage),
            'new_land_area_ha': float(new_land_area),
            'carbon_stock_change_t_c_per_ha': float(carbon_stock_change),
            'leakage_t_co2e': float(leakage),
        })
    return {'status': 'preview', 'methodology': 'VM0047 v1.0', 'rule_module': 'VMD0054 v1.0',
            'scope': 'One agricultural commodity; one project instance; 1-5 monitoring years.',
            'commodity': inputs.commodity, 'production_unit': inputs.unit,
            'annual_results': years,
            'project_area_ha': float(inputs.project_area) if inputs.project_area is not None else None,
            'mitigation_area_ha': float(inputs.mitigation_area) if inputs.mitigation_area is not None else None,
            'reference_replay': inputs.reference,
            'historical_production': [
                {'year': inputs.start_year - (2 if inputs.reference else 3) + i, 'project': float(project), 'mitigation': float(mitigation)}
                for i, (project, mitigation) in enumerate(zip(inputs.historical_project, inputs.historical_mitigation))
            ],
            'total_leakage_t_co2e': float(total_leakage),
            'limitations': [
                *(['Reference workbook replay. Historical labels include the 2022 start year. Repeated monitoring entries are workbook inputs, including years beyond the first monitoring period.'] if inputs.reference else []),
                'Input evidence and applicability conditions have not been independently verified.',
                'Additional emissions from intensification, supplemental feed, and other effects are outside this preview.',
                'Multiple commodities, fuelwood, and grouped project instances are not supported.',
                'Historical production is limited to three complete calendar years; longer crop rotations are outside this pilot.',
                'The displayed total is an arithmetic sum of year-specific previews; VMD0054 calls LK_t cumulative and its reporting interpretation needs review.',
            ]}
