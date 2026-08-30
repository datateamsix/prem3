"""Shared P6-04 fixtures. Amounts stay on transient PortfolioView only."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.investment_optimization.consumption import validate_consumption_contract
from app.investment_optimization.contracts import (
    ModelConsumptionContract,
    ModelConsumptionVariable,
)
from app.investment_optimization.enums import (
    PINNED_MERIDIAN_RUNTIME,
    ModelGeoSemantics,
    ModelVariableOptimizationEligibility,
    ModelVariableRole,
    SpendSemantics,
)
from app.investment_planning.contracts import (
    MoneyAmount,
    PortfolioAllocationView,
    PortfolioEvidenceCoverage,
    PortfolioObservation,
    PortfolioSnapshotRef,
    PortfolioSourceFreshness,
    PortfolioSummary,
    PortfolioView,
)
from app.investment_planning.enums import (
    AmountKind,
    ObservationSeverity,
    PortfolioBaselineKind,
    PortfolioObservationType,
)
from app.modeling.mmm.contracts import MMMModelVersion
from app.modeling.mmm.states import MMMModelingStage

TENANT = "ten_bbbbbbbbbbbbbbbbbbbb"
PROJECT = "wsp_cccccccccccccccccccc"
SNAPSHOT_ID = "psnap_aaaaaaaaaaaaaaaaaaa"
MODEL_ID = "mver_aaaaaaaaaaaaaaaaaaaa"


def now() -> datetime:
    return datetime(2026, 8, 27, tzinfo=UTC)


def approved_amount(value: str = "100.00") -> MoneyAmount:
    return MoneyAmount(
        kind=AmountKind.APPROVED, currency="USD", value=Decimal(value), missing=False
    )


def snapshot(
    *,
    baseline: PortfolioBaselineKind = PortfolioBaselineKind.APPROVED_PLAN,
    fingerprint: str = "fp_snap",
) -> PortfolioSnapshotRef:
    return PortfolioSnapshotRef(
        snapshot_id=SNAPSHOT_ID,
        tenant_id=TENANT,
        project_id=PROJECT,
        workspace_id=PROJECT,
        fiscal_year=2027,
        baseline_kind=baseline,
        investment_plan_id="ipln_aaaaaaaaaaaaaaaaaaaa",
        business_profile_snapshot_id="bps_dddddddddddddddddddd",
        fingerprint=fingerprint,
        created_at=now(),
        created_by="user_music_center",
    )


def allocation(market_id: str, channel_id: str, value: str = "100.00") -> PortfolioAllocationView:
    return PortfolioAllocationView(
        fiscal_year=2027,
        quarter=1,
        market_id=market_id,
        channel_id=channel_id,
        channel_registry_version=1,
        amounts=(approved_amount(value),),
    )


def portfolio_view(
    *,
    rows: tuple[PortfolioAllocationView, ...] | None = None,
    baseline: PortfolioBaselineKind = PortfolioBaselineKind.APPROVED_PLAN,
    observations: tuple[PortfolioObservation, ...] = (),
    currency: str = "USD",
) -> PortfolioView:
    cells = rows or (allocation("mkt_us", "search_paid"),)
    total = approved_amount("100.00")
    return PortfolioView(
        snapshot_id=SNAPSHOT_ID,
        tenant_id=TENANT,
        project_id=PROJECT,
        fiscal_year=2027,
        currency=currency,
        baseline_kind=baseline,
        summary=PortfolioSummary(currency=currency, totals=(total,)),
        allocations=cells,
        coverage=PortfolioEvidenceCoverage(),
        freshness=PortfolioSourceFreshness(),
        observations=observations,
    )


def observation(kind: PortfolioObservationType) -> PortfolioObservation:
    return PortfolioObservation(
        observation_id="pobs_aaaaaaaaaaaaaaaaaaaa",
        project_id=PROJECT,
        observation_type=kind,
        severity=ObservationSeverity.ERROR,
        message_key=kind.value,
    )


def spend_variable(
    variable_id: str = "search_spend",
    channel_id: str = "search_paid",
    *,
    eligibility: ModelVariableOptimizationEligibility = (
        ModelVariableOptimizationEligibility.OPTIMIZABLE
    ),
    role: ModelVariableRole = ModelVariableRole.MEDIA_SPEND,
    semantics: SpendSemantics | None = SpendSemantics.APPROVED_MEDIA_SPEND,
    market_id: str | None = None,
) -> ModelConsumptionVariable:
    return ModelConsumptionVariable(
        model_variable_id=variable_id,
        model_variable_name=variable_id,
        variable_role=role,
        eligibility=eligibility,
        spend_semantics=semantics,
        canonical_channel_id=channel_id,
        canonical_market_id=market_id,
    )


def complete_contract(
    *,
    variables: tuple[ModelConsumptionVariable, ...] | None = None,
    geo: ModelGeoSemantics = ModelGeoSemantics.NATIONAL,
    currency: str = "USD",
    window: tuple[str, str] = ("2024-01-01", "2026-12-31"),
    future_horizon_allowed: bool = True,
    meridian_version: str = PINNED_MERIDIAN_RUNTIME,
    optimizer_artifact_ref: str | None = "gs://models/accepted.bin",
    response_evidence_ref: str | None = "gs://models/response.json",
    accepted_state: str = "MODEL_ACCEPTED",
    model_version_id: str = MODEL_ID,
    tenant_id: str = TENANT,
    project_id: str = PROJECT,
) -> ModelConsumptionContract:
    contract = ModelConsumptionContract(
        consumption_contract_id="omcc_aaaaaaaaaaaaaaaaaaaa",
        tenant_id=tenant_id,
        project_id=project_id,
        model_version_id=model_version_id,
        model_plan_fingerprint="fp_plan",
        model_consumption_contract_fingerprint="",
        model_acceptance_ref="macc_aaaaaaaaaaaaaaaaaaaa",
        meridian_version=meridian_version,
        runtime_mode="OFFICIAL_MERIDIAN_RUNTIME",
        accepted_model_state=accepted_state,
        modeled_window_start=window[0],
        modeled_window_end=window[1],
        geo_semantics=geo,
        currency=currency,
        kpi="revenue",
        variables=variables or (spend_variable(),),
        optimizer_artifact_ref=optimizer_artifact_ref,
        response_evidence_ref=response_evidence_ref,
        model_spec_ref="mplan_aaaaaaaaaaaaaaaaaaa",
        future_horizon_allowed=future_horizon_allowed,
        fingerprint="",
    )
    return validate_consumption_contract(contract)


def model_version(
    *,
    model_version_id: str = MODEL_ID,
    state: MMMModelingStage = MMMModelingStage.MODEL_ACCEPTED,
    accepted: bool = True,
    tenant_id: str = TENANT,
    project_id: str = PROJECT,
) -> MMMModelVersion:
    return MMMModelVersion(
        model_version_id=model_version_id,
        tenant_id=tenant_id,
        project_id=project_id,
        cycle_id="cyc_aaaaaaaaaaaaaaaaaaaa",
        track_id="trk_aaaaaaaaaaaaaaaaaaaa",
        model_ready_run_id="run_aaaaaaaaaaaaaaaaaaaa",
        model_ready_manifest_fingerprint="fp_ready",
        created_by="user_music_center",
        created_at=now(),
        state=state,
        accepted=accepted,
        meridian_version=PINNED_MERIDIAN_RUNTIME,
        model_plan_fingerprint="fp_plan",
        model_window_start="2024-01-01",
        model_window_end="2026-12-31",
    )
