"""Optimization proposal authority. Approval does not mutate the active plan."""

from __future__ import annotations

from app.investment_optimization.enums import OptimizationProposalStatus
from app.investment_planning.authority import require_human_approver
from app.investment_planning.errors import PlanningAuthorityError


def require_new_plan_version_on_approval(
    *,
    current_status: OptimizationProposalStatus,
    actor_id: str,
) -> str:
    """RECOMMENDED → APPROVED authorizes a new Drive plan version (P6-06), not a mutation."""
    approver = require_human_approver(actor_id)
    if current_status is not OptimizationProposalStatus.RECOMMENDED:
        raise PlanningAuthorityError(
            "Only RECOMMENDED proposals may be approved into a new plan version."
        )
    return approver
