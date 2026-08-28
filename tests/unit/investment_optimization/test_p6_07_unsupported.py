"""P6-07 unsupported-channel policies. Missing evidence is never treated as zero."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.investment_optimization.enums import (
    ModelVariableOptimizationEligibility,
    UnsupportedChannelPolicy,
)
from app.investment_optimization.errors import ProxyApprovalRequiredError
from app.investment_optimization.unsupported_channels import apply_unsupported_policies
from tests.unit.investment_optimization.p6_07_support import budget_line, constraint_set


def _unmodeled() -> tuple:
    return (
        budget_line(
            "display_spend",
            channel_id="display",
            baseline="40.00",
            eligibility=ModelVariableOptimizationEligibility.UNSUPPORTED,
        ),
    )


def test_not_zeroed() -> None:
    lines = apply_unsupported_policies(lines=_unmodeled(), constraint_set=None)
    assert lines[0].baseline == Decimal("40.00")
    assert lines[0].eligibility is ModelVariableOptimizationEligibility.FIXED


def test_four_policies() -> None:
    hold = constraint_set(
        unsupported_channel_policies=(("display", UnsupportedChannelPolicy.HOLD_BASELINE),)
    )
    held = apply_unsupported_policies(lines=_unmodeled(), constraint_set=hold)
    assert held[0].eligibility is ModelVariableOptimizationEligibility.FIXED
    assert held[0].baseline == Decimal("40.00")

    reserve = constraint_set(
        unsupported_channel_policies=(
            ("display", UnsupportedChannelPolicy.RESERVE_EXPERIMENT_AMOUNT),
        )
    )
    reserved = apply_unsupported_policies(lines=_unmodeled(), constraint_set=reserve)
    assert reserved[0].eligibility is ModelVariableOptimizationEligibility.FIXED
    assert reserved[0].baseline == Decimal("40.00")

    exclude = constraint_set(
        unsupported_channel_policies=(
            ("display", UnsupportedChannelPolicy.EXCLUDE_FROM_OPTIMIZER_BUT_KEEP_PORTFOLIO),
        )
    )
    excluded = apply_unsupported_policies(lines=_unmodeled(), constraint_set=exclude)
    assert excluded[0].eligibility is ModelVariableOptimizationEligibility.FIXED
    assert excluded[0].baseline == Decimal("40.00")

    proxy = constraint_set(
        unsupported_channel_policies=(
            ("display", UnsupportedChannelPolicy.APPROVED_PROXY_WITH_REVIEW),
        )
    )
    approved = apply_unsupported_policies(
        lines=_unmodeled(),
        constraint_set=proxy,
        approved_proxy_channel_ids=frozenset({"display"}),
    )
    assert approved[0].eligibility is ModelVariableOptimizationEligibility.UNSUPPORTED
    assert approved[0].baseline == Decimal("40.00")


def test_proxy_requires_approval() -> None:
    payload = constraint_set(
        unsupported_channel_policies=(
            ("display", UnsupportedChannelPolicy.APPROVED_PROXY_WITH_REVIEW),
        )
    )
    with pytest.raises(ProxyApprovalRequiredError):
        apply_unsupported_policies(lines=_unmodeled(), constraint_set=payload)
