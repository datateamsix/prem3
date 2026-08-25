"""Clearly labeled synthetic / official-compatible fixtures for M4-00 tests."""

from __future__ import annotations

from app.modeling.mmm.contracts import DecisionIntelligenceAuthority, ReviewSource
from app.modeling.mmm.results import ADAPTER_VERSION, MERIDIAN_RUNTIME_VERSION
from app.modeling.mmm.results.builder import build_snapshot_from_raw, default_fit_evidence, resolve_result_status
from app.modeling.mmm.results.contracts import (
    LimitationCategory,
    LimitationSeverity,
    ModelLimitation,
    MMMResultStatus,
    MMMResultsSnapshot,
    RawChannelMetricBundle,
    RawMeridianResultsEvidence,
    RawResponseCurveBundle,
    ResponseCurvePoint,
    ResultProvenance,
)


SYNTHETIC_LABEL = "SYNTHETIC_OFFICIAL_COMPATIBLE_FIXTURE"


def _provenance(fit_run_id: str, artifact_sha: str) -> ResultProvenance:
    return ResultProvenance(
        model_ready_fingerprint="fixture-model-ready",
        business_profile_snapshot_id="fixture-biz-iq",
        data_foundation_fingerprint="fixture-data-foundation",
        model_plan_fingerprint="fixture-model-plan",
        model_decision_ids=("dec-1",),
        fit_plan_fingerprint="fixture-fit-plan",
        fit_approval_id="fixture-fit-approval",
        fit_run_id=fit_run_id,
        model_artifact_sha256=artifact_sha,
        review_pack_fingerprint="fixture-review-pack",
        analyzer_source_methods=("Analyzer.roi", "Analyzer.marginal_roi"),
    )


def _base_channels(
    *,
    include_mroi: bool = True,
    include_intervals: bool = True,
    nan_roi_channel: str | None = None,
    zero_spend_channel: str | None = None,
) -> tuple[RawChannelMetricBundle, ...]:
    channels = [
        RawChannelMetricBundle(
            channel_id="paid_search",
            channel_name="Paid Search",
            spend=1000.0,
            incremental_outcome=1400.0,
            incremental_outcome_lower=1200.0 if include_intervals else None,
            incremental_outcome_upper=1600.0 if include_intervals else None,
            contribution=0.40,
            contribution_lower=0.35 if include_intervals else None,
            contribution_upper=0.45 if include_intervals else None,
            roi=1.4,
            roi_lower=1.1 if include_intervals else None,
            roi_upper=1.7 if include_intervals else None,
            marginal_roi=1.1 if include_mroi else None,
            marginal_roi_lower=0.8 if include_mroi and include_intervals else None,
            marginal_roi_upper=1.3 if include_mroi and include_intervals else None,
            source_methods=("Analyzer.roi", "Analyzer.marginal_roi", "Analyzer.summary_metrics"),
            metric_flags={} if include_mroi else {"marginal_roi": "NOT_AVAILABLE"},
        ),
        RawChannelMetricBundle(
            channel_id="paid_social",
            channel_name="Paid Social",
            spend=800.0,
            incremental_outcome=1200.0,
            incremental_outcome_lower=900.0 if include_intervals else None,
            incremental_outcome_upper=1500.0 if include_intervals else None,
            contribution=0.35,
            roi=1.5,
            roi_lower=1.0 if include_intervals else None,
            roi_upper=2.0 if include_intervals else None,
            marginal_roi=1.4 if include_mroi else None,
            marginal_roi_lower=0.5 if include_mroi and include_intervals else None,
            marginal_roi_upper=2.2 if include_mroi and include_intervals else None,
            source_methods=("Analyzer.roi", "Analyzer.marginal_roi", "Analyzer.summary_metrics"),
            metric_flags={} if include_mroi else {"marginal_roi": "NOT_AVAILABLE"},
        ),
        RawChannelMetricBundle(
            channel_id="display",
            channel_name="Display",
            spend=500.0 if zero_spend_channel != "display" else 0.0,
            incremental_outcome=200.0,
            contribution=0.10,
            roi=0.4,
            marginal_roi=0.2 if include_mroi else None,
            source_methods=("Analyzer.roi", "Analyzer.summary_metrics"),
            metric_flags={} if include_mroi else {"marginal_roi": "NOT_AVAILABLE"},
        ),
    ]
    if nan_roi_channel:
        updated: list[RawChannelMetricBundle] = []
        for item in channels:
            if item.channel_id == nan_roi_channel:
                updated.append(
                    item.model_copy(
                        update={
                            "roi": float("nan"),
                            "metric_flags": {**item.metric_flags, "roi": "INVALID"},
                        }
                    )
                )
            else:
                updated.append(item)
        channels = updated
    return tuple(channels)


