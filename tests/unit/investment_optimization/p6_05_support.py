"""P6-05 fixtures. Amounts stay on transient PortfolioView / result payload only."""

from __future__ import annotations

from datetime import UTC, datetime

from app.control_plane.entitlements import PlanId, entitlement_for_plan
from app.control_plane.models import EntitlementSource
from app.core.tenancy import AuthState, TenantContext, bind_tenant
from app.investment_optimization.accepted_model import MemoryAcceptedModelDirectory
from app.investment_optimization.adapter import FixedBudgetOptimizer
from app.investment_optimization.consumption import MemoryModelConsumptionSource
from app.investment_optimization.contracts import (
    NativeOptimizerChannelResult,
    NativeOptimizerRawResult,
    OptimizerBudgetVector,
)
from app.investment_optimization.coverage import assemble_optimization_evidence_coverage
from app.investment_optimization.enums import ModelVariableOptimizationEligibility
from app.investment_optimization.mapping import build_portfolio_model_mapping
from app.investment_optimization.readiness import (
    build_optimization_input_contract,
    evaluate_readiness,
)
from app.investment_optimization.run_service import OptimizationRunService
from app.investment_optimization.store import InMemoryOptimizationMetadataStore
from app.investment_planning.enums import PortfolioCoverageState
from app.service.object_store import FakeObjectStore, ObjectStore
from tests.unit.investment_optimization.p6_04_support import (
    PROJECT,
    TENANT,
    complete_contract,
    model_version,
    now,
    portfolio_view,
    snapshot,
)


class ScriptedFixedBudgetOptimizer:
    """Deterministic test double. Not a production solver."""

    def __init__(
        self,
        spends: dict[str, float] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.spends = spends
        self.error = error
        self.calls: list[dict[str, object]] = []

    def optimize_fixed_budget(
        self,
        *,
        model_artifact_ref: str,
        vector: OptimizerBudgetVector,
        object_store: ObjectStore | None = None,
        artifact_bucket: str | None = None,
    ) -> NativeOptimizerRawResult:
        del object_store, artifact_bucket
        self.calls.append(
            {
                "model_artifact_ref": model_artifact_ref,
                "variable_ids": tuple(line.model_variable_id for line in vector.lines),
            }
        )
        if self.error is not None:
            raise self.error
        channels: list[NativeOptimizerChannelResult] = []
        for line in vector.lines:
            if line.eligibility is not ModelVariableOptimizationEligibility.OPTIMIZABLE:
                continue
            if self.spends is not None and line.model_variable_id in self.spends:
                spend = self.spends[line.model_variable_id]
            else:
                spend = float(line.baseline)
            channels.append(
                NativeOptimizerChannelResult(
                    model_variable_id=line.model_variable_id,
                    recommended_spend=spend,
                )
            )
        return NativeOptimizerRawResult(channels=tuple(channels))


class FakePlanning:
    plan_status = "APPROVED"
    drive_writes: list[str]

    def __init__(self, snap, view) -> None:
        self.snapshot = snap
        self.view = view
        self.drive_writes = []
        self.plan_revisions: list[str] = []

    def assemble_portfolio(self, *, project_id: str, fiscal_year: int | None, actor_id: str):
        del project_id, fiscal_year, actor_id
        return PortfolioCoverageState.PLAN_ONLY, self.snapshot, self.view


class FakeEntitlementRepo:
    def get_current_entitlement(self, tenant_id: str):
        return entitlement_for_plan(
            tenant_id=tenant_id,
            plan_id=PlanId.PORTFOLIO,
            source=EntitlementSource.BILLING_PROVIDER,
            now=datetime(2026, 8, 27, tzinfo=UTC),
        )


def tenant_ctx() -> TenantContext:
    return TenantContext(
        tenant_id=TENANT,
        user_id="user_music_center",
        auth_state=AuthState.AUTHENTICATED,
    )


def persist_ready(*, view=None, contract=None, snap=None, version=None):
    view = view or portfolio_view()
    contract = contract or complete_contract()
    snap = snap or snapshot()
    version = version or model_version()
    mapping = build_portfolio_model_mapping(
        tenant_id=TENANT,
        project_id=PROJECT,
        snapshot_id=view.snapshot_id,
        baseline_kind=view.baseline_kind,
        view=view,
        contract=contract,
        created_at=now(),
        created_by="user_music_center",
    )
    coverage = assemble_optimization_evidence_coverage(mapping=mapping, contract=contract)
    input_contract = build_optimization_input_contract(
        tenant_id=TENANT,
        project_id=PROJECT,
        snapshot=snap,
        view=view,
        mapping=mapping,
        contract=contract,
        created_at=now(),
        issues=(),
    )
    receipt = evaluate_readiness(
        tenant_id=TENANT,
        project_id=PROJECT,
        coverage_state=PortfolioCoverageState.PLAN_ONLY,
        snapshot=snap,
        view=view,
        contract=contract,
        mapping=mapping,
        coverage=coverage,
        input_contract=input_contract,
        created_at=now(),
    )
    return mapping, coverage, input_contract, receipt, contract, version, view, snap


def run_service(
    *,
    optimizer: FixedBudgetOptimizer | None = None,
    view=None,
    contract=None,
    snap=None,
    version=None,
    object_store: ObjectStore | None = None,
    execute_inline: bool = True,
):
    mapping, coverage, input_contract, receipt, contract, version, view, snap = persist_ready(
        view=view, contract=contract, snap=snap, version=version
    )
    store = InMemoryOptimizationMetadataStore()
    store.put(mapping)
    store.put(coverage)
    store.put(input_contract)
    store.put(receipt)
    store.put(contract)
    consumption = MemoryModelConsumptionSource()
    consumption.put(contract)
    models = MemoryAcceptedModelDirectory()
    models.put(version)
    service = OptimizationRunService(
        repo=FakeEntitlementRepo(),  # type: ignore[arg-type]
        store=store,
        planning=FakePlanning(snap, view),  # type: ignore[arg-type]
        models=models,
        consumption=consumption,
        object_store=object_store or FakeObjectStore(),
        artifact_bucket="prem3-test-artifacts",
        optimizer=optimizer or ScriptedFixedBudgetOptimizer(),
        execute_inline=execute_inline,
    )
    return service, receipt, store, mapping, input_contract, contract, version, models


def bound(service_call):
    with bind_tenant(tenant_ctx()):
        return service_call()
