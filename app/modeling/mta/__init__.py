"""MTA track domain — observable journey attribution (not causal incrementality)."""

from __future__ import annotations

from app.modeling.mta.states import MTATrackStage

ADAPTER_VERSION = "m5-01.1"
DP6_MAM_PINNED_VERSION = "1.0.11"

# Forbidden substrings in MTA user-facing copy (epistemic boundary).
FORBIDDEN_CAUSAL_PHRASES = (
    "causal contribution",
    "incremental contribution",
    "true contribution",
    "true channel impact",
    "incremental lift",
    "incremental revenue",
)

__all__ = [
    "ADAPTER_VERSION",
    "DP6_MAM_PINNED_VERSION",
    "FORBIDDEN_CAUSAL_PHRASES",
    "MTATrackStage",
]
