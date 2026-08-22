"""Transformation catalog. Default authority is owned by policy, not the agent."""

from __future__ import annotations

from app.data_foundation.enums import TransformAuthority, TransformId

CATALOG: dict[TransformId, tuple[str, TransformAuthority]] = {
    TransformId.DF_T001: ("Trim deterministic whitespace", TransformAuthority.AUTO_SAFE),
    TransformId.DF_T002: (
        "Normalize approved blank representation to NULL",
        TransformAuthority.AUTO_SAFE,
    ),
    TransformId.DF_T003: (
        "Parse/normalize dates using explicit format",
        TransformAuthority.AUTO_SAFE,
    ),
    TransformId.DF_T004: (
        "Safe numeric parsing using explicit locale/format",
        TransformAuthority.AUTO_SAFE,
    ),
    TransformId.DF_T005: ("Provider unit conversion", TransformAuthority.AUTO_SAFE),
    TransformId.DF_T006: ("Remove exact duplicate rows", TransformAuthority.AUTO_SAFE),
    TransformId.DF_T007: ("Remove verified connector reissues", TransformAuthority.AUTO_SAFE),
    TransformId.DF_T008: ("Apply explicit category/label mapping", TransformAuthority.AUTO_SAFE),
    TransformId.DF_T009: (
        "Normalize timezone using explicit source timezone",
        TransformAuthority.AUTO_SAFE,
    ),
    TransformId.DF_T010: ("Normalize validated geo codes", TransformAuthority.AUTO_SAFE),
    TransformId.DF_T011: ("Aggregate to required grain", TransformAuthority.APPROVAL_REQUIRED),
    TransformId.DF_T012: ("Union a compatible recurring file series", TransformAuthority.AUTO_SAFE),
    TransformId.DF_T013: (
        "Historical Drive backfill + ongoing BQ precedence",
        TransformAuthority.APPROVAL_REQUIRED,
    ),
    TransformId.DF_T014: (
        "Currency conversion across currencies",
        TransformAuthority.USER_REQUIRED,
    ),
    TransformId.DF_T015: (
        "Resolve ambiguous business-key dedupe",
        TransformAuthority.USER_REQUIRED,
    ),
    TransformId.DF_T016: (
        "Resolve overlapping promotion semantics",
        TransformAuthority.USER_REQUIRED,
    ),
    TransformId.DF_T017: (
        "Apply registry-backed late-arrival watermark",
        TransformAuthority.AUTO_SAFE,
    ),
    TransformId.DF_T018: ("Align additive schema versions", TransformAuthority.AUTO_SAFE),
    TransformId.DF_T019: (
        "Drop semantic fields to force compatibility",
        TransformAuthority.NOT_RECOMMENDED,
    ),
    TransformId.DF_T020: (
        "Fill unknown media periods with zero",
        TransformAuthority.NOT_RECOMMENDED,
    ),
    TransformId.DF_T021: (
        "Fabricate lower-grain rows from aggregate history",
        TransformAuthority.NOT_RECOMMENDED,
    ),
    TransformId.DF_T022: (
        "Reject duplicate file fingerprint from reingestion",
        TransformAuthority.AUTO_SAFE,
    ),
}


def authority_for(action_id: TransformId) -> TransformAuthority:
    return CATALOG[action_id][1]


def refuse_authority_promotion(
    action_id: TransformId, requested: TransformAuthority
) -> TransformAuthority:
    owned = authority_for(action_id)
    if requested is TransformAuthority.AUTO_SAFE and owned is not TransformAuthority.AUTO_SAFE:
        raise PermissionError("The agent cannot promote a transformation to AUTO_SAFE.")
    return owned
