"""Persona and Audience ledger helpers. Definitions only; not people or members."""

from __future__ import annotations

import re

from app.identity_graph.contracts import (
    AudienceLedgerValidationReceipt,
    PersonaLedgerValidationReceipt,
)
from app.identity_graph.enums import AudienceStatus, IdentityGraphCapabilityState, PersonaStatus
from app.identity_graph.errors import IdentityGraphError

_LEDGER_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"ACTIVE", "ARCHIVED"}),
    "ACTIVE": frozenset({"INACTIVE", "ARCHIVED"}),
    "INACTIVE": frozenset({"ACTIVE", "ARCHIVED"}),
    "ARCHIVED": frozenset(),
}

_SOURCE_REF_SQL = re.compile(
    r"(;|--|/\*|\bselect\b|\bfrom\b|\bwhere\b|\binsert\b|\bupdate\b|\bdelete\b)",
    re.IGNORECASE,
)


def assert_ledger_status_transition(*, current: str, proposed: str) -> None:
    if proposed == current:
        return
    allowed = _LEDGER_TRANSITIONS.get(current, frozenset())
    if proposed not in allowed:
        raise IdentityGraphError(
            f"Status transition {current} → {proposed} is not allowed.",
            code="STATUS_TRANSITION",
        )


def assert_persona_status_transition(current: PersonaStatus, proposed: PersonaStatus) -> None:
    assert_ledger_status_transition(current=current.value, proposed=proposed.value)


def assert_audience_status_transition(current: AudienceStatus, proposed: AudienceStatus) -> None:
    assert_ledger_status_transition(current=current.value, proposed=proposed.value)


def validate_source_ref(source_ref: str | None) -> None:
    """source_ref is a metadata pointer, never SQL or a person identifier."""
    if source_ref is None or source_ref == "":
        return
    if "@" in source_ref or _SOURCE_REF_SQL.search(source_ref) is not None:
        raise IdentityGraphError(
            "source_ref must be a metadata pointer, not SQL or a person identifier.",
            code="SOURCE_REF_FORBIDDEN",
        )


def would_create_audience_cycle(
    *,
    audience_id: str,
    new_parent_id: str,
    audiences: dict[str, str | None],
) -> bool:
    if audience_id == new_parent_id:
        return True
    seen: set[str] = set()
    current: str | None = new_parent_id
    while current:
        if current == audience_id:
            return True
        if current in seen:
            return True
        seen.add(current)
        current = audiences.get(current)
    return False


def ledger_state_from_receipts(
    items: list[object],
    receipts: list[PersonaLedgerValidationReceipt | AudienceLedgerValidationReceipt | None],
) -> IdentityGraphCapabilityState:
    if not items:
        return IdentityGraphCapabilityState.NOT_CONFIGURED
    if any(
        receipt is not None and receipt.state == IdentityGraphCapabilityState.REVIEW_REQUIRED
        for receipt in receipts
    ):
        return IdentityGraphCapabilityState.REVIEW_REQUIRED
    if all(
        receipt is not None and receipt.state == IdentityGraphCapabilityState.READY
        for receipt in receipts
    ):
        return IdentityGraphCapabilityState.READY
    return IdentityGraphCapabilityState.PARTIAL
