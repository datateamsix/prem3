"""Build typed MMMResultsSnapshot from raw adapter evidence."""

from __future__ import annotations

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mmm.contracts import ReviewSource
from app.modeling.mmm.results import (
    ADAPTER_VERSION,
    MERIDIAN_RUNTIME_VERSION,
    METRIC_EXTRACTION_POLICY_VERSION,
)
from app.modeling.mmm.results.contracts import (
    EvidenceEligibility,
    MarginalEfficiencyEvidence,
    MetricAvailability,
    ModelFitEvidence,
    ModelLimitation,
    MMMChannelResult,
    MMMResultStatus,
    MMMResultsSnapshot,
    RawMeridianResultsEvidence,
    ResponseCurveEvidence,
    ResultProvenance,
)
from app.modeling.mmm.results.fingerprint import (
    new_result_snapshot_id,
    result_source_fingerprint,
    snapshot_content_fingerprint,
)
from app.modeling.mmm.results.portfolio import build_portfolio_summary
from app.modeling.mmm.results.validation import channel_availability, metric_value


def resolve_result_status(
    *,
    fit_complete: bool,
    model_accepted: bool,
    review_pending: bool,
    superseded: bool = False,
) -> MMMResultStatus:
    if not fit_complete:
        return MMMResultStatus.NOT_AVAILABLE
    if superseded:
        return MMMResultStatus.SUPERSEDED
    if model_accepted:
        return MMMResultStatus.ACCEPTED
    if review_pending:
        return MMMResultStatus.FIT_COMPLETE_REVIEW_PENDING
    return MMMResultStatus.REVIEWED_NOT_ACCEPTED


def resolve_eligibility(status: MMMResultStatus) -> EvidenceEligibility:
    if status is MMMResultStatus.ACCEPTED:
        return EvidenceEligibility.ACCEPTED_MODEL_RESULTS
    if status in {
        MMMResultStatus.FIT_COMPLETE_REVIEW_PENDING,
        MMMResultStatus.REVIEWED_NOT_ACCEPTED,
        MMMResultStatus.SUPERSEDED,
    }:
        return EvidenceEligibility.PRE_ACCEPTANCE_RESULTS
    return EvidenceEligibility.NOT_ELIGIBLE


