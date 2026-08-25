"""Frontend-ready MMM results read models — server computes acceptance/availability."""

from __future__ import annotations

from app.modeling.mmm.results.contracts import (
    MMMDecisionIntelligenceBrief,
    MMMResultsSnapshot,
    MMMResultsUnavailable,
)
from app.service.models import ApiModel


class MetricValueView(ApiModel):
    value: float | None = None
    availability: str
    unit: str | None = None
    interval_lower: float | None = None
    interval_upper: float | None = None


class ChannelResultView(ApiModel):
    channel_id: str
    channel_name: str
    spend: MetricValueView
    incremental_outcome: MetricValueView
    contribution: MetricValueView
    roi: MetricValueView
    marginal_roi: MetricValueView
    response_curve_ref: str | None = None
    availability: str


class PortfolioSummaryView(ApiModel):
    total_spend: MetricValueView
    modeled_incremental_outcome: MetricValueView
    portfolio_roi: MetricValueView


class ModelContextView(ApiModel):
    model_version_id: str
    fit_run_id: str
    model_window_start: str | None = None
    model_window_end: str | None = None
    meridian_version: str
    adapter_version: str
    model_accepted: bool
    eligibility: str


class HealthSummaryView(ApiModel):
    review_source: str
    model_accepted: bool
    blocking_failures: list[str]
    review_items: list[str]
    acknowledgments: list[str]


class FindingView(ApiModel):
    finding_id: str
    authority: str
    title: str
    statement: str
    affected_channels: list[str] = []


class LimitationView(ApiModel):
    limitation_id: str
    category: str
    severity: str
    title: str
    description: str


class NextActionView(ApiModel):
    action_id: str
    title: str
    statement: str
    authority: str


class ProvenanceSummaryView(ApiModel):
    result_snapshot_id: str
    result_fingerprint: str
    model_artifact_sha256: str
    fit_run_id: str
    model_plan_fingerprint: str | None = None
    fit_plan_fingerprint: str | None = None
    synthetic: bool = False
    synthetic_label: str | None = None


class MmmResultsReadModelResponse(ApiModel):
    status: str
    reason: str | None = None
    model_context: ModelContextView | None = None
    health_summary: HealthSummaryView | None = None
    portfolio_summary: PortfolioSummaryView | None = None
    channel_results: list[ChannelResultView] = []
    key_findings: list[FindingView] = []
    known_limitations: list[LimitationView] = []
    next_actions: list[NextActionView] = []
    provenance_summary: ProvenanceSummaryView | None = None
    acceptance_computed_by_server: bool = True
    recommendation_eligibility_computed_by_server: bool = True
    latest_result_snapshot_id: str | None = None
    accepted_result_snapshot_id: str | None = None


class ResponseCurvePointView(ApiModel):
    spend_level: float
    expected_outcome: float | None = None
    outcome_lower: float | None = None
    outcome_upper: float | None = None


class ResponseCurveView(ApiModel):
    response_curve_id: str
    channel_id: str
    points: list[ResponseCurvePointView]
    current_spend: float | None = None
    current_marginal_roi: float | None = None
    uncertainty_available: bool
    observed_spend_min: float | None = None
    observed_spend_max: float | None = None
    source_method: str


class MmmResponseCurvesResponse(ApiModel):
    status: str
    result_snapshot_id: str | None = None
    curves: list[ResponseCurveView] = []


class DecisionBriefResponse(ApiModel):
    status: str
    brief_id: str | None = None
    result_snapshot_id: str | None = None
    result_status: str | None = None
    eligibility: str | None = None
    executive_summary: str
    verified_findings: list[FindingView] = []
    interpretations: list[FindingView] = []
    recommendations: list[dict] = []
    counter_evidence: list[dict] = []
    uncertainties: list[FindingView] = []
    decision_requirements: list[NextActionView] = []
    acceptance_computed_by_server: bool = True
    investment_recommendations_allowed: bool = False


def _metric_view(metric) -> MetricValueView:
    interval = metric.interval
    return MetricValueView(
        value=metric.value,
        availability=metric.availability.value,
        unit=metric.unit,
        interval_lower=None if interval is None else interval.lower,
        interval_upper=None if interval is None else interval.upper,
    )


def render_unavailable(unavailable: MMMResultsUnavailable) -> MmmResultsReadModelResponse:
    return MmmResultsReadModelResponse(
        status=unavailable.status.value,
        reason=unavailable.reason.value,
        channel_results=[],
        key_findings=[],
        known_limitations=[],
        next_actions=[
            NextActionView(
                action_id="await-fit",
                title="Await completed posterior fit",
                statement=unavailable.detail
                or "Results are not available until an official Meridian fit completes.",
                authority="DECISION_REQUIRED",
            )
        ],
    )


