"""Internal normative retrieval adapter. No live GitHub/docs fetch during fit."""

from __future__ import annotations

from app.modeling.common.external_assets import (
    PINNED_RUNTIME_VERSION,
    PINNED_UPSTREAM_COMMIT,
    read_snapshot_text,
    require_enabled_asset,
)
from app.modeling.mmm.contracts import NormativeRecommendation, NormativeSourceKind

_TOPIC_HINTS = {
    "knots": "docs/advanced-modeling/setting-knots",
    "priors": "docs/advanced-modeling/model-spec",
    "rf": "docs/user-guide/load-geo-data-with-rf",
    "eda": "docs/pre-modeling/perform-eda",
}


def consult_topic(topic: str) -> NormativeRecommendation:
    asset = require_enabled_asset("meridian.skill.doc_consultant")
    mapping = read_snapshot_text(
        "skills/meridian_doc_consultant/references/documentation_map.md"
    )
    hint = _TOPIC_HINTS.get(topic.lower())
    if hint is None or hint not in mapping:
        return NormativeRecommendation(
            topic=topic,
            recommendation="Authoritative source unavailable; do not invent a numeric default.",
            source_refs=(),
            upstream_asset_version=asset.internal_version,
            meridian_version=PINNED_RUNTIME_VERSION,
            source_kind=NormativeSourceKind.PINNED_REPO_SOURCE,
            available=False,
        )
    return NormativeRecommendation(
        topic=topic,
        recommendation=(
            f"Consult Meridian topic ontology entry {hint}. Public repo has no /docs tree; "
            "use OFFICIAL_MERIDIAN_WEB_DOC or PREM3_CURATED_MERIDIAN_CONTEXT for numbers."
        ),
        source_refs=(
            f"google/meridian@{PINNED_UPSTREAM_COMMIT}:skills/meridian_doc_consultant",
            hint,
        ),
        upstream_asset_version=asset.internal_version,
        meridian_version=PINNED_RUNTIME_VERSION,
        source_kind=NormativeSourceKind.PINNED_REPO_SOURCE,
        available=True,
    )