def _curves() -> tuple[RawResponseCurveBundle, ...]:
    return (
        RawResponseCurveBundle(
            channel_id="paid_social",
            points=(
                ResponseCurvePoint(spend_level=400.0, expected_outcome=700.0, outcome_lower=600.0, outcome_upper=800.0),
                ResponseCurvePoint(spend_level=800.0, expected_outcome=1200.0, outcome_lower=900.0, outcome_upper=1500.0),
                ResponseCurvePoint(spend_level=1200.0, expected_outcome=1500.0, outcome_lower=1100.0, outcome_upper=1800.0),
            ),
            current_spend=800.0,
            uncertainty_available=True,
            observed_spend_min=400.0,
            observed_spend_max=1200.0,
        ),
    )


def raw_healthy() -> RawMeridianResultsEvidence:
    return RawMeridianResultsEvidence(
        meridian_version=MERIDIAN_RUNTIME_VERSION,
        adapter_version=ADAPTER_VERSION,
        source_methods_used=(
            "Analyzer.roi",
            "Analyzer.incremental_outcome",
            "Analyzer.marginal_roi",
            "Analyzer.summary_metrics",
            "Analyzer.response_curves",
        ),
        source_methods_unavailable=(),
        channels=_base_channels(),
        response_curves=_curves(),
        confidence_level=0.9,
        notes=("SYNTHETIC fixture — not Music Center production evidence.",),
        synthetic=True,
    )


def snapshot_fixture(
    *,
    name: str,
    tenant_id: str = "tenant-a",
    project_id: str = "project-a",
    cycle_id: str = "cycle-a",
    model_version_id: str = "mv-fixture",
    fit_run_id: str = "fit-fixture",
    artifact_sha: str = "a" * 64,
    model_accepted: bool = False,
    review_pending: bool = True,
    superseded: bool = False,
    include_mroi: bool = True,
    include_intervals: bool = True,
    nan_roi_channel: str | None = None,
    review_items: tuple[str, ...] = (),
) -> MMMResultsSnapshot:
    if name == "missing_mroi":
        include_mroi = False
    if name == "missing_interval":
        include_intervals = False
    if name == "nan_inf_metric":
        nan_roi_channel = "paid_search"
    if name == "accepted_fit":
        model_accepted = True
        review_pending = False
    if name == "unaccepted_fit":
        model_accepted = False
        review_pending = False
    if name == "with_review":
        review_items = ("rhat_attention",)
        review_pending = True
    if name == "superseded_accepted":
        model_accepted = True
        review_pending = False
        superseded = True

    raw = RawMeridianResultsEvidence(
        meridian_version=MERIDIAN_RUNTIME_VERSION,
        adapter_version=ADAPTER_VERSION,
        source_methods_used=("Analyzer.roi", "Analyzer.summary_metrics"),
        source_methods_unavailable=() if include_mroi else ("Analyzer.marginal_roi",),
        channels=_base_channels(
            include_mroi=include_mroi,
            include_intervals=include_intervals,
            nan_roi_channel=nan_roi_channel,
        ),
        response_curves=_curves() if name != "missing_mroi" else (),
        confidence_level=0.9 if include_intervals else None,
        notes=(f"SYNTHETIC fixture `{name}` — not Music Center production evidence.",),
        synthetic=True,
    )
    status = resolve_result_status(
        fit_complete=True,
        model_accepted=model_accepted and not superseded,
        review_pending=review_pending,
        superseded=superseded,
    )
    if superseded:
        status = MMMResultStatus.SUPERSEDED
    limitations: tuple[ModelLimitation, ...] = ()
    if review_items:
        limitations = (
            ModelLimitation(
                limitation_id="lim-review-1",
                category=LimitationCategory.MODEL_REVIEW,
                authority=DecisionIntelligenceAuthority.VERIFIED,
                severity=LimitationSeverity.WARN,
                title="Official REVIEW item present",
                description="Model review requires acknowledgment before acceptance.",
                evidence_refs=review_items,
                affected_metrics=(),
            ),
        )
    return build_snapshot_from_raw(
        tenant_id=tenant_id,
        project_id=project_id,
        cycle_id=cycle_id,
        model_version_id=model_version_id,
        fit_run_id=fit_run_id,
        model_artifact_sha256=artifact_sha,
        raw=raw,
        fit_evidence=default_fit_evidence(
            review_source=ReviewSource.OFFICIAL_MERIDIAN,
            model_accepted=model_accepted and status is MMMResultStatus.ACCEPTED,
            review_items=review_items,
        ),
        provenance=_provenance(fit_run_id, artifact_sha),
        result_status=status,
        model_plan_fingerprint="fixture-model-plan",
        fit_plan_fingerprint="fixture-fit-plan",
        review_pack_fingerprint="fixture-review-pack",
        model_window_start="2024-01-01",
        model_window_end="2025-12-31",
        outcome_name="revenue",
        outcome_unit="USD",
        currency="USD",
        limitations=limitations,
        source_runtime="SYNTHETIC_FIXTURE",
        synthetic_label=SYNTHETIC_LABEL,
    )


FIXTURE_NAMES = (
    "healthy_completed_fit",
    "with_review",
    "missing_mroi",
    "missing_interval",
    "nan_inf_metric",
    "unaccepted_fit",
    "accepted_fit",
    "superseded_accepted",
)
