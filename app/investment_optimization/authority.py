"""Optimization proposal authority. Approval does not mutate the active plan."""

from __future__ import annotations

from app.investment_optimization.enums import (
    OptimizationProposalLifecycleStatus,
    OptimizationProposalStatus,
)
from app.investment_planning.authority import require_human_approver
from app.investment_planning.errors import PlanningAuthorityError

_ALLOWED = frozenset(
    {
        OptimizationProposalStatus.RECOMMENDED,
        OptimizationProposalLifecycleStatus.APPROVED,
    }
)


def require_new_plan_version_on_approval(
    *,
    current_status: OptimizationProposalStatus | OptimizationProposalLifecycleStatus,
    actor_id: str,
) -> str:
    """APPROVED (P6-06) or RECOMMENDED (P6-00 seam) authorizes a new Drive plan version."""
    approver = require_human_approver(actor_id)
    if current_status not in _ALLOWED:
        raise PlanningAuthorityError(
            "Only APPROVED proposals may create a new plan version."
        )
    return approver
