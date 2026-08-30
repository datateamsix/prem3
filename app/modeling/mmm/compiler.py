"""Deterministic final ModelSpec compiler. No agent-authored Python."""

from __future__ import annotations

from typing import Any

from app.modeling.common.errors import MeridianCompatibilityError, ModelSpecInvalidError
from app.modeling.common.external_assets import PINNED_RUNTIME_VERSION
from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mmm.compatibility import (
    MEDIA_EFFECTS_DIST,
    MODELSPEC_PARAMS,
    ORGANIC_PRIOR_TYPES,
    PRIOR_TYPES,
)
from app.modeling.mmm.contracts import (
    CompiledMeridianModelSpec,
    FitPurpose,
    ModelPlan,
    PriorSource,
    PriorSpec,
)

ALLOWED_ADSTOCK = frozenset({"geometric", "binomial"})
ALLOWED_SATURATION = frozenset({"hill", "none"})


def _validate_decay_or_saturation(
    value: str | dict[str, str], *, allowed: frozenset[str], field: str
) -> None:
    if isinstance(value, str):
        if value not in allowed:
            raise ModelSpecInvalidError(f"Unsupported {field}={value}.")
        return
    for channel, spec in value.items():
        if spec not in allowed:
            raise ModelSpecInvalidError(f"Unsupported {field} for {channel}={spec}.")


def compile_meridian_model_spec(
    *,
    plan: ModelPlan,
    meridian_version: str = PINNED_RUNTIME_VERSION,
) -> CompiledMeridianModelSpec:
    if meridian_version != PINNED_RUNTIME_VERSION:
        raise MeridianCompatibilityError(
            f"Meridian version {meridian_version} is not the pinned runtime."
        )
    spec = plan.spec
    payload = spec.model_dump(mode="json", exclude_none=True)
    unknown = [key for key in payload if key not in MODELSPEC_PARAMS and key != "prior"]
    if unknown:
        raise ModelSpecInvalidError(f"Unsupported ModelSpec fields: {unknown}")
    if spec.media_effects_dist not in MEDIA_EFFECTS_DIST:
        raise ModelSpecInvalidError(
            f"media_effects_dist={spec.media_effects_dist!r} is invalid; "
            "roi belongs on media_prior_type."
        )
    if spec.media_prior_type not in PRIOR_TYPES:
        raise ModelSpecInvalidError(f"Unsupported media_prior_type={spec.media_prior_type}.")
    if spec.rf_prior_type not in PRIOR_TYPES:
        raise ModelSpecInvalidError(f"Unsupported rf_prior_type={spec.rf_prior_type}.")
    if spec.organic_media_prior_type not in ORGANIC_PRIOR_TYPES:
        raise ModelSpecInvalidError("Unsupported organic_media_prior_type.")
    if spec.enable_aks and spec.knots is not None:
        raise ModelSpecInvalidError("knots and enable_aks are mutually exclusive.")
    _validate_decay_or_saturation(
        spec.adstock_decay_spec, allowed=ALLOWED_ADSTOCK, field="adstock_decay_spec"
    )
    _validate_decay_or_saturation(
        spec.saturation_spec, allowed=ALLOWED_SATURATION, field="saturation_spec"
    )
    if spec.paid_media_prior_type is not None:
        raise ModelSpecInvalidError(
            "New plans must set media_prior_type and rf_prior_type, not paid_media_prior_type."
        )
    fingerprint = canonical_fingerprint(
        {
            "spec": payload,
            "priors": [item.model_dump(mode="json") for item in plan.priors],
            "meridian_version": meridian_version,
            "input_fingerprint": plan.model_ready_manifest_fingerprint,
            "model_window": [plan.model_window_start, plan.model_window_end],
            "mcmc": plan.mcmc,
        }
    )
    return CompiledMeridianModelSpec(
        spec=spec,
        priors=plan.priors,
        fingerprint=fingerprint,
        meridian_version=meridian_version,
        compatibility_status="COMPATIBLE",
    )


def compile_fit_plan_payload(
    plan: ModelPlan,
    *,
    fit_purpose: FitPurpose = FitPurpose.MODEL_ITERATION,
    container_image_digest: str | None = None,
    source_commit_sha: str | None = None,
    worker_build_id: str | None = None,
    python_version: str | None = None,
    tensorflow_version: str | None = None,
) -> dict[str, Any]:
    schedule = plan.mcmc.get("n_chains_schedule")
    payload: dict[str, Any] = {
        "n_chains": int(plan.mcmc["n_chains"]) if "n_chains" in plan.mcmc else 4,
        "n_adapt": int(plan.mcmc["n_adapt"]) if "n_adapt" in plan.mcmc else 500,
        "n_burnin": int(plan.mcmc["n_burnin"]) if "n_burnin" in plan.mcmc else 500,
        "n_keep": int(plan.mcmc["n_keep"]) if "n_keep" in plan.mcmc else 1000,
        "seed": int(plan.mcmc["seed"]) if "seed" in plan.mcmc else 1,
        "compute_profile": plan.compute_profile.value,
        "fit_purpose": fit_purpose.value,
        "container_image_digest": container_image_digest,
        "source_commit_sha": source_commit_sha,
        "worker_build_id": worker_build_id,
        "python_version": python_version,
        "tensorflow_version": tensorflow_version,
        "meridian_version": plan.meridian_version,
        "model_plan_fingerprint": plan.fingerprint,
        "input_fingerprint": plan.model_ready_manifest_fingerprint,
    }
    if isinstance(schedule, (list, tuple)):
        payload["n_chains_schedule"] = [int(item) for item in schedule]
    return payload


def default_priors() -> tuple[PriorSpec, ...]:
    return (
        PriorSpec(
            parameter="roi_m",
            distribution_family="LogNormal",
            parameters={"loc": 0.2, "scale": 0.9},
            source=PriorSource.MERIDIAN_DEFAULT,
            rationale="Meridian default ROI prior family; not customer-migrated.",
        ),
    )
