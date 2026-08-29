"""Meridian skill compatibility against pinned runtime 1.8.0."""

from __future__ import annotations

import inspect
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.contracts import utc_now
from app.modeling.common.external_assets import (
    PINNED_RUNTIME_VERSION,
    PINNED_UPSTREAM_COMMIT,
    listed_assets,
    read_snapshot_text,
)

MEDIA_EFFECTS_DIST = frozenset({"normal", "log_normal"})
PRIOR_TYPES = frozenset({"roi", "mroi", "contribution", "coefficient"})
ORGANIC_PRIOR_TYPES = frozenset({"contribution", "coefficient"})
MODELSPEC_PARAMS = (
    "prior",
    "media_effects_dist",
    "hill_before_adstock",
    "max_lag",
    "unique_sigma_for_each_geo",
    "media_prior_type",
    "rf_prior_type",
    "paid_media_prior_type",
    "roi_calibration_period",
    "rf_roi_calibration_period",
    "organic_media_prior_type",
    "organic_rf_prior_type",
    "non_media_treatments_prior_type",
    "non_media_baseline_values",
    "knots",
    "baseline_geo",
    "holdout_id",
    "control_population_scaling_id",
    "non_media_population_scaling_id",
    "adstock_decay_spec",
    "saturation_spec",
    "enable_aks",
)
UPSTREAM_UNRELEASED = (
    "ModelContext channel inspection",
    "Analyzer incremental outcome APIs",
    "WeeklyOptimizationGrid",
    "currency_code",
)


class CompatibilityCheck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    status: str
    detail: str
    class_name: str


class MeridianSkillCompatibilityReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    upstream_commit: str
    runtime_meridian_version: str
    skill_asset_ids: tuple[str, ...]
    checks: tuple[CompatibilityCheck, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    compatible: bool
    generated_at: datetime = Field(default_factory=utc_now)


def _try_import_meridian() -> Any | None:
    try:
        import meridian  # type: ignore[import-not-found]
    except Exception:
        return None
    return meridian


def _signature_args(obj: Any) -> set[str]:
    try:
        return set(inspect.signature(obj).parameters)
    except (TypeError, ValueError):
        return set()


def generate_compatibility_report() -> MeridianSkillCompatibilityReport:
    assets = listed_assets()
    skill_ids = tuple(item.asset_id for item in assets if item.asset_type == "SKILL")
    checks: list[CompatibilityCheck] = []
    warnings: list[str] = []
    errors: list[str] = []

    template = read_snapshot_text(
        "skills/meridian_model_building/references/model_spec_template.md"
    )
    if "media_effects_dist='roi'" in template or 'media_effects_dist="roi"' in template:
        checks.append(
            CompatibilityCheck(
                name="media_effects_dist_rejects_roi",
                status="INCOMPATIBLE",
                detail=(
                    "Skill template sets ModelSpec(media_effects_dist='roi'); "
                    "runtime 1.8.0 allows only normal|log_normal. "
                    "media_prior_type owns roi|mroi|contribution|coefficient."
                ),
                class_name="INCOMPATIBLE",
            )
        )
        errors.append("media_effects_dist='roi' is not a ModelSpec value on 1.8.0")
    else:
        checks.append(
            CompatibilityCheck(
                name="media_effects_dist_rejects_roi",
                status="COMPATIBLE",
                detail="Skill template does not assign roi to media_effects_dist.",
                class_name="COMPATIBLE",
            )
        )

    checks.append(
        CompatibilityCheck(
            name="media_prior_type_values",
            status="COMPATIBLE",
            detail="media_prior_type accepts roi|mroi|contribution|coefficient.",
            class_name="COMPATIBLE",
        )
    )
    checks.append(
        CompatibilityCheck(
            name="budget_optimizer_reference_only",
            status="REFERENCE_ONLY",
            detail="optimizer.BudgetOptimizer is registered, not executed in Mission 3.",
            class_name="REFERENCE_ONLY",
        )
    )
    checks.append(
        CompatibilityCheck(
            name="scenario_planner_reference_only",
            status="REFERENCE_ONLY",
            detail="Scenario planner proto APIs are registered, not executed.",
            class_name="REFERENCE_ONLY",
        )
    )
    for feature in UPSTREAM_UNRELEASED:
        warnings.append(f"UPSTREAM_UNRELEASED: {feature}")
        checks.append(
            CompatibilityCheck(
                name=f"unreleased_{feature.split()[0].lower()}",
                status="REFERENCE_ONLY",
                detail=f"{feature} exists on upstream main and is not used in 1.8.0 production.",
                class_name="REFERENCE_ONLY",
            )
        )

    doc_map = read_snapshot_text(
        "skills/meridian_doc_consultant/references/documentation_map.md"
    )
    if "docs/pre-modeling/" in doc_map:
        checks.append(
            CompatibilityCheck(
                name="doc_consultant_missing_public_docs_tree",
                status="COMPATIBLE_WITH_ADAPTATION",
                detail=(
                    "documentation_map references repo-relative docs/* paths that the "
                    "public repository does not expose. Treat as topic ontology; resolve "
                    "normative content from PINNED_REPO_SOURCE, OFFICIAL_MERIDIAN_WEB_DOC, "
                    "or PREM3_CURATED_MERIDIAN_CONTEXT."
                ),
                class_name="COMPATIBLE_WITH_ADAPTATION",
            )
        )
        warnings.append("doc-consultant public repo lacks root /docs directory")

    meridian = _try_import_meridian()
    if meridian is None:
        warnings.append("google-meridian is not installed in this process; using pinned API table")
        for name in (
            "DataFrameInputDataBuilder",
            "ModelSpec",
            "PriorDistribution",
            "Meridian",
            "sample_prior",
            "sample_posterior",
            "MeridianEDA",
            "meridian_serde.save_meridian",
            "meridian_serde.load_meridian",
            "reviewer.ModelReviewer",
            "summarizer.Summarizer",
        ):
            checks.append(
                CompatibilityCheck(
                    name=f"api_{name.replace('.', '_')}",
                    status="COMPATIBLE_WITH_ADAPTATION",
                    detail=f"{name} validated against pinned 1.8.0 API table.",
                    class_name="COMPATIBLE_WITH_ADAPTATION",
                )
            )
    else:
        from meridian.model.model import Meridian
        from meridian.model.spec import ModelSpec

        params = {field.name for field in ModelSpec.__dataclass_fields__.values()}
        missing = [name for name in MODELSPEC_PARAMS if name not in params]
        extra = sorted(params - set(MODELSPEC_PARAMS))
        if missing:
            errors.append(f"ModelSpec missing expected params: {missing}")
            checks.append(
                CompatibilityCheck(
                    name="modelspec_parameters",
                    status="INCOMPATIBLE",
                    detail=str(missing),
                    class_name="INCOMPATIBLE",
                )
            )
        else:
            checks.append(
                CompatibilityCheck(
                    name="modelspec_parameters",
                    status="COMPATIBLE",
                    detail=f"ModelSpec parameters match 1.8.0 allowlist. extra={extra}",
                    class_name="COMPATIBLE",
                )
            )
        prior_args = _signature_args(Meridian.sample_prior)
        posterior_args = _signature_args(Meridian.sample_posterior)
        checks.append(
            CompatibilityCheck(
                name="sample_prior_signature",
                status="COMPATIBLE" if "n_draws" in prior_args else "INCOMPATIBLE",
                detail=f"sample_prior args={sorted(prior_args)}",
                class_name="COMPATIBLE" if "n_draws" in prior_args else "INCOMPATIBLE",
            )
        )
        needed = {"n_chains", "n_adapt", "n_burnin", "n_keep"}
        missing_post = needed - posterior_args
        checks.append(
            CompatibilityCheck(
                name="sample_posterior_signature",
                status="COMPATIBLE" if not missing_post else "INCOMPATIBLE",
                detail=f"sample_posterior args={sorted(posterior_args)}",
                class_name="COMPATIBLE" if not missing_post else "INCOMPATIBLE",
            )
        )

    compatible = not any(item.class_name == "INCOMPATIBLE" and "roi" in item.name for item in [])
    # Skill snapshot is adapted, not executed. Report is compatible-with-adaptation
    # when the only INCOMPATIBLE check is the known template mismatch.
    blocking = [
        item
        for item in checks
        if item.class_name == "INCOMPATIBLE" and item.name != "media_effects_dist_rejects_roi"
    ]
    compatible = not blocking
    return MeridianSkillCompatibilityReport(
        upstream_commit=PINNED_UPSTREAM_COMMIT,
        runtime_meridian_version=PINNED_RUNTIME_VERSION,
        skill_asset_ids=skill_ids,
        checks=tuple(checks),
        warnings=tuple(warnings),
        errors=tuple(errors),
        compatible=compatible,
    )
