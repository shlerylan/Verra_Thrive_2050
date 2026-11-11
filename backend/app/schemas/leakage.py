from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class LeakagePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workbook_id: UUID


class LeakageScenarioRequest(LeakagePreviewRequest):
    year: int = Field(strict=True)
    mitigation_production: Decimal = Field(ge=0, allow_inf_nan=False)


class LeakageYear(BaseModel):
    year: int
    t: int
    scenario_max_mitigation_production: float
    zero_leakage_mitigation_production: float | None
    monitored_project_production: float
    monitored_mitigation_production: float
    new_land_per_production_unit: float
    baseline_project_production: float
    project_shortfall: float
    baseline_project_density: float | None
    monitored_project_density: float | None
    baseline_mitigation_density: float | None
    monitored_mitigation_density: float | None
    foregone_production: float
    baseline_mitigation_production: float
    leakage_mitigation: float
    production_subject_to_leakage: float
    new_land_area_ha: float
    carbon_stock_change_t_c_per_ha: float
    leakage_t_co2e: float


class HistoricalProduction(BaseModel):
    year: int
    project: float
    mitigation: float


class LeakagePreview(BaseModel):
    status: Literal["preview"]
    methodology: str
    rule_module: str
    scope: str
    commodity: str
    production_unit: str
    annual_results: list[LeakageYear]
    historical_production: list[HistoricalProduction]
    project_area_ha: float | None
    mitigation_area_ha: float | None
    reference_replay: bool
    total_leakage_t_co2e: float
    limitations: list[str]
    source_workbook_id: UUID
    source_sha256: str


class LeakageScenario(BaseModel):
    result: LeakageYear
    source_workbook_id: UUID
    source_sha256: str
