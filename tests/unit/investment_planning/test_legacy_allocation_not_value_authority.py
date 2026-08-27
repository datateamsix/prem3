"""P6-00: PlanningChannelAllocation.amount is not Planning value authority."""

from __future__ import annotations

import inspect

import pytest

from app.domain.channels.bindings import PlanningChannelAllocation
from app.investment_planning.errors import PlanningValueAuthorityError
from app.investment_planning.legacy_allocation import (
    LEGACY_AMOUNT_FIELD,
    LEGACY_PLANNING_ALLOCATION_AMOUNT_IS_NOT_VALUE_AUTHORITY,
    reject_legacy_planning_allocation_as_value_authority,
)
from app.investment_planning.service import PortfolioAssembler


def test_shared_planning_channel_allocation_class_is_unmodified() -> None:
    source = inspect.getsource(PlanningChannelAllocation)
    assert "amount: float | None = None" in source
    assert LEGACY_AMOUNT_FIELD == "amount"
    assert LEGACY_PLANNING_ALLOCATION_AMOUNT_IS_NOT_VALUE_AUTHORITY is True


def test_p6_does_not_consume_legacy_allocation_amount_as_value_authority() -> None:
    alloc = PlanningChannelAllocation(
        allocation_id="a1",
        channel_id="search_paid",
        channel_registry_version=1,
        amount=123456.78,
    )
    assembler = PortfolioAssembler()
    with pytest.raises(PlanningValueAuthorityError, match="pre-P6 compatibility"):
        assembler.assemble_from_legacy_allocation(alloc)
    with pytest.raises(PlanningValueAuthorityError):
        reject_legacy_planning_allocation_as_value_authority(alloc)
    # The float remains on the shared class for M5 compatibility, unused by P6.
    assert alloc.amount == 123456.78
