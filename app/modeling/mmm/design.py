"""Model Design Brief construction from pinned evidence. No raw chat authority."""

from __future__ import annotations

from typing import Any

from app.control_plane.ids import new_decision_id
from app.modeling.common.external_assets import PINNED_RUNTIME_VERSION, PINNED_UPSTREAM_COMMIT
from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mmm.compiler import default_priors
from app.modeling.mmm.contracts import (
    ComputeProfile,
    DecisionType,
    DesignBriefSection,
    KnowledgeClass,
    MeridianModelSpecProposal,
    MMMModelDesignBrief,
    ModelDecision,
    ModelPlan,
    Recommendation,
)

REQUIRED_DECISION_TYPES = (
    DecisionType.MODEL_WINDOW,
    DecisionType.MODEL_SCOPE,
    DecisionType.KPI_TYPE,
    DecisionType.MEDIA_PRIOR_TYPE,
    DecisionType.KNOT_STRATEGY,
    DecisionType.ENABLE_AKS,
    DecisionType.MAX_LAG,
    DecisionType.HOLDOUT,
    DecisionType.MCMC_CONFIGURATION,
)


def _section(
    name: str, proposal: Any, reason: str, *, refs: tuple[str, ...] = ()
) -> DesignBriefSection:
    return DesignBriefSection(
        name=name,
        recommendation=Recommendation(
            proposal=proposal,
            reason=reason,
            evidence_refs=refs,
            knowledge_asset_refs=(f"meridian:{PINNED_UPSTREAM_COMMIT}",),
            authority=KnowledgeClass.PREM3_DETERMINISTIC_EVIDENCE,
            requires_approval=True,
        ),
    )


def build_design_brief(
    *,
    model_version_id: str,
    model_window_start: str,
    model_window_end: str,
    scope: str,
    kpi: str,
    media_channels: tuple[str, ...],
    rf_channels: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    coverage=None,
) -> MMMModelDesignBrief:
    window = f"{model_window_start}/{model_window_end}"
    sections = (
        _section(
            "model objective",
            "Fit a Meridian MMM for incremental media contribution",
            "Business outcome is causal media contribution.",
            refs=evidence_refs,
        ),
        _section(
            "KPI / revenue treatment",
            kpi,
            "Pinned Business IQ KPI.",
            refs=evidence_refs,
        ),
        _section(
            "geo vs national scope",
            scope,
            "Derived from ModelReadyManifest geos.",
            refs=evidence_refs,
        ),
        _section(
            "final model window",
            window,
            "Final MMM window is a modeling decision, not Foundation cutoff.",
            refs=evidence_refs,
        ),
        _section(
            "paid-media treatments",
            media_channels,
            "Verified ModelReady mapping.",
            refs=evidence_refs,
        ),
        _section(
            "RF treatments",
            rf_channels,
            "RF channels stay on the RF builder path.",
            refs=evidence_refs,
        ),
        _section(
            "prior strategy",
            "roi",
            "Prefer media_prior_type=roi on current ModelSpec.",
            refs=evidence_refs,
        ),
        _section(
            "knots / AKS",
            {"knots": None, "enable_aks": False},
            "Do not hard-code knot count; AKS mutually exclusive with knots.",
            refs=evidence_refs,
        ),
        _section(
            "MCMC",
            {"n_chains": 4, "n_adapt": 500, "n_burnin": 500, "n_keep": 1000},
            "Human must approve exact FitPlan.",
            refs=evidence_refs,
        ),
    )
    required = [item.value for item in REQUIRED_DECISION_TYPES]
    if rf_channels:
        required.append(DecisionType.RF_PRIOR_TYPE.value)
    limitations = (
        "EDA ModelSpec is PRE_MODELING_EDA_ONLY and is not the fitted spec.",
        "Measurement Cycle dates are decision context, not the MMM model window.",
    )
    if coverage is not None:
        coverage_span = coverage.shared_usable_historical_coverage or (
            f"{coverage.earliest_time}/{coverage.latest_time}"
        )
        adequacy = (coverage_span, coverage.source or "model-ready-coverage")
    else:
        adequacy = ()
    return MMMModelDesignBrief(
        model_version_id=model_version_id,
        model_objective="Fit a reviewed Meridian MMM for incremental paid-media contribution.",
        kpi_treatment=kpi,
        geo_vs_national=scope,
        final_model_window=window,
        paid_media_treatments=media_channels,
        rf_treatments=rf_channels,
        time_effect_strategy="Meridian default time effects; knots/AKS require approval.",
        prior_strategy="media_prior_type=roi; custom numeric priors require evidence + approval.",
        adstock_strategy="geometric default unless evidence justifies binomial.",
        saturation_strategy="hill default.",
        population_scaling="Required for geo models when the contract requires population.",
        holdout_strategy="Optional holdout_id; default none.",
        mcmc_recommendation={
            "n_chains": 4,
            "n_adapt": 500,
            "n_burnin": 500,
            "n_keep": 1000,
            "seed": 1,
        },
        known_limitations=limitations,
        decisions_requiring_human_input=tuple(required),
        evidence_refs=evidence_refs,
        sections=sections,
        candidate_window=window,
        n_times=None if coverage is None else coverage.n_times,
        n_geos=None if coverage is None else coverage.n_geos,
        n_treatments=None if coverage is None else coverage.n_treatments,
        n_controls=None if coverage is None else coverage.n_controls,
        adequacy_evidence=adequacy,
    )


