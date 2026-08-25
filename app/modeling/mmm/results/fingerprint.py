"""Result and brief fingerprint helpers."""

from __future__ import annotations

from typing import Any

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mmm.results import (
    ADAPTER_VERSION,
    MERIDIAN_RUNTIME_VERSION,
    METRIC_EXTRACTION_POLICY_VERSION,
)


def result_source_fingerprint(
    *,
    model_artifact_sha256: str,
    model_version_id: str,
    fit_run_id: str,
    adapter_version: str = ADAPTER_VERSION,
    meridian_version: str = MERIDIAN_RUNTIME_VERSION,
    metric_extraction_policy_version: str = METRIC_EXTRACTION_POLICY_VERSION,
) -> str:
    return canonical_fingerprint(
        {
            "model_artifact_sha256": model_artifact_sha256,
            "model_version_id": model_version_id,
            "fit_run_id": fit_run_id,
            "adapter_version": adapter_version,
            "meridian_version": meridian_version,
            "metric_extraction_policy_version": metric_extraction_policy_version,
        }
    )


def snapshot_content_fingerprint(payload: dict[str, Any]) -> str:
    return canonical_fingerprint(payload)


def brief_fingerprint(payload: dict[str, Any]) -> str:
    return canonical_fingerprint(payload)


def new_result_snapshot_id(*, source_fingerprint: str) -> str:
    return f"mrs_{source_fingerprint[:24]}"


def new_brief_id(*, result_snapshot_id: str, policy_version: str) -> str:
    digest = canonical_fingerprint(
        {"result_snapshot_id": result_snapshot_id, "policy_version": policy_version}
    )
    return f"dib_{digest[:24]}"
