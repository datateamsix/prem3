"""Compile PreM3 constraints/assumptions into native Meridian BudgetOptimizer kwargs."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.investment_optimization.assumptions import assumption_fingerprint
from app.investment_optimization.contracts import (
    FutureScenarioAssumptions,
    OptimizationConstraintSet,
    OptimizerBudgetVector,
)
from app.investment_optimization.enums import (
    PINNED_FLEXIBLE_SPEND_CONSTRAINT,
    PINNED_OPTIMIZER_GTOL,
    PINNED_SPEND_CONSTRAINT_LOWER,
    PINNED_SPEND_CONSTRAINT_UPPER,
    ModelVariableOptimizationEligibility,
    OptimizationBudgetMode,
    OptimizationObjectiveMode,
)
from app.investment_optimization.errors import FlexibleBudgetApiUnsupportedError
from app.investment_optimization.numeric import float_from_decimal, pct_of_spend
from app.investment_planning.actuals import round_money
from app.investment_planning.fingerprint import metadata_fingerprint


@dataclass(frozen=True)
class NativeOptimizeSpec:
    fixed_budget: bool
    budget: float | None
    pct_of_spend: tuple[float, ...]
    spend_constraint_lower: tuple[float, ...] | float
    spend_constraint_upper: tuple[float, ...] | float
    target_roi: float | None
    target_mroi: float | None
    use_kpi: bool
    use_posterior: bool
    gtol: float
    selected_geos: tuple[str, ...] | None
    start_date: str | None
    end_date: str | None
    new_data_kind: str
    fingerprint: str


def compile_native_spec(
    *,
    vector: OptimizerBudgetVector,
    mode: OptimizationObjectiveMode,
    budget_mode: OptimizationBudgetMode,
    constraint_set: OptimizationConstraintSet | None,
    assumptions: FutureScenarioAssumptions | None,
    target_roi: float | None,
    target_mroi: float | None,
    use_kpi: bool,
) -> NativeOptimizeSpec:
    if budget_mode is OptimizationBudgetMode.FLEXIBLE:
        if target_roi is not None and target_mroi is not None:
            raise FlexibleBudgetApiUnsupportedError(
                "Native Meridian 1.8.0 accepts target_roi or target_mroi, not both."
            )
        if target_roi is None and target_mroi is None:
            raise FlexibleBudgetApiUnsupportedError(
                "Flexible budget requires native target_roi or target_mroi."
            )
    shares = pct_of_spend(vector)
    budget_decimal, lower, upper = _spend_box(
        vector=vector,
        budget_mode=budget_mode,
        constraint_set=constraint_set,
    )
    new_data_kind = _new_data_kind(assumptions)
    start_date = None if assumptions is None else assumptions.period_start
    end_date = None if assumptions is None else assumptions.period_end
    geos = _selected_geos(constraint_set)
    spec = NativeOptimizeSpec(
        fixed_budget=budget_mode is OptimizationBudgetMode.FIXED,
        budget=None if budget_decimal is None else float_from_decimal(budget_decimal),
        pct_of_spend=shares,
        spend_constraint_lower=lower,
        spend_constraint_upper=upper,
        target_roi=target_roi if budget_mode is OptimizationBudgetMode.FLEXIBLE else None,
        target_mroi=target_mroi if budget_mode is OptimizationBudgetMode.FLEXIBLE else None,
        use_kpi=use_kpi,
        use_posterior=True,
        gtol=PINNED_OPTIMIZER_GTOL,
        selected_geos=geos,
        start_date=start_date,
        end_date=end_date,
        new_data_kind=new_data_kind,
        fingerprint="",
    )
    return spec.__class__(
        **{
            **spec.__dict__,
            "fingerprint": _spec_fingerprint(spec, assumptions),
        }
    )


def _spec_fingerprint(
    spec: NativeOptimizeSpec, assumptions: FutureScenarioAssumptions | None
) -> str:
    return metadata_fingerprint(
        {
            "fixed_budget": spec.fixed_budget,
            "budget": spec.budget,
            "pct_of_spend": list(spec.pct_of_spend),
            "spend_constraint_lower": spec.spend_constraint_lower
            if isinstance(spec.spend_constraint_lower, float)
            else list(spec.spend_constraint_lower),
            "spend_constraint_upper": spec.spend_constraint_upper
            if isinstance(spec.spend_constraint_upper, float)
            else list(spec.spend_constraint_upper),
            "target_roi": spec.target_roi,
            "target_mroi": spec.target_mroi,
            "use_kpi": spec.use_kpi,
            "gtol": spec.gtol,
            "selected_geos": None if spec.selected_geos is None else list(spec.selected_geos),
            "start_date": spec.start_date or "",
            "end_date": spec.end_date or "",
            "new_data_kind": spec.new_data_kind,
            "assumptions": "" if assumptions is None else assumption_fingerprint(assumptions),
        }
    )


def _spend_box(
    *,
    vector: OptimizerBudgetVector,
    budget_mode: OptimizationBudgetMode,
    constraint_set: OptimizationConstraintSet | None,
) -> tuple[Decimal, tuple[float, ...] | float, tuple[float, ...] | float]:
    approved = round_money(vector.fixed_budget)
    if constraint_set is None or (
        constraint_set.total_budget_bounds is None
        and not constraint_set.line_bounds
        and not constraint_set.movement_limits
        and not constraint_set.locked_lines
    ):
        if budget_mode is OptimizationBudgetMode.FIXED:
            return (
                approved,
                PINNED_SPEND_CONSTRAINT_LOWER,
                PINNED_SPEND_CONSTRAINT_UPPER,
            )
        return approved, PINNED_FLEXIBLE_SPEND_CONSTRAINT, PINNED_FLEXIBLE_SPEND_CONSTRAINT

    bounds = constraint_set.total_budget_bounds
    if budget_mode is OptimizationBudgetMode.FLEXIBLE and bounds is not None:
        lower_total = bounds.lower if bounds.lower is not None else Decimal("0")
        upper_total = bounds.upper if bounds.upper is not None else approved * Decimal("2")
        if lower_total > upper_total:
            raise FlexibleBudgetApiUnsupportedError("B_min must not exceed B_max.")
        midpoint = round_money((lower_total + upper_total) / Decimal("2"))
        if midpoint <= 0:
            raise FlexibleBudgetApiUnsupportedError(
                "Native spend-box compilation requires a positive budget center."
            )
        scalar_l = float_from_decimal((upper_total - lower_total) / (lower_total + upper_total))
        if scalar_l < 0 or scalar_l > 1:
            raise FlexibleBudgetApiUnsupportedError(
                "Native spend_constraint_lower must be in [0, 1]; B_min/B_max cannot be encoded."
            )
        scalar_u = scalar_l
        lowers, uppers = _per_channel_constraints(
            vector=vector,
            constraint_set=constraint_set,
            budget=midpoint,
            default_lower=scalar_l,
            default_upper=scalar_u,
        )
        return midpoint, lowers, uppers

    budget = constraint_set.total_budget or approved
    default_l = (
        PINNED_SPEND_CONSTRAINT_LOWER
        if budget_mode is OptimizationBudgetMode.FIXED
        else PINNED_FLEXIBLE_SPEND_CONSTRAINT
    )
    default_u = (
        PINNED_SPEND_CONSTRAINT_UPPER
        if budget_mode is OptimizationBudgetMode.FIXED
        else PINNED_FLEXIBLE_SPEND_CONSTRAINT
    )
    lowers, uppers = _per_channel_constraints(
        vector=vector,
        constraint_set=constraint_set,
        budget=budget,
        default_lower=default_l,
        default_upper=default_u,
    )
    return budget, lowers, uppers


def _per_channel_constraints(
    *,
    vector: OptimizerBudgetVector,
    constraint_set: OptimizationConstraintSet,
    budget: Decimal,
    default_lower: float,
    default_upper: float,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    optimizable = [
        line
        for line in vector.lines
        if line.eligibility is ModelVariableOptimizationEligibility.OPTIMIZABLE
    ]
    total = sum((line.baseline for line in optimizable), Decimal("0"))
    lowers: list[float] = []
    uppers: list[float] = []
    bound_by_id = {item.line_id: item for item in constraint_set.line_bounds}
    move_by_id = {item.line_id: item for item in constraint_set.movement_limits}
    locked = {item.line_id for item in constraint_set.locked_lines} | set(
        constraint_set.locked_line_ids
    )
    for line in optimizable:
        alloc = Decimal("0") if total <= 0 else line.baseline / total
        center = round_money(budget * alloc)
        lo_frac = default_lower
        hi_frac = default_upper
        if line.model_variable_id in locked:
            lo_frac, hi_frac = 0.0, 0.0
        bound = bound_by_id.get(line.model_variable_id)
        if bound is not None and center > 0:
            if bound.lower is not None:
                lo_frac = min(lo_frac, _lower_fraction(center, bound.lower))
            if bound.upper is not None:
                hi_frac = min(hi_frac, _upper_fraction(center, bound.upper))
        move = move_by_id.get(line.model_variable_id)
        if move is not None and center > 0:
            if move.max_absolute_move is not None:
                lo_abs = max(Decimal("0"), line.baseline - move.max_absolute_move)
                hi_abs = line.baseline + move.max_absolute_move
                lo_frac = min(lo_frac, _lower_fraction(center, lo_abs))
                hi_frac = min(hi_frac, _upper_fraction(center, hi_abs))
            if move.max_percent_move is not None and line.baseline > 0:
                delta = line.baseline * move.max_percent_move / Decimal("100")
                lo_frac = min(
                    lo_frac, _lower_fraction(center, max(Decimal("0"), line.baseline - delta))
                )
                hi_frac = min(hi_frac, _upper_fraction(center, line.baseline + delta))
        if lo_frac < 0 or lo_frac > 1:
            raise FlexibleBudgetApiUnsupportedError(
                "Compiled spend_constraint_lower is outside native [0, 1] bounds."
            )
        if hi_frac < 0:
            raise FlexibleBudgetApiUnsupportedError(
                "Compiled spend_constraint_upper cannot be negative."
            )
        lowers.append(lo_frac)
        uppers.append(hi_frac)
    return tuple(lowers), tuple(uppers)


def _lower_fraction(center: Decimal, lower: Decimal) -> float:
    # lower = (1 - L) * center  =>  L = 1 - lower/center
    ratio = float_from_decimal(lower / center)
    return max(0.0, min(1.0, 1.0 - ratio))


def _upper_fraction(center: Decimal, upper: Decimal) -> float:
    # upper = (1 + U) * center  =>  U = upper/center - 1
    return max(0.0, float_from_decimal(upper / center) - 1.0)


def _new_data_kind(assumptions: FutureScenarioAssumptions | None) -> str:
    if assumptions is None:
        return "none"
    kinds: list[str] = []
    if assumptions.cost_per_media_unit or assumptions.future_cpm_by_channel:
        kinds.append("media_spend")
    if assumptions.flighting:
        kinds.append("media")
    if assumptions.revenue_per_kpi is not None or assumptions.contribution_margin is not None:
        kinds.append("revenue_per_kpi")
    return ",".join(kinds) if kinds else "none"


def _selected_geos(constraint_set: OptimizationConstraintSet | None) -> tuple[str, ...] | None:
    if constraint_set is None or not constraint_set.availability_constraints:
        return None
    geos = tuple(
        item.market_id
        for item in constraint_set.availability_constraints
        if item.available and item.market_id
    )
    return geos or None