def proposed_model_plan(
    *,
    model_plan_id: str,
    model_version_id: str,
    model_ready_run_id: str,
    model_ready_manifest_fingerprint: str,
    business_profile_snapshot_id: str | None,
    model_window_start: str,
    model_window_end: str,
    scope: str,
    media_channels: tuple[str, ...],
    rf_channels: tuple[str, ...],
    compute_profile: ComputeProfile = ComputeProfile.CPU_TEST,
) -> ModelPlan:
    spec = MeridianModelSpecProposal(
        media_effects_dist="log_normal",
        media_prior_type="roi",
        rf_prior_type="roi" if rf_channels else "roi",
        enable_aks=False,
        knots=None,
        max_lag=8,
        hill_before_adstock=False,
        adstock_decay_spec="geometric",
        saturation_spec="hill",
    )
    mcmc = {"n_chains": 4, "n_adapt": 500, "n_burnin": 500, "n_keep": 1000, "seed": 1}
    fingerprint = canonical_fingerprint(
        {
            "input": model_ready_manifest_fingerprint,
            "window": [model_window_start, model_window_end],
            "spec": spec.model_dump(mode="json"),
            "priors": [item.model_dump(mode="json") for item in default_priors()],
            "mcmc": mcmc,
            "meridian_version": PINNED_RUNTIME_VERSION,
            "scope": scope,
            "channels": {"media": media_channels, "rf": rf_channels},
        }
    )
    return ModelPlan(
        model_plan_id=model_plan_id,
        model_version_id=model_version_id,
        model_ready_run_id=model_ready_run_id,
        model_ready_manifest_fingerprint=model_ready_manifest_fingerprint,
        business_profile_snapshot_id=business_profile_snapshot_id,
        meridian_version=PINNED_RUNTIME_VERSION,
        model_window_start=model_window_start,
        model_window_end=model_window_end,
        scope=scope,
        spec=spec,
        priors=default_priors(),
        mcmc=mcmc,
        compute_profile=compute_profile,
        rf_channels=rf_channels,
        media_channels=media_channels,
        fingerprint=fingerprint,
    )


def initial_decisions(
    *,
    tenant_id: str,
    project_id: str,
    model_version_id: str,
    plan: ModelPlan,
    include_rf: bool,
    include_ambiguous_promotion: bool = False,
    include_insufficient_controls: bool = False,
    include_experiment_prior: bool = False,
) -> list[ModelDecision]:
    items: list[ModelDecision] = []
    proposals: list[tuple[DecisionType, Any, str]] = [
        (
            DecisionType.MODEL_WINDOW,
            [plan.model_window_start, plan.model_window_end],
            "Final MMM window.",
        ),
        (DecisionType.MODEL_SCOPE, plan.scope, "National vs geo."),
        (DecisionType.KPI_TYPE, "revenue", "Pinned KPI treatment."),
        (
            DecisionType.MEDIA_PRIOR_TYPE,
            plan.spec.media_prior_type,
            "Current ModelSpec media_prior_type.",
        ),
        (DecisionType.KNOT_STRATEGY, plan.spec.knots, "Knot locations or count."),
        (
            DecisionType.ENABLE_AKS,
            plan.spec.enable_aks,
            "AKS mutually exclusive with knots.",
        ),
        (DecisionType.MAX_LAG, plan.spec.max_lag, "Adstock max lag."),
        (DecisionType.HOLDOUT, None, "Holdout tensor; default none."),
        (DecisionType.MCMC_CONFIGURATION, plan.mcmc, "Exact MCMC FitPlan values."),
    ]
    if include_rf:
        proposals.append(
            (DecisionType.RF_PRIOR_TYPE, plan.spec.rf_prior_type, "RF prior type.")
        )
    if include_ambiguous_promotion:
        proposals.append(
            (
                DecisionType.TREATMENT_CLASSIFICATION,
                {"promotion": "UNRESOLVED"},
                "Promotion role is ambiguous between control and non-media treatment.",
            )
        )
    if include_insufficient_controls:
        proposals.append(
            (
                DecisionType.CONTROL_SELECTION,
                {"status": "INSUFFICIENT_EVIDENCE"},
                "Do not select controls from correlation alone.",
            )
        )
    if include_experiment_prior:
        proposals.append(
            (
                DecisionType.CUSTOM_PRIOR,
                {
                    "parameter": "roi_m",
                    "source": "EXPERIMENT",
                    "channels": ["paid_search"],
                },
                "Experiment-informed prior requires evidence timing review and approval.",
            )
        )
        proposals.append(
            (
                DecisionType.ROI_CALIBRATION_PERIOD,
                {"status": "REQUIRES_APPROVAL"},
                "Calibration period is not auto-applied from historical evidence.",
            )
        )
    for decision_type, value, reason in proposals:
        items.append(
            ModelDecision(
                decision_id=new_decision_id(),
                model_version_id=model_version_id,
                tenant_id=tenant_id,
                project_id=project_id,
                decision_type=decision_type,
                proposal=value,
                recommended_value=value,
                authority=KnowledgeClass.PREM3_DETERMINISTIC_EVIDENCE,
                reason=reason,
                requires_approval=True,
                plan_fingerprint=plan.fingerprint,
            )
        )
    return items
