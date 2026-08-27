"""Planning service stubs. No Drive, BigQuery, or Meridian execution in P6-00."""

from __future__ import annotations

from app.domain.channels.bindings import PlanningChannelAllocation
from app.investment_planning.contracts import PortfolioView
from app.investment_planning.errors import PortfolioAssemblyNotImplementedError
from app.investment_planning.legacy_allocation import (
    reject_legacy_planning_allocation_as_value_authority,
)


class PortfolioAssembler:
    """Assembles a transient PortfolioView. Live assembly is P6-02."""

    def assemble(self, *, snapshot_id: str) -> PortfolioView:
        del snapshot_id
        raise PortfolioAssemblyNotImplementedError(
            "Portfolio assembly from Drive/actuals/measurement is not implemented in P6-00."
        )

    def assemble_from_legacy_allocation(
        self, allocation: PlanningChannelAllocation
    ) -> PortfolioView:
        reject_legacy_planning_allocation_as_value_authority(allocation)
        raise PortfolioAssemblyNotImplementedError(
            "Legacy PlanningChannelAllocation cannot populate a PortfolioView."
        )
