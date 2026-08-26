"""Reject forbidden causal language in MTA user-facing strings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.modeling.mta import FORBIDDEN_CAUSAL_PHRASES
from app.modeling.mta.results_contracts import RESULT_FORBIDDEN_SUBSTRINGS


class CausalLanguageError(ValueError):
    pass


def assert_no_causal_mta_language(text: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_CAUSAL_PHRASES:
        if phrase in lowered:
            raise CausalLanguageError(f"MTA user-facing text must not use '{phrase}'.")


def scan_strings_for_causal_language(values: list[str] | tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    for value in values:
        lowered = value.lower()
        for phrase in FORBIDDEN_CAUSAL_PHRASES:
            if phrase in lowered:
                hits.append(f"{value!r} contains {phrase!r}")
    return hits


def iter_strings(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, Mapping):
        for item in value.values():
            found.extend(iter_strings(item))
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        for item in value:
            found.extend(iter_strings(item))
    return found


def scan_result_payload_for_forbidden_language(payload: Any) -> list[str]:
    """Stricter result/brief guard: incremental / causal / lift / true contribution.

    ``incrementality experiment`` is an allowed measurement recommendation and is
    stripped before the ``incremental`` token check.
    """
    hits: list[str] = []
    for text in iter_strings(payload):
        lowered = text.lower().replace("incrementality experiment", " ")
        for phrase in RESULT_FORBIDDEN_SUBSTRINGS:
            if phrase in lowered:
                hits.append(f"{text!r} contains {phrase!r}")
    return hits


def assert_result_payload_language(payload: Any) -> None:
    hits = scan_result_payload_for_forbidden_language(payload)
    if hits:
        raise CausalLanguageError("; ".join(hits[:8]))