def build_snapshot_from_raw(
    *,
    tenant_id: str,
    project_id: str,
    cycle_id: str,
    model_version_id: str,
    fit_run_id: str,
    model_artifact_sha256: str,
    raw: RawMeridianResultsEvidence,
    fit_evidence: ModelFitEvidence,
    provenance: ResultProvenance,
    result_status: MMMResultStatus,
    model_plan_fingerprint: str | None = None,
    fit_plan_fingerprint: str | None = None,
    review_pack_fingerprint: str | None = None,
    model_window_start: str | None = None,
    model_window_end: str | None = None,
    outcome_name: str | None = None,
    outcome_unit: str | None = None,
    currency: str | None = None,
    limitations: tuple[ModelLimitation, ...] = (),
    source_runtime: str = "OFFICIAL_MERIDIAN",
    synthetic_label: str | None = None,
) -> MMMResultsSnapshot:
    source_fp = result_source_fingerprint(
        model_artifact_sha256=model_artifact_sha256,
        model_version_id=model_version_id,
        fit_run_id=fit_run_id,
        adapter_version=raw.adapter_version or ADAPTER_VERSION,
        meridian_version=raw.meridian_version or MERIDIAN_RUNTIME_VERSION,
        metric_extraction_policy_version=METRIC_EXTRACTION_POLICY_VERSION,
    )
    result_snapshot_id = new_result_snapshot_id(source_fingerprint=source_fp)
    confidence = raw.confidence_level

    channels: list[MMMChannelResult] = []
    curves: list[ResponseCurveEvidence] = []
    marginal: list[MarginalEfficiencyEvidence] = []

    curve_by_channel = {item.channel_id: item for item in raw.response_curves}
    for bundle in raw.channels:
        spend = metric_value(bundle.spend, source_method="Analyzer.summary_metrics|get_historical_spend")
        incremental = metric_value(
            bundle.incremental_outcome,
            lower=bundle.incremental_outcome_lower,
            upper=bundle.incremental_outcome_upper,
            confidence_level=confidence,
            source_method="Analyzer.incremental_outcome",
        )
        contribution = metric_value(
            bundle.contribution,
            lower=bundle.contribution_lower,
            upper=bundle.contribution_upper,
            confidence_level=confidence,
            source_method="Analyzer.summary_metrics.pct_of_contribution",
        )
        roi = metric_value(
            bundle.roi,
            lower=bundle.roi_lower,
            upper=bundle.roi_upper,
            confidence_level=confidence,
            source_method="Analyzer.roi",
        )
        mroi = metric_value(
            bundle.marginal_roi,
            lower=bundle.marginal_roi_lower,
            upper=bundle.marginal_roi_upper,
            confidence_level=confidence,
            source_method="Analyzer.marginal_roi",
        )
        for flag_name, flag_value in bundle.metric_flags.items():
            if flag_value == "INVALID":
                if flag_name == "roi":
                    roi = metric_value(None, forced_availability=MetricAvailability.INVALID)
                elif flag_name == "marginal_roi":
                    mroi = metric_value(None, forced_availability=MetricAvailability.INVALID)
                elif flag_name == "incremental_outcome":
                    incremental = metric_value(None, forced_availability=MetricAvailability.INVALID)
                elif flag_name == "contribution":
                    contribution = metric_value(None, forced_availability=MetricAvailability.INVALID)

        curve_ref = None
        raw_curve = curve_by_channel.get(bundle.channel_id)
        if raw_curve is not None and raw_curve.points:
            curve_fp = canonical_fingerprint(
                {
                    "result_snapshot_id": result_snapshot_id,
                    "channel_id": bundle.channel_id,
                    "points": [p.model_dump(mode="json") for p in raw_curve.points],
                }
            )
            curve_ref = f"rc_{curve_fp[:20]}"
            curves.append(
                ResponseCurveEvidence(
                    response_curve_id=curve_ref,
                    result_snapshot_id=result_snapshot_id,
                    channel_id=bundle.channel_id,
                    points=raw_curve.points,
                    current_spend=raw_curve.current_spend if raw_curve.current_spend is not None else spend.value,
                    current_expected_outcome=None,
                    current_marginal_roi=mroi.value,
                    spend_unit=raw_curve.spend_unit,
                    outcome_unit=raw_curve.outcome_unit or outcome_unit,
                    uncertainty_available=raw_curve.uncertainty_available,
                    source_method=raw_curve.source_method,
                    fingerprint=curve_fp,
                    observed_spend_min=raw_curve.observed_spend_min,
                    observed_spend_max=raw_curve.observed_spend_max,
                )
            )

        availability = channel_availability(spend, incremental, contribution, roi, mroi)
        channels.append(
            MMMChannelResult(
                channel_id=bundle.channel_id,
                channel_name=bundle.channel_name,
                spend=spend,
                incremental_outcome=incremental,
                contribution=contribution,
                roi=roi,
                marginal_roi=mroi,
                response_curve_ref=curve_ref,
                evidence_status=availability,
                availability=availability,
            )
        )
        if mroi.availability in {MetricAvailability.VALUE, MetricAvailability.ZERO}:
            marginal.append(
                MarginalEfficiencyEvidence(
                    channel_id=bundle.channel_id,
                    current_spend=spend.value,
                    marginal_roi=mroi,
                    response_curve_ref=curve_ref,
                )
            )

    channel_tuple = tuple(channels)
    portfolio = build_portfolio_summary(channel_tuple)
    content_fp = snapshot_content_fingerprint(
        {
            "result_snapshot_id": result_snapshot_id,
            "source_fingerprint": source_fp,
            "channels": [c.model_dump(mode="json") for c in channel_tuple],
            "portfolio": portfolio.model_dump(mode="json"),
            "fit_evidence": fit_evidence.model_dump(mode="json"),
            "limitations": [item.model_dump(mode="json") for item in limitations],
            "response_curves": [item.model_dump(mode="json") for item in curves],
        }
    )
    return MMMResultsSnapshot(
        result_snapshot_id=result_snapshot_id,
        tenant_id=tenant_id,
        project_id=project_id,
        cycle_id=cycle_id,
        model_version_id=model_version_id,
        fit_run_id=fit_run_id,
        model_plan_fingerprint=model_plan_fingerprint,
        fit_plan_fingerprint=fit_plan_fingerprint,
        model_artifact_sha256=model_artifact_sha256,
        review_pack_fingerprint=review_pack_fingerprint,
        result_status=result_status,
        eligibility=resolve_eligibility(result_status),
        outcome_name=outcome_name,
        outcome_unit=outcome_unit,
        currency=currency,
        model_window_start=model_window_start,
        model_window_end=model_window_end,
        channels=channel_tuple,
        portfolio_summary=portfolio,
        response_curves=tuple(curves),
        marginal_efficiency=tuple(marginal),
        fit_evidence=fit_evidence,
        limitations=limitations,
        provenance=provenance.model_copy(
            update={
                "fit_run_id": fit_run_id,
                "model_artifact_sha256": model_artifact_sha256,
                "analyzer_source_methods": raw.source_methods_used,
            }
        ),
        source_runtime=source_runtime,
        meridian_version=raw.meridian_version or MERIDIAN_RUNTIME_VERSION,
        adapter_version=raw.adapter_version or ADAPTER_VERSION,
        metric_extraction_policy_version=METRIC_EXTRACTION_POLICY_VERSION,
        synthetic=raw.synthetic,
        synthetic_label=synthetic_label,
        result_fingerprint=content_fp,
    )


def default_fit_evidence(
    *,
    review_source: ReviewSource = ReviewSource.FAKE_TEST,
    model_accepted: bool = False,
    review_items: tuple[str, ...] = (),
    acknowledgments: tuple[str, ...] = (),
    blocking_failures: tuple[str, ...] = (),
) -> ModelFitEvidence:
    return ModelFitEvidence(
        official_review_source=review_source,
        review_checks=(),
        review_acknowledgments=acknowledgments,
        blocking_failures=blocking_failures,
        review_items=review_items,
        model_accepted=model_accepted,
    )
