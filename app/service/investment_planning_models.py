"""Presentation contracts for Investment Plan HTTP. Metadata only; no amounts."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.investment_planning.enums import BudgetScope
from app.service.models import ApiModel


class CreateInvestmentPlanRequest(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    fiscal_year: int
    currency: str = "USD"
    budget_scope: BudgetScope = BudgetScope.PAID_MEDIA_ONLY


class BindDriveBudgetSourceRequest(ApiModel):
    drive_file_id: str = Field(min_length=1, max_length=128)


class ConfirmBudgetMappingRequest(ApiModel):
    mapping_id: str
    market_column: str | None = None
    channel_column: str | None = None
    quarter_columns: tuple[str, ...] | None = None


class ValidateInvestmentPlanRequest(ApiModel):
    mapping_id: str | None = None
    blanks_acknowledged: bool = False


class ApproveInvestmentPlanRequest(ApiModel):
    receipt_id: str


class InvestmentPlanResponse(ApiModel):
    plan_id: str
    project_id: str
    workspace_id: str
    name: str
    fiscal_year: int
    fiscal_start_month: int
    currency: str
    budget_scope: str
    business_profile_snapshot_id: str
    business_profile_fingerprint: str
    active_source_version_id: str | None = None
    status: str
    revision: int
    predecessor_plan_id: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by: str
    approved_at: datetime | None = None
    approved_by: str | None = None


class InvestmentPlanListResponse(ApiModel):
    items: tuple[InvestmentPlanResponse, ...]


class BudgetSourceResponse(ApiModel):
    source_version_id: str
    plan_id: str
    drive_file_id: str
    file_name: str
    mime_type: str
    drive_version: str | None = None
    head_revision_id: str | None = None
    md5_checksum: str | None = None
    schema_version: str
    predecessor_source_version_id: str | None = None
    created_at: datetime
    created_by: str


class BudgetMappingResponse(ApiModel):
    mapping_id: str
    plan_id: str
    source_version_id: str
    market_column: str | None = None
    channel_column: str | None = None
    quarter_columns: tuple[str, ...] = ()
    initiative_column: str | None = None
    confirmed: bool
    ambiguous: tuple[str, ...] = ()


class BudgetDriveSourceAcceptedResponse(ApiModel):
    source: BudgetSourceResponse
    mapping: BudgetMappingResponse


class InvestmentPlanValidationResponse(ApiModel):
    receipt_id: str
    plan_id: str
    source_version_id: str
    status: str
    error_codes: tuple[str, ...] = ()
    flagged_row_indexes: tuple[int, ...] = ()
    flagged_headers: tuple[str, ...] = ()


class InvestmentPlanReadyResponse(ApiModel):
    plan_id: str
    status: str
    receipt_id: str | None = None
    error_codes: tuple[str, ...] = ()


class MoneyAmountResponse(ApiModel):
    kind: str
    currency: str
    value: str | None = None
    missing: bool = False


class PortfolioAllocationResponse(ApiModel):
    fiscal_year: int
    quarter: int
    market_id: str
    channel_id: str
    channel_registry_version: int
    amounts: tuple[MoneyAmountResponse, ...] = ()


class PortfolioDimensionTotalResponse(ApiModel):
    market_id: str | None = None
    channel_id: str | None = None
    amount: MoneyAmountResponse


class QuarterlyPortfolioResponse(ApiModel):
    quarter: int
    summary: tuple[MoneyAmountResponse, ...] = ()


class PortfolioFreshnessResponse(ApiModel):
    plan_source_as_of: datetime | None = None
    actuals_as_of: datetime | None = None
    measurement_as_of: datetime | None = None


class InvestmentPortfolioResponse(ApiModel):
    coverage_state: str
    snapshot_id: str | None = None
    project_id: str
    workspace_id: str
    fiscal_year: int | None = None
    currency: str | None = None
    baseline_kind: str | None = None
    summary: tuple[MoneyAmountResponse, ...] = ()
    remaining: MoneyAmountResponse | None = None
    allocations: tuple[PortfolioAllocationResponse, ...] = ()
    channel_allocation: tuple[PortfolioDimensionTotalResponse, ...] = ()
    market_allocation: tuple[PortfolioDimensionTotalResponse, ...] = ()
    quarterly: tuple[QuarterlyPortfolioResponse, ...] = ()
    freshness: PortfolioFreshnessResponse | None = None
