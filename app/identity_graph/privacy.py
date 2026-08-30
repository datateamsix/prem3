"""Privacy boundary: this graph maps marketing objects, not people."""

from __future__ import annotations

from typing import Any

from app.identity_graph.errors import IdentityGraphError

PROHIBITED_PERSON_FIELDS = frozenset(
    {
        "email",
        "phone",
        "hashed_email",
        "hashed_phone",
        "user_pseudo_id",
        "user_id",
        "crm_person_id",
        "device_id",
        "ip_address",
        "ip",
        "cookie_id",
        "audience_members",
        "raw_audience_membership",
        "membership",
    }
)

PROHIBITED_BUDGET_FIELDS = frozenset(
    {
        "planned_spend",
        "budget",
        "actual_spend",
        "recommended_spend",
    }
)

PROHIBITED_EVENT_FIELDS = frozenset(
    {
        "events",
        "event_rows",
        "ga4_events",
        "event_data",
    }
)


def _walk_keys(payload: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            keys.append(str(key))
            keys.extend(_walk_keys(value))
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            keys.extend(_walk_keys(item))
    return keys


def reject_identity_graph_payload(payload: Any) -> None:
    keys = {key.lower() for key in _walk_keys(payload)}
    person = sorted(keys & PROHIBITED_PERSON_FIELDS)
    if person:
        raise IdentityGraphError(
            f"Identity Graph rejects person-identity fields: {', '.join(person)}.",
            code="PERSON_IDENTITY_FORBIDDEN",
        )
    budget = sorted(keys & PROHIBITED_BUDGET_FIELDS)
    if budget:
        raise IdentityGraphError(
            f"Identity Graph rejects budget fields: {', '.join(budget)}.",
            code="BUDGET_FORBIDDEN",
        )
    events = sorted(keys & PROHIBITED_EVENT_FIELDS)
    if events:
        raise IdentityGraphError(
            f"Identity Graph rejects event-scale rows: {', '.join(events)}.",
            code="EVENT_ROWS_FORBIDDEN",
        )
