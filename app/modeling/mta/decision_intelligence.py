"""Deterministic MTA Decision Intelligence compiler. No LLM narrative."""

from __future__ import annotations

from app.core.contracts import utc_now
from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.language import assert_result_payload_language
from app.modeling.mta.results_contracts import (
    DECISION_INTELLIGENCE_POLICY_VERSION,
    ChannelRoleEvidence,
    ChannelRoleLabel,
    DecisionIntelligenceFinding,
    DecisionIntelligenceRecommendation,
    DecisionRequirement,
    MetricAvailability,
    MTAChannelResult,
    MTADecisionIntelligenceBrief,
    MTAFindingAuthority,
    MTAJourneySummary,
    MTAModelSensitivityEvidence,
    MTAObservabilitySummary,
    MTAResultsCompileError,
    MTAResultsCompileFailureClass,
    MTAResultsSnapshot,
    ObservabilityStatus,
    SensitivityLabel,
    ShapleyAttributionEvidence,
)

BUDGET_FORBIDDEN = (
    "increase ",
    "cut ",
    "spend by",
    "reallocation",
    "budget",
    "move $",
    "incremental revenue",
    "caused $",
)


def _finding(
    *,
    finding_id: str,
    authority: MTAFindingAuthority,
    title: str,
    statement: str,
    evidence_refs: tuple[str, ...],
    channels: tuple[str, ...] = (),
    materiality: str = "CONTEXTUAL",
) -> DecisionIntelligenceFinding:
    return DecisionIntelligenceFinding(
        finding_id=finding_id,
        authority=authority,
        title=title,
        statement=statement,
        evidence_refs=evidence_refs,
        materiality=materiality,
        affected_channels=channels,
    )


