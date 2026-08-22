"""Readiness states remain independently owned. No helper infers one from another."""

from __future__ import annotations

from app.governance.codes import ImportReadinessStatus, PublishReadinessStatus
from app.materialization.foundation_compat import (
    FOUNDATION_SOURCE_NOT_READY,
    FOUNDATION_SOURCE_READY,
)
from app.publish_execution.contracts import PublishExecutionStatus


def test_readiness_vocabulary_stays_distinct() -> None:
    assert ImportReadinessStatus.IMPORT_READY.value != FOUNDATION_SOURCE_READY
    assert FOUNDATION_SOURCE_READY != "DATA_FOUNDATION_READY"
    assert ImportReadinessStatus.IMPORT_READY.value != "MODEL_READY"
    assert "MODEL_READY" != PublishReadinessStatus.PUBLISH_READY.value
    assert PublishReadinessStatus.PUBLISH_READY.value != "PUBLISHED"
    assert PublishReadinessStatus.PUBLISH_READY.value != PublishExecutionStatus.COMPLETE.value
    assert FOUNDATION_SOURCE_NOT_READY != ImportReadinessStatus.NOT_IMPORT_READY.value
    assert "BUSINESS_CONTEXT_READY" != ImportReadinessStatus.IMPORT_READY.value
