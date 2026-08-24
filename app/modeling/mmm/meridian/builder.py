"""Deterministic InputData construction from a verified ModelReadyManifest."""

from __future__ import annotations

from typing import Any

from app.modeling.common.errors import InputContractMismatchError


def mapping_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    semantics = manifest.get("semantics") or {}
    fingerprint = (
        (manifest.get("identity") or {}).get("canonical_artifact_fingerprint")
        or manifest.get("fingerprint")
    )
    if not fingerprint:
        raise InputContractMismatchError("ModelReadyManifest fingerprint is missing.")
    return {
        "fingerprint": fingerprint,
        "kpi": semantics.get("kpi"),
        "geo": semantics.get("geo"),
        "time": semantics.get("time"),
        "media": tuple(semantics.get("media_channels") or ()),
        "rf": tuple(semantics.get("rf_channels") or ()),
        "population": semantics.get("population"),
        "approved_for_final_modeling": False,
    }


def assert_not_eda_spec(context: dict[str, Any]) -> None:
    if context.get("purpose") == "PRE_MODELING_EDA_ONLY":
        raise InputContractMismatchError(
            "EDA ModelSpec is PRE_MODELING_EDA_ONLY and cannot be promoted."
        )
    if context.get("approved_for_final_modeling") is False and context.get("eda_only"):
        raise InputContractMismatchError("EDA-only spec cannot be used for fitting.")


def assert_input_fingerprint(expected: str, actual: str) -> None:
    if expected != actual:
        raise InputContractMismatchError("STALE_INPUT: ModelReady fingerprint changed.")
