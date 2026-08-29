"""Official Meridian identifiability failures. PreM3 does not select the fix."""

from __future__ import annotations

import re
from typing import Any

from app.control_plane.ids import new_decision_id
from app.modeling.mmm.contracts import (
    DecisionStatus,
    DecisionType,
    KnowledgeClass,
    ModelDecision,
)

OFFICIAL_MERIDIAN_LIBRARY = "google-meridian"
MUSIC_CENTER_PROMO_VARIABLE = "music_center_promo"

IDENTIFIABILITY_ALTERNATIVES: tuple[dict[str, Any], ...] = (
    {
        "id": "A",
        "summary": "Retain music_center_promo. Reduce time-effect knot flexibility.",
        "selected": False,
    },
    {
        "id": "B",
        "summary": "Remove music_center_promo. Retain n_knots = n_time.",
        "selected": False,
    },
    {
        "id": "C",
        "summary": (
            "Use legitimate geo-varying promotion intensity if such data actually exists."
        ),
        "selected": False,
        "guardrail": "Never fabricate geo variation in music_center_promo.",
    },
)

_TREATMENT_RE = re.compile(r"\[(?:b)?'([^']+)'\]")


def is_geo_invariant_identifiability_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "do not vary across geos" in text and "unidentifiable" in text


def official_identifiability_message(exc: BaseException) -> str:
    return str(exc)


def extract_invariant_treatment(message: str) -> str | None:
    match = _TREATMENT_RE.search(message)
    if match is None:
        return None
    return match.group(1)


def prem3_identifiability_summary(message: str) -> str:
    name = extract_invariant_treatment(message) or "the geo-invariant treatment"
    return (
        f"Meridian could not identify {name} separately from a fully flexible "
        "time effect because the treatment does not vary across geographies."
    )


def identifiability_decision(
    *,
    tenant_id: str,
    project_id: str,
    model_version_id: str,
    official_message: str,
    plan_fingerprint: str | None,
    evidence_refs: tuple[str, ...] = (),
) -> ModelDecision:
    variable = extract_invariant_treatment(official_message) or MUSIC_CENTER_PROMO_VARIABLE
    return ModelDecision(
        decision_id=new_decision_id(),
        model_version_id=model_version_id,
        tenant_id=tenant_id,
        project_id=project_id,
        decision_type=DecisionType.KNOT_STRATEGY,
        proposal={
            "decision_family": DecisionType.KNOT_STRATEGY.value,
            "kind": "IDENTIFIABILITY",
            "variable": variable,
            "n_knots": "n_time",
            "geo_invariance": True,
            "official_library": OFFICIAL_MERIDIAN_LIBRARY,
            "official_message": official_message,
            "alternatives": list(IDENTIFIABILITY_ALTERNATIVES),
            "selected": None,
        },
        authority=KnowledgeClass.MMM_JUDGMENT,
        evidence_refs=evidence_refs,
        recommended_value=None,
        chosen_value=None,
        reason=(
            "Official Meridian rejected the ModelSpec before sampling. "
            "A model-design decision is required. PreM3 does not select A, B, or C."
        ),
        requires_approval=True,
        status=DecisionStatus.PENDING,
        plan_fingerprint=plan_fingerprint,
    )
