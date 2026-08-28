"""Construct and fingerprint OptimizationConstraintSet. Amounts stay transient."""

from __future__ import annotations

from decimal import Decimal

from app.investment_optimization.contracts import (
    ConstraintAuthorityRecord,
    GroupConstraint,
    OptimizationConstraintSet,
    ReserveConstraint,
)
from app.investment_optimization.enums import ConstraintAuthority
from app.investment_optimization.errors import ConstraintReferenceInvalidError
from app.investment_planning.fingerprint import metadata_fingerprint


def line_key(*, period: str, market_id: str, channel_id: str) -> str:
    return f"{period}|{market_id}|{channel_id}"


def constraint_authority(
    *,
    source: str,
    authority: ConstraintAuthority,
    scope: str,
    period: str,
    reason: str,
) -> ConstraintAuthorityRecord:
    if authority is ConstraintAuthority.HUMAN_CONFIRMED and not reason:
        raise ConstraintReferenceInvalidError("Hard constraints require an explicit reason.")
    body = {
        "source": source,
        "authority": authority.value,
        "scope": scope,
        "period": period,
        "reason": reason,
    }
    return ConstraintAuthorityRecord(
        source=source,
        authority=authority,
        scope=scope,
        period=period,
        reason=reason,
        fingerprint=metadata_fingerprint(body),
    )


def _money(value: Decimal | None) -> str:
    return "" if value is None else format(value, "f")


def constraint_set_fingerprint(constraint_set: OptimizationConstraintSet) -> str:
    return metadata_fingerprint(
        {
            "constraint_set_id": constraint_set.constraint_set_id,
            "project_id": constraint_set.project_id or "",
            "currency": constraint_set.currency,
            "period_start": constraint_set.period_start or "",
            "period_end": constraint_set.period_end or "",
            "total_budget": _money(constraint_set.total_budget),
            "bounds": None
            if constraint_set.total_budget_bounds is None
            else {
                "lower": _money(constraint_set.total_budget_bounds.lower),
                "upper": _money(constraint_set.total_budget_bounds.upper),
                "currency": constraint_set.total_budget_bounds.currency,
            },
            "line_bounds": [
                {
                    "constraint_id": item.constraint_id,
                    "family": item.family.value,
                    "line_id": item.line_id,
                    "lower": _money(item.lower),
                    "upper": _money(item.upper),
                }
                for item in constraint_set.line_bounds
            ],
            "locked": [
                {
                    "constraint_id": item.constraint_id,
                    "line_id": item.line_id,
                    "baseline": format(item.baseline, "f"),
                    "reason": item.reason,
                }
                for item in constraint_set.locked_lines
            ],
            "locked_line_ids": list(constraint_set.locked_line_ids),
            "movement": [
                {
                    "constraint_id": item.constraint_id,
                    "family": item.family.value,
                    "line_id": item.line_id,
                    "abs": _money(item.max_absolute_move),
                    "pct": _money(item.max_percent_move),
                    "percent_unavailable": item.percent_unavailable,
                }
                for item in constraint_set.movement_limits
            ],
            "markets": [_group_body(item) for item in constraint_set.market_constraints],
            "quarters": [_group_body(item) for item in constraint_set.quarter_constraints],
            "funnels": [
                {
                    "constraint_id": item.constraint_id,
                    "family": item.family.value,
                    "group_id": item.group_id,
                    "weights": [
                        (line_id, format(weight, "f")) for line_id, weight in item.member_weights
                    ],
                    "lower": _money(item.lower),
                    "upper": _money(item.upper),
                }
                for item in constraint_set.funnel_constraints
            ],
            "experiment": _reserve_body(constraint_set.experiment_reserve),
            "contingency": _reserve_body(constraint_set.contingency_reserve),
            "availability": [
                item.constraint_id for item in constraint_set.availability_constraints
            ],
            "policies": [
                (channel_id, policy.value)
                for channel_id, policy in constraint_set.unsupported_channel_policies
            ],
            "exposure_guardrails": list(constraint_set.exposure_guardrails),
        }
    )


def _group_body(item: GroupConstraint) -> dict[str, object]:
    return {
        "constraint_id": item.constraint_id,
        "family": item.family.value,
        "group_id": item.group_id,
        "members": list(item.member_line_ids),
        "lower": _money(item.lower),
        "upper": _money(item.upper),
    }


def _reserve_body(item: ReserveConstraint | None) -> dict[str, str] | None:
    if item is None:
        return None
    return {
        "constraint_id": item.constraint_id,
        "family": item.family.value,
        "amount": format(item.amount, "f"),
        "currency": item.currency,
        "period": item.period,
        "reason": item.reason,
    }


def pin_constraint_set(constraint_set: OptimizationConstraintSet) -> OptimizationConstraintSet:
    if constraint_set.exposure_guardrails:
        raise ConstraintReferenceInvalidError(
            "Exposure guardrails are owned by P6-08 and cannot be set in P6-07."
        )
    return constraint_set.model_copy(
        update={"fingerprint": constraint_set_fingerprint(constraint_set)}
    )


def iter_hard_constraints(constraint_set: OptimizationConstraintSet) -> tuple[str, ...]:
    ids: list[str] = []
    ids.extend(item.constraint_id for item in constraint_set.line_bounds)
    ids.extend(item.constraint_id for item in constraint_set.locked_lines)
    ids.extend(item.constraint_id for item in constraint_set.movement_limits)
    ids.extend(item.constraint_id for item in constraint_set.market_constraints)
    ids.extend(item.constraint_id for item in constraint_set.quarter_constraints)
    ids.extend(item.constraint_id for item in constraint_set.funnel_constraints)
    ids.extend(item.constraint_id for item in constraint_set.availability_constraints)
    if constraint_set.experiment_reserve is not None:
        ids.append(constraint_set.experiment_reserve.constraint_id)
    if constraint_set.contingency_reserve is not None:
        ids.append(constraint_set.contingency_reserve.constraint_id)
    return tuple(ids)


def empty_constraint_set(
    *, constraint_set_id: str, project_id: str | None = None
) -> OptimizationConstraintSet:
    empty = OptimizationConstraintSet(constraint_set_id=constraint_set_id, project_id=project_id)
    return pin_constraint_set(empty)