def render_results(
    snapshot: MMMResultsSnapshot,
    *,
    brief: MMMDecisionIntelligenceBrief | None = None,
    latest_result_snapshot_id: str | None = None,
    accepted_result_snapshot_id: str | None = None,
) -> MmmResultsReadModelResponse:
    findings: list[FindingView] = []
    if brief is not None:
        findings = [
            FindingView(
                finding_id=item.finding_id,
                authority=item.authority.value,
                title=item.title,
                statement=item.statement,
                affected_channels=list(item.affected_channels),
            )
            for item in brief.verified_findings[:8]
        ]
    next_actions = []
    if brief is not None:
        next_actions = [
            NextActionView(
                action_id=item.requirement_id,
                title=item.title,
                statement=item.statement,
                authority=item.authority.value,
            )
            for item in brief.decision_requirements
        ]
    return MmmResultsReadModelResponse(
        status=snapshot.result_status.value,
        reason=None,
        model_context=ModelContextView(
            model_version_id=snapshot.model_version_id,
            fit_run_id=snapshot.fit_run_id,
            model_window_start=snapshot.model_window_start,
            model_window_end=snapshot.model_window_end,
            meridian_version=snapshot.meridian_version,
            adapter_version=snapshot.adapter_version,
            model_accepted=snapshot.fit_evidence.model_accepted,
            eligibility=snapshot.eligibility.value,
        ),
        health_summary=HealthSummaryView(
            review_source=snapshot.fit_evidence.official_review_source.value,
            model_accepted=snapshot.fit_evidence.model_accepted,
            blocking_failures=list(snapshot.fit_evidence.blocking_failures),
            review_items=list(snapshot.fit_evidence.review_items),
            acknowledgments=list(snapshot.fit_evidence.review_acknowledgments),
        ),
        portfolio_summary=PortfolioSummaryView(
            total_spend=_metric_view(snapshot.portfolio_summary.total_spend),
            modeled_incremental_outcome=_metric_view(
                snapshot.portfolio_summary.modeled_incremental_outcome
            ),
            portfolio_roi=_metric_view(snapshot.portfolio_summary.portfolio_roi),
        ),
        channel_results=[
            ChannelResultView(
                channel_id=channel.channel_id,
                channel_name=channel.channel_name,
                spend=_metric_view(channel.spend),
                incremental_outcome=_metric_view(channel.incremental_outcome),
                contribution=_metric_view(channel.contribution),
                roi=_metric_view(channel.roi),
                marginal_roi=_metric_view(channel.marginal_roi),
                response_curve_ref=channel.response_curve_ref,
                availability=channel.availability.value,
            )
            for channel in snapshot.channels
        ],
        key_findings=findings,
        known_limitations=[
            LimitationView(
                limitation_id=item.limitation_id,
                category=item.category.value,
                severity=item.severity.value,
                title=item.title,
                description=item.description,
            )
            for item in snapshot.limitations
        ],
        next_actions=next_actions,
        provenance_summary=ProvenanceSummaryView(
            result_snapshot_id=snapshot.result_snapshot_id,
            result_fingerprint=snapshot.result_fingerprint,
            model_artifact_sha256=snapshot.model_artifact_sha256,
            fit_run_id=snapshot.fit_run_id,
            model_plan_fingerprint=snapshot.model_plan_fingerprint,
            fit_plan_fingerprint=snapshot.fit_plan_fingerprint,
            synthetic=snapshot.synthetic,
            synthetic_label=snapshot.synthetic_label,
        ),
        latest_result_snapshot_id=latest_result_snapshot_id,
        accepted_result_snapshot_id=accepted_result_snapshot_id,
    )


def render_response_curves(snapshot: MMMResultsSnapshot) -> MmmResponseCurvesResponse:
    return MmmResponseCurvesResponse(
        status=snapshot.result_status.value,
        result_snapshot_id=snapshot.result_snapshot_id,
        curves=[
            ResponseCurveView(
                response_curve_id=curve.response_curve_id,
                channel_id=curve.channel_id,
                points=[
                    ResponseCurvePointView(
                        spend_level=point.spend_level,
                        expected_outcome=point.expected_outcome,
                        outcome_lower=point.outcome_lower,
                        outcome_upper=point.outcome_upper,
                    )
                    for point in curve.points
                ],
                current_spend=curve.current_spend,
                current_marginal_roi=curve.current_marginal_roi,
                uncertainty_available=curve.uncertainty_available,
                observed_spend_min=curve.observed_spend_min,
                observed_spend_max=curve.observed_spend_max,
                source_method=curve.source_method,
            )
            for curve in snapshot.response_curves
        ],
    )


def render_decision_brief(
    brief: MMMDecisionIntelligenceBrief,
) -> DecisionBriefResponse:
    investment_allowed = any(item.investment_action for item in brief.recommendations)
    return DecisionBriefResponse(
        status=brief.result_status.value,
        brief_id=brief.brief_id,
        result_snapshot_id=brief.result_snapshot_id,
        result_status=brief.result_status.value,
        eligibility=brief.eligibility.value,
        executive_summary=brief.executive_summary,
        verified_findings=[
            FindingView(
                finding_id=item.finding_id,
                authority=item.authority.value,
                title=item.title,
                statement=item.statement,
                affected_channels=list(item.affected_channels),
            )
            for item in brief.verified_findings
        ],
        interpretations=[
            FindingView(
                finding_id=item.finding_id,
                authority=item.authority.value,
                title=item.title,
                statement=item.statement,
                affected_channels=list(item.affected_channels),
            )
            for item in brief.interpretations
        ],
        recommendations=[item.model_dump(mode="json") for item in brief.recommendations],
        counter_evidence=[item.model_dump(mode="json") for item in brief.counter_evidence],
        uncertainties=[
            FindingView(
                finding_id=item.finding_id,
                authority=item.authority.value,
                title=item.title,
                statement=item.statement,
                affected_channels=list(item.affected_channels),
            )
            for item in brief.uncertainties
        ],
        decision_requirements=[
            NextActionView(
                action_id=item.requirement_id,
                title=item.title,
                statement=item.statement,
                authority=item.authority.value,
            )
            for item in brief.decision_requirements
        ],
        investment_recommendations_allowed=investment_allowed,
    )
