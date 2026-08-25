"""Decision Intelligence brief compiler — separate from verified result snapshots."""

from __future__ import annotations

from app.modeling.mmm.contracts import DecisionIntelligenceAuthority
from app.modeling.mmm.results.contracts import (
    AdvisorRecommendation,
    CounterEvidence,
    DecisionIntelligenceFinding,
    DecisionRequirement,
    EvidenceEligibility,
    FindingType,
    MetricAvailability,
    MMMDecisionIntelligenceBrief,
    MMMResultStatus,
    MMMResultsSnapshot,
)
from app.modeling.mmm.results.fingerprint import brief_fingerprint, new_brief_id

DI_POLICY_VERSION = "m4-00.1"
DI_KNOWLEDGE_VERSION = "m4-00.1"


def compile_decision_intelligence_brief(
    *,
    snapshot: MMMResultsSnapshot,
    business_iq_notes: tuple[str, ...] = (),
    allow_investment_recommendations: bool | None = None,
) -> MMMDecisionIntelligenceBrief:
    """Compile advisor brief. Does not mutate the result snapshot.

    Default production policy: investment recommendations require MODEL_ACCEPTED /
    ACCEPTED result status.
    """
    accepted = snapshot.result_status is MMMResultStatus.ACCEPTED
    if allow_investment_recommendations is None:
        allow_investment_recommendations = accepted

    verified: list[DecisionIntelligenceFinding] = []
    interpretations: list[DecisionIntelligenceFinding] = []
    uncertainties: list[DecisionIntelligenceFinding] = []
    counters: list[CounterEvidence] = []
    recommendations: list[AdvisorRecommendation] = []
    decisions: list[DecisionRequirement] = []

    for channel in snapshot.channels:
        if channel.roi.availability is MetricAvailability.VALUE and channel.roi.value is not None:
            verified.append(
                DecisionIntelligenceFinding(
                    finding_id=f"verified-roi-{channel.channel_id}",
                    authority=DecisionIntelligenceAuthority.VERIFIED,
                    finding_type=FindingType.CHANNEL_METRIC,
                    title=f"{channel.channel_name} ROI",
                    statement=f"{channel.channel_name} ROI = {channel.roi.value}",
                    evidence_refs=(snapshot.result_fingerprint, f"channel:{channel.channel_id}:roi"),
                    affected_channels=(channel.channel_id,),
                )
            )
        if (
            channel.marginal_roi.availability is MetricAvailability.VALUE
            and channel.marginal_roi.value is not None
        ):
            verified.append(
                DecisionIntelligenceFinding(
                    finding_id=f"verified-mroi-{channel.channel_id}",
                    authority=DecisionIntelligenceAuthority.VERIFIED,
                    finding_type=FindingType.CHANNEL_METRIC,
                    title=f"{channel.channel_name} mROI",
                    statement=f"{channel.channel_name} mROI = {channel.marginal_roi.value}",
                    evidence_refs=(
                        snapshot.result_fingerprint,
                        f"channel:{channel.channel_id}:marginal_roi",
                    ),
                    affected_channels=(channel.channel_id,),
                )
            )
            interval = channel.marginal_roi.interval
            if (
                interval is not None
                and interval.availability is MetricAvailability.VALUE
                and interval.lower is not None
                and interval.upper is not None
                and (interval.upper - interval.lower) >= max(1.0, abs(channel.marginal_roi.value))
            ):
                counters.append(
                    CounterEvidence(
                        counter_evidence_id=f"ce-wide-mroi-{channel.channel_id}",
                        statement=(
                            f"{channel.channel_name} mROI interval is wide "
                            f"[{interval.lower}, {interval.upper}]."
                        ),
                        evidence_refs=(f"channel:{channel.channel_id}:marginal_roi.interval",),
                        affected_channels=(channel.channel_id,),
                    )
                )
                uncertainties.append(
                    DecisionIntelligenceFinding(
                        finding_id=f"unc-mroi-{channel.channel_id}",
                        authority=DecisionIntelligenceAuthority.INTERPRETATION,
                        finding_type=FindingType.LIMITATION,
                        title=f"Uncertainty around {channel.channel_name} mROI",
                        statement="Wide credible interval reduces action confidence.",
                        evidence_refs=(f"channel:{channel.channel_id}:marginal_roi.interval",),
                        affected_channels=(channel.channel_id,),
                    )
                )
        if channel.roi.availability is MetricAvailability.NOT_AVAILABLE:
            # Explicitly do not render missing metrics as zero.
            uncertainties.append(
                DecisionIntelligenceFinding(
                    finding_id=f"unc-missing-roi-{channel.channel_id}",
                    authority=DecisionIntelligenceAuthority.VERIFIED,
                    finding_type=FindingType.LIMITATION,
                    title=f"{channel.channel_name} ROI not available",
                    statement="ROI is NOT_AVAILABLE; it is not zero.",
                    evidence_refs=(f"channel:{channel.channel_id}:roi",),
                    affected_channels=(channel.channel_id,),
                )
            )
        if channel.roi.availability is MetricAvailability.INVALID:
            uncertainties.append(
                DecisionIntelligenceFinding(
                    finding_id=f"unc-invalid-roi-{channel.channel_id}",
                    authority=DecisionIntelligenceAuthority.VERIFIED,
                    finding_type=FindingType.LIMITATION,
                    title=f"{channel.channel_name} ROI invalid",
                    statement="ROI failed finite validation and must not be coerced.",
                    evidence_refs=(f"channel:{channel.channel_id}:roi",),
                    affected_channels=(channel.channel_id,),
                )
            )

    # Interpretation: relative marginal efficiency without advisory grades.
    ranked = [
        ch
        for ch in snapshot.channels
        if ch.marginal_roi.availability is MetricAvailability.VALUE and ch.marginal_roi.value is not None
    ]
    ranked.sort(key=lambda ch: float(ch.marginal_roi.value or 0.0), reverse=True)
    if ranked:
        top = ranked[0]
        interpretations.append(
            DecisionIntelligenceFinding(
                finding_id=f"interp-mroi-{top.channel_id}",
                authority=DecisionIntelligenceAuthority.INTERPRETATION,
                finding_type=FindingType.CHANNEL_METRIC,
                title=f"{top.channel_name} retains relative marginal efficiency",
                statement=(
                    f"{top.channel_name} appears to retain more marginal efficiency at current spend "
                    "than other modeled channels in this snapshot."
                ),
                evidence_refs=(
                    snapshot.result_fingerprint,
                    f"channel:{top.channel_id}:marginal_roi",
                ),
                affected_channels=(top.channel_id,),
            )
        )

    for note in business_iq_notes:
        interpretations.append(
            DecisionIntelligenceFinding(
                finding_id=f"biziq-{abs(hash(note)) % 10_000_000}",
                authority=DecisionIntelligenceAuthority.INTERPRETATION,
                finding_type=FindingType.BUSINESS_IQ_CONTEXT,
                title="Business IQ context",
                statement=note,
                evidence_refs=("BUSINESS_IQ_CONTEXT",),
            )
        )

    for limitation in snapshot.limitations:
        uncertainties.append(
            DecisionIntelligenceFinding(
                finding_id=f"lim-{limitation.limitation_id}",
                authority=limitation.authority,
                finding_type=FindingType.LIMITATION,
                title=limitation.title,
                statement=limitation.description,
                evidence_refs=limitation.evidence_refs,
                affected_channels=limitation.affected_channels,
            )
        )

    for item in snapshot.fit_evidence.review_items:
        if item not in snapshot.fit_evidence.review_acknowledgments:
            decisions.append(
                DecisionRequirement(
                    requirement_id=f"ack-{item}",
                    title=f"Acknowledge review item {item}",
                    statement=f"Official REVIEW item {item} requires human acknowledgment.",
                    evidence_refs=(snapshot.result_fingerprint, item),
                )
            )

    if not accepted:
        decisions.append(
            DecisionRequirement(
                requirement_id="accept-model",
                title="Model acceptance required",
                statement=(
                    "Pre-acceptance results cannot authorize investment action or "
                    "downstream scenario/budget execution."
                ),
                evidence_refs=(snapshot.result_fingerprint,),
            )
        )

    if allow_investment_recommendations and ranked:
        top = ranked[0]
        counter_refs = tuple(
            ce.counter_evidence_id
            for ce in counters
            if top.channel_id in ce.affected_channels
        )
        unc_refs = tuple(
            u.finding_id for u in uncertainties if top.channel_id in u.affected_channels
        )
        # Do not recommend solely because mROI is highest; require accepted + evidence refs.
        recommendations.append(
            AdvisorRecommendation(
                recommendation_id=f"rec-eval-{top.channel_id}",
                title=f"Evaluate controlled change for {top.channel_name}",
                recommended_action=(
                    f"Evaluate a controlled spend change for {top.channel_name} within the "
                    "supported response range."
                ),
                rationale=(
                    "Accepted-model verified mROI and response-curve context support a bounded "
                    "evaluation — not an automatic reallocation."
                ),
                evidence_refs=(
                    snapshot.result_fingerprint,
                    f"channel:{top.channel_id}:marginal_roi",
                ),
                counter_evidence_refs=counter_refs,
                uncertainty_refs=unc_refs,
                affected_channels=(top.channel_id,),
                decision_required=True,
                investment_action=True,
            )
        )
        decisions.append(
            DecisionRequirement(
                requirement_id="approve-scenario-analysis",
                title="Approve scenario analysis",
                statement="Human approval is required before scenario or budget optimization.",
                evidence_refs=(snapshot.result_fingerprint,),
                affected_channels=(top.channel_id,),
            )
        )

    if accepted:
        executive = (
            "Accepted-model verified evidence is available for decision intelligence. "
            "Recommendations remain advisory until a human decides."
        )
    elif snapshot.result_status is MMMResultStatus.NOT_AVAILABLE:
        executive = "Results are not available; no investment advice is issued."
    else:
        executive = (
            "Pre-acceptance technical results and interpretations are available. "
            "No investment action recommendations are issued."
        )

    brief_id = new_brief_id(
        result_snapshot_id=snapshot.result_snapshot_id, policy_version=DI_POLICY_VERSION
    )
    payload = {
        "brief_id": brief_id,
        "result_snapshot_id": snapshot.result_snapshot_id,
        "verified": [item.model_dump(mode="json") for item in verified],
        "interpretations": [item.model_dump(mode="json") for item in interpretations],
        "recommendations": [item.model_dump(mode="json") for item in recommendations],
        "policy_version": DI_POLICY_VERSION,
    }
    return MMMDecisionIntelligenceBrief(
        brief_id=brief_id,
        result_snapshot_id=snapshot.result_snapshot_id,
        model_version_id=snapshot.model_version_id,
        fit_run_id=snapshot.fit_run_id,
        result_status=snapshot.result_status,
        eligibility=snapshot.eligibility,
        executive_summary=executive,
        verified_findings=tuple(verified),
        interpretations=tuple(interpretations),
        recommendations=tuple(recommendations),
        counter_evidence=tuple(counters),
        uncertainties=tuple(uncertainties),
        decision_requirements=tuple(decisions),
        evidence_refs=(snapshot.result_fingerprint,),
        policy_version=DI_POLICY_VERSION,
        knowledge_version=DI_KNOWLEDGE_VERSION,
        fingerprint=brief_fingerprint(payload),
    )


def assert_verified_finding_has_typed_evidence(finding: DecisionIntelligenceFinding) -> None:
    if finding.authority is DecisionIntelligenceAuthority.VERIFIED and not finding.evidence_refs:
        raise ValueError("VERIFIED findings require typed evidence_refs.")
