"""Lightweight Decision Intelligence seam. No autonomous investment action."""

from __future__ import annotations

from app.modeling.mmm.contracts import (
    DecisionIntelligenceAuthority,
    DecisionIntelligenceRecommendation,
    MeridianModelHealthReceipt,
    MMMDecisionIntelligenceBrief,
    MMMModelReviewPack,
    OfficialHealthStatus,
    ReviewSource,
)


def compile_decision_intelligence_brief(
    *,
    health: MeridianModelHealthReceipt | None,
    pack: MMMModelReviewPack | None,
) -> MMMDecisionIntelligenceBrief:
    verified: list[str] = []
    reviews: list[str] = []
    limitations: list[str] = []
    recommendations: list[DecisionIntelligenceRecommendation] = []
    model_version_id = ""
    fit_run_id = None
    if health is not None:
        model_version_id = health.model_version_id
        fit_run_id = health.fit_run_id
        for check in health.check_results:
            if check.status is OfficialHealthStatus.PASS:
                verified.append(f"{check.check_name}={check.status.value}")
            elif check.status is OfficialHealthStatus.REVIEW:
                reviews.append(check.check_name)
            elif check.status is OfficialHealthStatus.FAIL:
                reviews.append(check.check_name)
        if health.review_source is ReviewSource.FAKE_TEST:
            limitations.append("FAKE_TEST evidence is not production modeling experience.")
    if pack is not None:
        model_version_id = pack.model_version_id
        fit_run_id = pack.fit_run_id
        limitations.extend(pack.known_limitations)
        for item in pack.review_required_items:
            if item not in pack.acknowledged_review_items:
                recommendations.append(
                    DecisionIntelligenceRecommendation(
                        recommendation_id=f"ack-{item}",
                        statement=f"Acknowledge official REVIEW item {item} before acceptance.",
                        evidence_refs=(pack.fingerprint,),
                        authority=DecisionIntelligenceAuthority.DECISION_REQUIRED,
                        requires_human_decision=True,
                    )
                )
    headline = "No grounded modeling recommendation."
    summary = "Decision Intelligence is empty until official review evidence exists."
    if verified and health is not None and health.review_source is ReviewSource.OFFICIAL_MERIDIAN:
        headline = "Official Meridian review evidence is available."
        summary = "Typed reviewer statuses are the authority; Gemini may explain them only."
    return MMMDecisionIntelligenceBrief(
        model_version_id=model_version_id or "unknown",
        fit_run_id=fit_run_id,
        headline=headline,
        summary=summary,
        verified_findings=tuple(verified),
        review_items=tuple(reviews),
        limitations=tuple(limitations),
        recommendations=tuple(recommendations),
        evidence_refs=() if pack is None else (pack.fingerprint,),
        model_health_receipt_ref=None if health is None else health.fit_run_id,
        review_pack_ref=None if pack is None else pack.fingerprint,
    )
