"""Legacy PlanningChannelAllocation is not Planning value authority."""

from __future__ import annotations

from app.domain.channels.bindings import PlanningChannelAllocation
from app.investment_planning.errors import PlanningValueAuthorityError

LEGACY_PLANNING_ALLOCATION_AMOUNT_IS_NOT_VALUE_AUTHORITY = True

# Pre-P6 compatibility field on the shared ChannelBinding seam.
# P6-00 must not modify PlanningChannelAllocation and must not read .amount
# into PortfolioView or optimization payloads.
LEGACY_AMOUNT_FIELD = "amount"


def reject_legacy_planning_allocation_as_value_authority(
    allocation: PlanningChannelAllocation,
) -> None:
    """Fail closed if a caller tries to treat the pre-P6 float amount as authority."""
    del allocation
    raise PlanningValueAuthorityError(
        "PlanningChannelAllocation.amount is a pre-P6 compatibility field, not "
        "Planning value authority. Use Drive-owned Decimal PortfolioView amounts.",
        code="LEGACY_ALLOCATION_NOT_VALUE_AUTHORITY",
    )


def legacy_allocation_amount_must_not_populate_portfolio(
    allocation: PlanningChannelAllocation,
) -> None:
    """Regression seam: P6 assemblers must call this instead of reading .amount."""
    if getattr(allocation, LEGACY_AMOUNT_FIELD, None) is not None:
        reject_legacy_planning_allocation_as_value_authority(allocation)
    reject_legacy_planning_allocation_as_value_authority(allocation)
