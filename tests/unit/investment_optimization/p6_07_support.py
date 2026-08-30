"""P6-07 fixtures. Amounts stay on transient payloads and test doubles only."""

from __future__ import annotations

from decimal import Decimal

from app.investment_optimization.advanced_service import AdvancedOptimizationService
from app.investment_optimization.assumptions import pin_assumptions
from app.investment_optimization.compile_native import NativeOptimizeSpec
from app.investment_optimization.constraints import constraint_authority, pin_constraint_set
from app.investment_optimization.contracts import (
    FlightingAssumption,
    FutureScenarioAssumptions,
    GroupConstraint,
    LockedLineConstraint,
    MediaUnitCostAssumption,
    MovementConstraint,
    NativeOptimizerRawResult,
    OptimizationConstraintSet,
    OptimizerBudgetLine,
    OptimizerBudgetVector,
    PortfolioLineConstraint,
    ReserveConstraint,
    UnitValueAssumption,
    WeightedGroupConstraint,
)
from app.investment_optimization.enums import (
    AssumptionAuthority,
    ConstraintAuthority,
    ConstraintFamily,
    MediaUnitCostKind,
    ModelVariableOptimizationEligibility,
)
from app.investment_optimization.store import InMemoryOptimizationMetadataStore
from app.service.object_store import FakeObjectStore, ObjectStore
from tests.unit.investment_optimization.p6_04_support import PROJECT, now
from tests.unit.investment_optimization.p6_05_support import (
    FakeEntitlementRepo,
    ScriptedFixedBudgetOptimizer,
)