class MTADecisionIntelligenceCompiler:
    def compile(
        self,
        *,
        snapshot: MTAResultsSnapshot,
        channel_results: tuple[MTAChannelResult, ...],
        roles: tuple[ChannelRoleEvidence, ...],
        sensitivity: tuple[MTAModelSensitivityEvidence, ...],
        journeys: MTAJourneySummary,
        shapley: ShapleyAttributionEvidence,
        observability: MTAObservabilitySummary,
        policy_version: str = DECISION_INTELLIGENCE_POLICY_VERSION,
    ) -> MTADecisionIntelligenceBrief:
        try:
            return self._compile(
                snapshot=snapshot,
                channel_results=channel_results,
                roles=roles,
                sensitivity=sensitivity,
                journeys=journeys,
                shapley=shapley,
                observability=observability,
                policy_version=policy_version,
            )
        except MTAResultsCompileError:
            raise
        except Exception as exc:
            raise MTAResultsCompileError(
                str(exc),
                failure_class=MTAResultsCompileFailureClass.MTA_DECISION_BRIEF_ERROR,
            ) from exc

    def _compile(
        self,
        *,
        snapshot: MTAResultsSnapshot,
        channel_results: tuple[MTAChannelResult, ...],
        roles: tuple[ChannelRoleEvidence, ...],
        sensitivity: tuple[MTAModelSensitivityEvidence, ...],
        journeys: MTAJourneySummary,
        shapley: ShapleyAttributionEvidence,
        observability: MTAObservabilitySummary,
        policy_version: str,
    ) -> MTADecisionIntelligenceBrief:
        refs_base = (
            snapshot.result_snapshot_id,
            snapshot.channel_results_ref,
            snapshot.journey_summary_ref,
        )
        verified: list[DecisionIntelligenceFinding] = [
            _finding(
                finding_id="vf_journey_count",
                authority=MTAFindingAuthority.VERIFIED,
                title="Converted journeys",
                statement=(
                    f"{journeys.converted_journey_count} converted journeys were compiled "
                    f"from the verified MTA run {snapshot.run_id}."
                ),
                evidence_refs=(snapshot.journey_summary_ref,),
                materiality="MATERIAL",
            ),
            _finding(
                finding_id="vf_models_completed",
                authority=MTAFindingAuthority.VERIFIED,
                title="Completed models",
                statement=(
                    "Completed attribution models: " + ", ".join(snapshot.models_completed) + "."
                ),
                evidence_refs=(snapshot.model_comparison_ref,),
                materiality="MATERIAL",
            ),
        ]
        interpretations: list[DecisionIntelligenceFinding] = []
        recommendations: list[DecisionIntelligenceRecommendation] = []
        counter: list[str] = []
        uncertainties: list[str] = []
        decisions: list[DecisionRequirement] = []
        role_by_channel = {item.channel_id: item for item in roles}

        for role in roles:
            if ChannelRoleLabel.INTRODUCER in role.labels:
                interpretations.append(
                    _finding(
                        finding_id=f"int_intro_{role.channel_id}",
                        authority=MTAFindingAuthority.INTERPRETATION,
                        title=f"{role.channel_id} appears earlier in observed journeys",
                        statement=(
                            f"{role.channel_id} appears frequently earlier in observable "
                            f"paths (first_position_share="
                            f"{role.first_position_share}). This is an observed journey "
                            "role, not a demand-creation claim."
                        ),
                        evidence_refs=role.evidence_refs or refs_base,
                        channels=(role.channel_id,),
                    )
                )
            if ChannelRoleLabel.CONVERTER in role.labels:
                interpretations.append(
                    _finding(
                        finding_id=f"int_conv_{role.channel_id}",
                        authority=MTAFindingAuthority.INTERPRETATION,
                        title=f"{role.channel_id} appears closer to conversion",
                        statement=(
                            f"{role.channel_id} appears closer to conversion in this MTA "
                            f"run (last_position_share={role.last_position_share})."
                        ),
                        evidence_refs=role.evidence_refs or refs_base,
                        channels=(role.channel_id,),
                    )
                )
            if ChannelRoleLabel.ASSISTER in role.labels:
                interpretations.append(
                    _finding(
                        finding_id=f"int_assist_{role.channel_id}",
                        authority=MTAFindingAuthority.INTERPRETATION,
                        title=f"{role.channel_id} appears mid-path",
                        statement=(
                            f"{role.channel_id} has material middle-position presence "
                            f"(middle_position_share={role.middle_position_share})."
                        ),
                        evidence_refs=role.evidence_refs or refs_base,
                        channels=(role.channel_id,),
                    )
                )
            if ChannelRoleLabel.DIRECT_CAPTURE in role.labels:
                interpretations.append(
                    _finding(
                        finding_id="int_direct_capture",
                        authority=MTAFindingAuthority.INTERPRETATION,
                        title="Direct closes many returning observable journeys",
                        statement=(
                            "Direct shows high closing presence under the configured "
                            "Direct policy. Direct is not treated as a media investment channel."
                        ),
                        evidence_refs=role.evidence_refs or refs_base,
                        channels=("direct",),
                    )
                )
                decisions.append(
                    DecisionRequirement(
                        requirement_id="dec_direct_policy",
                        decision_type="REVIEW_DIRECT_POLICY",
                        statement=(
                            "Review Direct policy if conclusions materially change under "
                            "last-non-direct treatment."
                        ),
                        evidence_refs=role.evidence_refs or refs_base,
                    )
                )
                recommendations.append(
                    DecisionIntelligenceRecommendation(
                        recommendation_id="rec_direct_policy",
                        statement=(
                            "Review Direct policy if last-non-direct would change which "
                            "channels receive closing credit."
                        ),
                        evidence_refs=role.evidence_refs or refs_base,
                        counterevidence_refs=(
                            "Last-non-direct may reassign Direct-closing journeys to "
                            "the prior eligible channel.",
                        ),
                        uncertainty=(
                            "Direct closing share depends on the configured Direct treatment."
                        ),
                        recommended_action="REVIEW_DIRECT_POLICY",
                    )
                )

        for item in sensitivity:
            if item.sensitivity_label in (
                SensitivityLabel.HIGH,
                SensitivityLabel.VERY_HIGH,
            ):
                interpretations.append(
                    _finding(
                        finding_id=f"int_sens_{item.channel_id}",
                        authority=MTAFindingAuthority.INTERPRETATION,
                        title=f"{item.channel_id} credit changes across models",
                        statement=(
                            f"{item.channel_id} attribution is materially sensitive to the "
                            f"attribution assumption (dispersion={item.dispersion}, "
                            f"label={item.sensitivity_label.value}). "
                            "This is model disagreement, not a confidence interval."
                        ),
                        evidence_refs=(snapshot.model_comparison_ref,),
                        channels=(item.channel_id,),
                        materiality="MATERIAL",
                    )
                )
                recommendations.append(
                    DecisionIntelligenceRecommendation(
                        recommendation_id=f"rec_sens_{item.channel_id}",
                        statement=(
                            f"Consider an incrementality experiment where {item.channel_id} "
                            "MTA model sensitivity is high, once "
                            "cross-method analysis is available."
                        ),
                        evidence_refs=(snapshot.model_comparison_ref,),
                        counterevidence_refs=(
                            f"A single heuristic (for example last-touch) may still be "
                            f"stable for {item.channel_id} even when the full model set disagrees.",
                        ),
                        uncertainty=(
                            "Cross-model range is disagreement among attribution assumptions, "
                            "not statistical uncertainty."
                        ),
                        recommended_action="REVIEW_MODEL_SENSITIVITY",
                    )
                )
                counter.append(
                    f"{item.channel_id} model range is assumption "
                    "disagreement, not over/under-valuation."
                )

        if shapley.availability is not MetricAvailability.AVAILABLE:
            decisions.append(
                DecisionRequirement(
                    requirement_id="dec_shapley",
                    decision_type="REVIEW_SHAPLEY_CONFIGURATION",
                    statement=(
                        shapley.unavailable_reason
                        or "Shapley was not run; decide whether to relax preflight or omit it."
                    ),
                    evidence_refs=(snapshot.result_snapshot_id,),
                )
            )
        elif shapley.path_limit_applied:
            recommendations.append(
                DecisionIntelligenceRecommendation(
                    recommendation_id="rec_shapley_limit",
                    statement=(
                        "Review Shapley path-limit assumptions if path lengths exceed "
                        f"configured size={shapley.size}."
                    ),
                    evidence_refs=(snapshot.shapley_evidence_ref or snapshot.result_snapshot_id,),
                    counterevidence_refs=(
                        "Shorter observed paths may already be fully "
                        "represented at the pinned size.",
                    ),
                    uncertainty="Truncation changes coalition membership for longer paths.",
                    recommended_action="REVIEW_SHAPLEY_LIMITATION",
                )
            )
            uncertainties.append("SHAPLEY_PATH_LIMIT_APPLIED")

        if observability.status in (
            ObservabilityStatus.REVIEW,
            ObservabilityStatus.LIMITED,
        ):
            interpretations.append(
                _finding(
                    finding_id="int_observability",
                    authority=MTAFindingAuthority.INTERPRETATION,
                    title="Observability constrains role confidence",
                    statement=(
                        f"Observability status is {observability.status.value}. "
                        "Low observability constrains interpretation confidence; "
                        "it does not automatically invalidate all MTA evidence."
                    ),
                    evidence_refs=(snapshot.result_snapshot_id,),
                    materiality="MATERIAL",
                )
            )
            decisions.append(
                DecisionRequirement(
                    requirement_id="dec_observability",
                    decision_type="REVIEW_LOW_OBSERVABILITY",
                    statement=(
                        "Review identity, mapping, or traffic-source coverage "
                        "before treating roles as stable."
                    ),
                    evidence_refs=(snapshot.result_snapshot_id,),
                )
            )

        unmapped = [
            c.channel_id
            for c in channel_results
            if any(lim.limitation_type.value == "UNMAPPED_TRAFFIC" for lim in c.limitations)
        ]
        if unmapped or any(
            lim.limitation_type.value == "UNMAPPED_TRAFFIC" for lim in snapshot.limitations
        ):
            decisions.append(
                DecisionRequirement(
                    requirement_id="dec_mapping",
                    decision_type="REVIEW_CHANNEL_MAPPING",
                    statement=(
                        "Investigate unmapped or unclassified traffic before "
                        "comparing channel roles."
                    ),
                    evidence_refs=(snapshot.channel_results_ref,),
                )
            )
            recommendations.append(
                DecisionIntelligenceRecommendation(
                    recommendation_id="rec_mapping",
                    statement="Investigate unmapped/referral traffic in the channel grouping.",
                    evidence_refs=(snapshot.channel_results_ref,),
                    counterevidence_refs=(
                        "Unmapped volume may be small enough that ranked "
                        "media channels are unaffected.",
                    ),
                    uncertainty=(
                        "Unmapped share may be a mapping issue rather than "
                        "a true other channel."
                    ),
                    recommended_action="REVIEW_CHANNEL_MAPPING",
                )
            )

        if len(snapshot.models_completed) >= 2:
            decisions.append(
                DecisionRequirement(
                    requirement_id="dec_compare",
                    decision_type="CHOOSE_RESULT_FOR_COMPARISON",
                    statement=(
                        "Choose which attribution models to display for comparison; "
                        "filtering is presentation-only and does not rerun MTA."
                    ),
                    evidence_refs=(snapshot.model_comparison_ref,),
                )
            )

        for rec in recommendations:
            if not rec.evidence_refs:
                raise MTAResultsCompileError(
                    "Recommendation missing evidence refs",
                    failure_class=MTAResultsCompileFailureClass.MTA_DECISION_BRIEF_ERROR,
                )
            if not rec.counterevidence_refs and not rec.uncertainty:
                raise MTAResultsCompileError(
                    "Material recommendation requires counter-evidence or uncertainty",
                    failure_class=MTAResultsCompileFailureClass.MTA_DECISION_BRIEF_ERROR,
                )

        summary = (
            f"Verified MTA snapshot {snapshot.result_snapshot_id} compiled "
            f"{journeys.converted_journey_count} converted journeys across "
            f"{len(snapshot.models_completed)} models. "
            f"Observability is {observability.status.value}."
        )
        if role_by_channel.get("ai_search"):
            interpretations.append(
                _finding(
                    finding_id="int_ai_search",
                    authority=MTAFindingAuthority.INTERPRETATION,
                    title="AI Search is present in observed journeys",
                    statement=(
                        "ai_search appears in this result snapshot because the source "
                        "traffic mapped to that canonical channel_id."
                    ),
                    evidence_refs=refs_base,
                    channels=("ai_search",),
                )
            )
        payload = {
            "snapshot": snapshot.result_snapshot_id,
            "policy": policy_version,
            "summary": summary,
            "verified": [f.statement for f in verified],
            "interpretations": [f.statement for f in interpretations],
            "recommendations": [r.statement for r in recommendations],
        }
        brief = MTADecisionIntelligenceBrief(
            brief_id=f"mdib_{canonical_fingerprint(payload)[:20]}",
            project_id=snapshot.project_id,
            cycle_id=snapshot.cycle_id,
            track_id=snapshot.track_id,
            result_snapshot_id=snapshot.result_snapshot_id,
            executive_summary=summary,
            verified_findings=tuple(verified),
            interpretations=tuple(interpretations),
            recommendations=tuple(recommendations),
            counter_evidence=tuple(counter),
            uncertainties=tuple(uncertainties),
            decision_requirements=tuple(decisions),
            limitations=snapshot.limitations,
            evidence_refs=refs_base,
            policy_version=policy_version,
            generated_at=utc_now(),
            fingerprint=canonical_fingerprint(payload),
        )
        dumped = brief.model_dump(mode="json")
        assert_result_payload_language(dumped)
        text_blob = " ".join(str(v) for v in dumped.values())
        lowered = text_blob.lower()
        for token in BUDGET_FORBIDDEN:
            if token in lowered and token != "incrementality experiment":
                # Allow "incrementality experiment" recommendation; block spend/budget.
                if (
                    token == "increase "
                    or token == "cut "
                    or token == "budget"
                    or token == "spend by"
                ):
                    raise MTAResultsCompileError(
                        f"Brief contains prohibited budget language: {token}",
                        failure_class=MTAResultsCompileFailureClass.MTA_DECISION_BRIEF_ERROR,
                    )
        return brief
