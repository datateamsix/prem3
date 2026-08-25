"""Typed MMM post-fit results and Decision Intelligence foundation (M4-00)."""

from __future__ import annotations

from app.modeling.mmm.results.contracts import (
    ACCEPTED_MODEL_RESULTS,
    PRE_ACCEPTANCE_RESULTS,
    AdvisorRecommendation,
    CounterEvidence,
    DecisionIntelligenceFinding,
    DecisionRequirement,
    EvidenceEligibility,
    IntervalEvidence,
    MarginalEfficiencyEvidence,
    MetricAvailability,
    MetricValue,
    ModelFitEvidence,
    ModelLimitation,
    MMMChannelResult,
    MMMDecisionIntelligenceBrief,
    MMMPortfolioSummary,
    MMMResultStatus,
    MMMResultsSnapshot,
    MMMResultsUnavailable,
    ResponseCurveEvidence,
    ResponseCurvePoint,
    ResultProvenance,
)

ADAPTER_VERSION = "m4-00.1"
METRIC_EXTRACTION_POLICY_VERSION = "m4-00.1"
MERIDIAN_RUNTIME_VERSION = "1.8.0"

__all__ = [
    "ACCEPTED_MODEL_RESULTS",
    "ADAPTER_VERSION",
    "MERIDIAN_RUNTIME_VERSION",
    "METRIC_EXTRACTION_POLICY_VERSION",
    "PRE_ACCEPTANCE_RESULTS",
    "AdvisorRecommendation",
    "CounterEvidence",
    "DecisionIntelligenceFinding",
    "DecisionRequirement",
    "EvidenceEligibility",
    "IntervalEvidence",
    "MarginalEfficiencyEvidence",
    "MetricAvailability",
    "MetricValue",
    "ModelFitEvidence",
    "ModelLimitation",
    "MMMChannelResult",
    "MMMDecisionIntelligenceBrief",
    "MMMPortfolioSummary",
    "MMMResultStatus",
    "MMMResultsSnapshot",
    "MMMResultsUnavailable",
    "ResponseCurveEvidence",
    "ResponseCurvePoint",
    "ResultProvenance",
]
