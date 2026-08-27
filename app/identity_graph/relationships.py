"""Typed Marketing Identity Graph edges. Closed set; no free-text types."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.contracts import utc_now
from app.identity_graph.contracts import IdentityGraphModel
from app.identity_graph.enums import MarketingIdentityEdgeType, MarketingIdentityNodeType
from app.identity_graph.errors import IdentityGraphError


class MarketingIdentityEdge(IdentityGraphModel):
    edge_id: str
    tenant_id: str
    project_id: str
    edge_type: MarketingIdentityEdgeType
    from_node_type: MarketingIdentityNodeType
    from_node_id: str
    to_node_type: MarketingIdentityNodeType
    to_node_id: str
    created_at: datetime = Field(default_factory=utc_now)


def assert_known_edge_type(edge_type: str) -> MarketingIdentityEdgeType:
    try:
        return MarketingIdentityEdgeType(edge_type)
    except ValueError as exc:
        raise IdentityGraphError(
            f"Unknown Identity Graph edge type {edge_type!r}.",
            code="UNKNOWN_EDGE_TYPE",
        ) from exc
