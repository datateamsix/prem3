"""Planning authority. Tenant/project are server-owned. Approval is human-only."""

from __future__ import annotations

from app.investment_planning.errors import PlanningAuthorityError

_SERVICE_ACCOUNT_MARKERS = ("gserviceaccount.com", ".iam.gserviceaccount.")


def require_human_approver(actor_id: str) -> str:
    lowered = actor_id.strip().lower()
    if not lowered:
        raise PlanningAuthorityError("Human approver is required.")
    if any(marker in lowered for marker in _SERVICE_ACCOUNT_MARKERS):
        raise PlanningAuthorityError("Service accounts cannot approve Investment Plans.")
    if lowered.startswith("service-account:") or lowered.startswith("sa:"):
        raise PlanningAuthorityError("Service accounts cannot approve Investment Plans.")
    return actor_id


def require_server_owned_scope(*, tenant_id: str, project_id: str) -> None:
    if not tenant_id or not project_id:
        raise PlanningAuthorityError("Tenant and project must be server-owned request context.")
