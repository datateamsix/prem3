"""In-memory analytical adapter. Schema, overlap filters, and read-back. No live BigQuery."""

from __future__ import annotations

from app.identity_graph.analytics.contracts import (
    AnalyticalSessionSeed,
    MtaJourneyRow,
    MtaTouchpointRow,
    UnifiedSessionRow,
)
from app.identity_graph.privacy import reject_identity_graph_payload

REQUIRED_SESSION_FIELDS = frozenset(
    {
        "session_id",
        "ga4_property_id",
        "ga4_source_binding_id",
        "market_status",
        "channel_status",
        "campaign_status",
        "session_start_ts",
    }
)
REQUIRED_TOUCHPOINT_FIELDS = frozenset(
    {
        "session_id",
        "touchpoint_order",
        "ga4_property_id",
        "ga4_source_binding_id",
    }
)
REQUIRED_JOURNEY_FIELDS = frozenset({"journey_id", "session_ids", "touchpoint_count"})


class InMemoryAnalyticalAdapter:
    def __init__(self) -> None:
        self._seeds: dict[tuple[str, str], list[AnalyticalSessionSeed]] = {}
        self._sessions: dict[str, tuple[UnifiedSessionRow, ...]] = {}
        self._touchpoints: dict[str, tuple[MtaTouchpointRow, ...]] = {}
        self._journeys: dict[str, tuple[MtaJourneyRow, ...]] = {}

    def seed(
        self,
        *,
        tenant_id: str,
        project_id: str,
        rows: tuple[AnalyticalSessionSeed, ...] | list[AnalyticalSessionSeed],
    ) -> None:
        payload = [item.model_dump(mode="json") for item in rows]
        reject_identity_graph_payload(payload)
        self._seeds[(tenant_id, project_id)] = list(rows)

    def seeds(self, *, tenant_id: str, project_id: str) -> tuple[AnalyticalSessionSeed, ...]:
        return tuple(self._seeds.get((tenant_id, project_id), ()))

    def put_sessions(
        self, compilation_id: str, rows: tuple[UnifiedSessionRow, ...]
    ) -> tuple[UnifiedSessionRow, ...]:
        self._sessions[compilation_id] = rows
        return rows

    def put_touchpoints(
        self, compilation_id: str, rows: tuple[MtaTouchpointRow, ...]
    ) -> tuple[MtaTouchpointRow, ...]:
        self._touchpoints[compilation_id] = rows
        return rows

    def put_journeys(
        self, compilation_id: str, rows: tuple[MtaJourneyRow, ...]
    ) -> tuple[MtaJourneyRow, ...]:
        self._journeys[compilation_id] = rows
        return rows

    def read_back_sessions(self, compilation_id: str) -> tuple[UnifiedSessionRow, ...]:
        return self._sessions.get(compilation_id, ())

    def read_back_touchpoints(self, compilation_id: str) -> tuple[MtaTouchpointRow, ...]:
        return self._touchpoints.get(compilation_id, ())

    def read_back_journeys(self, compilation_id: str) -> tuple[MtaJourneyRow, ...]:
        return self._journeys.get(compilation_id, ())

    def schema_validate_sessions(self, rows: tuple[UnifiedSessionRow, ...]) -> tuple[str, ...]:
        return _schema_issues(rows, REQUIRED_SESSION_FIELDS)

    def schema_validate_touchpoints(self, rows: tuple[MtaTouchpointRow, ...]) -> tuple[str, ...]:
        return _schema_issues(rows, REQUIRED_TOUCHPOINT_FIELDS)

    def schema_validate_journeys(self, rows: tuple[MtaJourneyRow, ...]) -> tuple[str, ...]:
        return _schema_issues(rows, REQUIRED_JOURNEY_FIELDS)


def _schema_issues(rows: tuple, required: frozenset[str]) -> tuple[str, ...]:
    issues: list[str] = []
    for row in rows:
        payload = row.model_dump(mode="json")
        missing = sorted(field for field in required if field not in payload)
        if missing:
            issues.append("SCHEMA_MISSING_FIELDS")
            break
        reject_identity_graph_payload(payload)
    return tuple(dict.fromkeys(issues))
