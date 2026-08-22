"""Cross-source compatibility observations. Pre-Modeling decides model suitability."""

from __future__ import annotations

from datetime import UTC, datetime

from app.data_foundation.contracts import (
    AlignmentRow,
    CrossSourceAlignmentAssessment,
    SourceBinding,
)
from app.data_foundation.enums import AlignmentVerdict, ConsequenceClass


def assess_alignment(
    *,
    workspace_id: str,
    bindings: list[SourceBinding],
) -> CrossSourceAlignmentAssessment:
    currencies = {item.contract.currency for item in bindings if item.contract.currency}
    timezones = {item.contract.timezone for item in bindings if item.contract.timezone}
    grains = {item.contract.grain for item in bindings if item.contract.grain}
    rows = [
        AlignmentRow(
            dimension="Currency",
            kpi_value=next(iter(currencies), "unknown"),
            media_value=", ".join(sorted(x for x in currencies if x)),
            verdict=AlignmentVerdict.COMPATIBLE
            if len(currencies) <= 1
            else AlignmentVerdict.REVIEW_NEEDED,
            note="Currency conversion is USER_REQUIRED when sources disagree.",
            consequence=ConsequenceClass.PREMODEL_REVIEW
            if len(currencies) > 1
            else ConsequenceClass.ADVISORY,
        ),
        AlignmentRow(
            dimension="Time zone",
            kpi_value=next(iter(timezones), "unknown"),
            media_value=", ".join(sorted(x for x in timezones if x)),
            verdict=AlignmentVerdict.NORMALIZE
            if len(timezones) > 1
            else AlignmentVerdict.COMPATIBLE,
            note="Canonical layer may normalize to one reporting zone.",
            consequence=ConsequenceClass.PREMODEL_REVIEW
            if len(timezones) > 1
            else ConsequenceClass.ADVISORY,
        ),
        AlignmentRow(
            dimension="Time grain",
            kpi_value=next(iter(grains), "unknown"),
            media_value=", ".join(sorted(x for x in grains if x)),
            verdict=AlignmentVerdict.COMPATIBLE
            if len(grains) <= 1
            else AlignmentVerdict.REVIEW_NEEDED,
            note="Daily disaggregation of weekly sources is forbidden.",
            consequence=ConsequenceClass.PREMODEL_REVIEW
            if len(grains) > 1
            else ConsequenceClass.ADVISORY,
        ),
    ]
    return CrossSourceAlignmentAssessment(
        workspace_id=workspace_id,
        common_window=None,
        rows=tuple(rows),
        assessed_at=datetime.now(UTC),
    )
