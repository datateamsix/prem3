"""Documented Planning API namespace. No fake HTTP 200 handlers in P6-00."""

from __future__ import annotations

CANONICAL_INVESTMENT_PLANS = "/v1/projects/{project_id}/investment-plans"
CANONICAL_INVESTMENT_PORTFOLIO = "/v1/projects/{project_id}/investment-portfolio"
CANONICAL_INVESTMENT_OPTIMIZATIONS = "/v1/projects/{project_id}/investment-optimizations"

WORKSPACE_ALIAS_INVESTMENT_PLANS = "/v1/workspaces/{workspace_id}/investment-plans"
WORKSPACE_ALIAS_INVESTMENT_PORTFOLIO = "/v1/workspaces/{workspace_id}/investment-portfolio"
WORKSPACE_ALIAS_INVESTMENT_OPTIMIZATIONS = (
    "/v1/workspaces/{workspace_id}/investment-optimizations"
)

QUERY_SAFE_FILTERS: frozenset[str] = frozenset(
    {
        "fiscal_year",
        "quarter",
        "market_id",
        "channel_id",
        "baseline_kind",
        "snapshot_id",
        "plan_id",
    }
)