class ScriptedFlexibleBudgetOptimizer(ScriptedFixedBudgetOptimizer):
    """Deterministic flexible-budget test double. Not a production solver."""

    def __init__(
        self,
        spends: dict[str, float] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        super().__init__(spends, error=error)
        self.specs: list[NativeOptimizeSpec] = []

    def optimize_flexible_budget(
        self,
        *,
        model_artifact_ref: str,
        vector: OptimizerBudgetVector,
        spec: NativeOptimizeSpec,
        object_store: ObjectStore | None = None,
        artifact_bucket: str | None = None,
    ) -> NativeOptimizerRawResult:
        self.specs.append(spec)
        return self.optimize_fixed_budget(
            model_artifact_ref=model_artifact_ref,
            vector=vector,
            object_store=object_store,
            artifact_bucket=artifact_bucket,
        )


def auth(*, reason: str = "committee lock") -> object:
    return constraint_authority(
        source="investment_plan",
        authority=ConstraintAuthority.HUMAN_CONFIRMED,
        scope="project",
        period="2027-Q1",
        reason=reason,
    )


def budget_line(
    variable_id: str = "search_spend",
    *,
    market_id: str = "mkt_us",
    channel_id: str = "search_paid",
    baseline: str = "100.00",
    eligibility: ModelVariableOptimizationEligibility = (
        ModelVariableOptimizationEligibility.OPTIMIZABLE
    ),
) -> OptimizerBudgetLine:
    return OptimizerBudgetLine(
        model_variable_id=variable_id,
        market_id=market_id,
        channel_id=channel_id,
        baseline=Decimal(baseline),
        eligibility=eligibility,
    )


def cost_assumption(
    *,
    ref_id: str = "cost_search",
    channel_id: str = "search_paid",
    value: str = "12.50",
) -> MediaUnitCostAssumption:
    return MediaUnitCostAssumption(
        ref_id=ref_id,
        kind=MediaUnitCostKind.CPM,
        unit="impressions",
        currency="USD",
        period="2027-Q1",
        channel_id=channel_id,
        source="business_iq",
        freshness="2026-08-01",
        value=Decimal(value),
    )


def flighting_assumption(
    *,
    ref_id: str = "flight_search",
    channel_id: str = "search_paid",
    weight: str = "1.00",
) -> FlightingAssumption:
    return FlightingAssumption(
        ref_id=ref_id,
        channel_id=channel_id,
        period="2027-Q1",
        weight=Decimal(weight),
        source="business_iq",
        authority=AssumptionAuthority.HUMAN_CONFIRMED,
    )


def governed_revenue(*, value: str = "4.00") -> UnitValueAssumption:
    return UnitValueAssumption(
        ref_id="rev_kpi",
        source="business_iq",
        scope="national",
        currency="USD",
        time_horizon="2027",
        freshness="2026-08-01",
        value=Decimal(value),
    )


def pinned_assumptions(**kwargs) -> FutureScenarioAssumptions:
    payload = FutureScenarioAssumptions(
        assumption_set_id=kwargs.pop("assumption_set_id", "oasm_testaaaaaaaaaaaaaa"),
        project_id=kwargs.pop("project_id", PROJECT),
        period_start=kwargs.pop("period_start", "2027-01-01"),
        period_end=kwargs.pop("period_end", "2027-03-31"),
        **kwargs,
    )
    return pin_assumptions(payload, created_at=now())


def line_bound(
    line_id: str = "search_spend",
    *,
    family: ConstraintFamily = ConstraintFamily.LINE_MIN,
    lower: str | None = None,
    upper: str | None = None,
) -> PortfolioLineConstraint:
    return PortfolioLineConstraint(
        constraint_id=f"c_{family.value.lower()}_{line_id}",
        family=family,
        line_id=line_id,
        market_id="mkt_us",
        channel_id="search_paid",
        period="2027-Q1",
        lower=None if lower is None else Decimal(lower),
        upper=None if upper is None else Decimal(upper),
        authority=auth(),
    )


def locked_line(line_id: str = "search_spend", *, baseline: str = "100.00") -> LockedLineConstraint:
    return LockedLineConstraint(
        constraint_id=f"c_lock_{line_id}",
        line_id=line_id,
        market_id="mkt_us",
        channel_id="search_paid",
        period="2027-Q1",
        baseline=Decimal(baseline),
        reason="contractual hold",
        authority=auth(reason="contractual hold"),
    )


def movement(
    line_id: str = "search_spend",
    *,
    family: ConstraintFamily = ConstraintFamily.MAX_ABSOLUTE_MOVE,
    abs_move: str | None = None,
    pct_move: str | None = None,
    percent_unavailable: bool = False,
) -> MovementConstraint:
    return MovementConstraint(
        constraint_id=f"c_move_{line_id}",
        family=family,
        line_id=line_id,
        market_id="mkt_us",
        channel_id="search_paid",
        period="2027-Q1",
        max_absolute_move=None if abs_move is None else Decimal(abs_move),
        max_percent_move=None if pct_move is None else Decimal(pct_move),
        percent_unavailable=percent_unavailable,
        authority=auth(),
    )


def group(
    *,
    family: ConstraintFamily,
    group_id: str,
    members: tuple[str, ...],
    lower: str | None = None,
    upper: str | None = None,
) -> GroupConstraint:
    return GroupConstraint(
        constraint_id=f"c_{family.value.lower()}_{group_id}",
        family=family,
        group_id=group_id,
        member_line_ids=members,
        lower=None if lower is None else Decimal(lower),
        upper=None if upper is None else Decimal(upper),
        period="2027-Q1",
        authority=auth(),
    )


def funnel(
    *,
    family: ConstraintFamily = ConstraintFamily.FUNNEL_FLOOR,
    members: tuple[tuple[str, str], ...] = (("search_spend", "1.00"),),
    lower: str | None = "50.00",
    upper: str | None = None,
) -> WeightedGroupConstraint:
    return WeightedGroupConstraint(
        constraint_id="c_funnel_primary",
        family=family,
        group_id="upper_funnel",
        member_weights=tuple((line_id, Decimal(weight)) for line_id, weight in members),
        lower=None if lower is None else Decimal(lower),
        upper=None if upper is None else Decimal(upper),
        period="2027-Q1",
        authority=auth(),
    )


def reserve(*, amount: str = "10.00") -> ReserveConstraint:
    return ReserveConstraint(
        constraint_id="c_experiment",
        family=ConstraintFamily.EXPERIMENT_RESERVE,
        amount=Decimal(amount),
        period="2027-Q1",
        reason="holdout",
        authority=auth(reason="holdout"),
    )


def constraint_set(**kwargs) -> OptimizationConstraintSet:
    payload = OptimizationConstraintSet(
        constraint_set_id=kwargs.pop("constraint_set_id", "ocst_testaaaaaaaaaaaaaa"),
        project_id=kwargs.pop("project_id", PROJECT),
        currency="USD",
        period_start="2027-01-01",
        period_end="2027-03-31",
        **kwargs,
    )
    return pin_constraint_set(payload)


def advanced_service(store=None, object_store=None) -> AdvancedOptimizationService:
    return AdvancedOptimizationService(
        repo=FakeEntitlementRepo(),  # type: ignore[arg-type]
        store=store or InMemoryOptimizationMetadataStore(),
        object_store=object_store or FakeObjectStore(),
        artifact_bucket="prem3-test-artifacts",
    )


def persist_constraint(service: AdvancedOptimizationService, payload: OptimizationConstraintSet):
    from tests.unit.investment_optimization.p6_05_support import bound

    return bound(
        lambda: service.create_constraint_set(
            project_id=PROJECT,
            actor_id="user_music_center",
            constraint_set=payload,
        )
    )


def persist_assumption(service: AdvancedOptimizationService, payload: FutureScenarioAssumptions):
    from tests.unit.investment_optimization.p6_05_support import bound

    return bound(
        lambda: service.create_assumption_set(
            project_id=PROJECT,
            actor_id="user_music_center",
            assumptions=payload,
        )
    )
