"""Deterministic InputData construction from a verified ModelReadyManifest."""

from __future__ import annotations

from typing import Any

from app.modeling.common.errors import InputContractMismatchError
from app.modeling.mmm.contracts import ModelPlan

SUPPORTED_CASES = (
    "geo",
    "national",
    "ordinary_media",
    "reach_frequency",
    "organic_media",
    "controls",
    "non_media_treatments",
    "population",
    "revenue_per_kpi",
)


def mapping_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    semantics = manifest.get("semantics") or {}
    fingerprint = (manifest.get("identity") or {}).get(
        "canonical_artifact_fingerprint"
    ) or manifest.get("fingerprint")
    if not fingerprint:
        raise InputContractMismatchError("ModelReadyManifest fingerprint is missing.")
    return {
        "fingerprint": fingerprint,
        "kpi": semantics.get("kpi"),
        "kpi_type": semantics.get("kpi_type") or "revenue",
        "geo": semantics.get("geo"),
        "time": semantics.get("time"),
        "media": tuple(semantics.get("media_channels") or ()),
        "media_spend": tuple(semantics.get("media_spend_channels") or ()),
        "media_channels": tuple(semantics.get("media_channel_names") or ()),
        "rf": tuple(semantics.get("rf_channels") or ()),
        "organic_media": tuple(semantics.get("organic_media") or ()),
        "organic_media_channels": tuple(semantics.get("organic_media_channels") or ()),
        "controls": tuple(semantics.get("controls") or ()),
        "non_media_treatments": tuple(semantics.get("non_media_treatments") or ()),
        "population": semantics.get("population"),
        "revenue_per_kpi": semantics.get("revenue_per_kpi"),
        "scope": semantics.get("scope"),
        "approved_for_final_modeling": False,
    }


def compile_input_mapping(
    *,
    plan: ModelPlan,
    mapping: dict[str, Any],
) -> dict[str, Any]:
    compiled = dict(mapping)
    fingerprint = compiled.get("fingerprint")
    if fingerprint and fingerprint != plan.model_ready_manifest_fingerprint:
        raise InputContractMismatchError("INPUT_CONTRACT_MISMATCH")
    if compiled.get("media_channels") and plan.media_channels:
        expected = tuple(compiled.get("media_channels") or compiled.get("media") or ())
        planned = tuple(plan.media_channels)
        if expected and planned != expected and set(planned) - set(expected):
            raise InputContractMismatchError("INPUT_CONTRACT_MISMATCH")
    if plan.rf_channels and compiled.get("rf") is not None:
        if set(plan.rf_channels) - set(compiled.get("rf") or ()):
            raise InputContractMismatchError("INPUT_CONTRACT_MISMATCH")
    if plan.scope == "GEO" and not compiled.get("geo") and compiled.get("frame") is not None:
        raise InputContractMismatchError("INPUT_CONTRACT_MISMATCH")
    return compiled


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


def supported_mapping_cases(mapping: dict[str, Any]) -> tuple[str, ...]:
    found: list[str] = []
    if mapping.get("geo"):
        found.append("geo")
    else:
        found.append("national")
    if mapping.get("media"):
        found.append("ordinary_media")
    if mapping.get("rf"):
        found.append("reach_frequency")
    if mapping.get("organic_media"):
        found.append("organic_media")
    if mapping.get("controls"):
        found.append("controls")
    if mapping.get("non_media_treatments"):
        found.append("non_media_treatments")
    if mapping.get("population"):
        found.append("population")
    if mapping.get("revenue_per_kpi"):
        found.append("revenue_per_kpi")
    return tuple(found)
