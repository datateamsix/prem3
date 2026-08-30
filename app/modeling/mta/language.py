"""Reject forbidden causal language in MTA user-facing strings."""

from __future__ import annotations

from app.modeling.mta import FORBIDDEN_CAUSAL_PHRASES


class CausalLanguageError(ValueError):
    pass


def assert_no_causal_mta_language(text: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_CAUSAL_PHRASES:
        if phrase in lowered:
            raise CausalLanguageError(
                f"MTA user-facing text must not use '{phrase}'."
            )


def scan_strings_for_causal_language(values: list[str] | tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    for value in values:
        lowered = value.lower()
        for phrase in FORBIDDEN_CAUSAL_PHRASES:
            if phrase in lowered:
                hits.append(f"{value!r} contains {phrase!r}")
    return hits
