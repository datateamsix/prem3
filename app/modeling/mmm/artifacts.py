"""Versioned modeling artifact helpers. Binary models are not stored in Firestore."""

from __future__ import annotations

import hashlib
from typing import Any

from app.core.resource_paths import modeling_artifact_prefix
from app.modeling.common.errors import ArtifactVerificationFailedError
from app.modeling.mmm.contracts import MeridianModelArtifactManifest
from app.modeling.mmm.ledger import BQ_MODEL_LEDGER_TABLES

CANONICAL_MODEL_BINARY_NAME = "meridian_model.binpb"
HEALTH_HTML_NAME = "model_health.html"
RESULTS_HTML_NAME = "results_summary.html"
ARTIFACT_MANIFEST_NAME = "model_artifact_manifest.json"
REVIEW_PACK_NAME = "model_review_pack.json"
REPRODUCIBILITY_NAME = "reproducibility_manifest.json"


def model_version_object_name(prefix: str, filename: str) -> str:
    return f"{prefix.rstrip('/')}/{filename}"


def persist_immutable_bytes(
    store: Any,
    *,
    bucket: str,
    object_name: str,
    data: bytes,
    content_type: str,
    expected_sha256: str | None = None,
) -> str:
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ArtifactVerificationFailedError("Artifact bytes do not match expected SHA-256.")
    existing = store.get_object_metadata(bucket=bucket, object_name=object_name)
    if existing is not None:
        reader = getattr(store, "read_bytes", None)
        stored = reader(bucket=bucket, object_name=object_name) if callable(reader) else None
        if stored is None and hasattr(store, "objects"):
            current = store.objects.get((bucket, object_name))
            stored = bytes(current["data"]) if current is not None else None
        if stored is None:
            raise ArtifactVerificationFailedError("Model-version artifact path already exists.")
        stored_digest = hashlib.sha256(stored).hexdigest()
        if stored_digest != digest:
            raise ArtifactVerificationFailedError(
                "Model-version artifact path is immutable; SHA-256 mismatch."
            )
        return digest
    store.write_bytes(
        bucket=bucket,
        object_name=object_name,
        data=data,
        content_type=content_type,
    )
    return digest


def modeling_prefix(tenant_id: str, project_id: str, model_version_id: str) -> str:
    return modeling_artifact_prefix(tenant_id, project_id, model_version_id)


__all__ = [
    "ARTIFACT_MANIFEST_NAME",
    "BQ_MODEL_LEDGER_TABLES",
    "CANONICAL_MODEL_BINARY_NAME",
    "HEALTH_HTML_NAME",
    "REPRODUCIBILITY_NAME",
    "RESULTS_HTML_NAME",
    "REVIEW_PACK_NAME",
    "MeridianModelArtifactManifest",
    "model_version_object_name",
    "modeling_prefix",
    "persist_immutable_bytes",
]
