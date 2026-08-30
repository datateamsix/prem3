"""Optimization domain errors. Codes are machine-stable."""

from __future__ import annotations

from app.investment_planning.errors import PlanningError


class OptimizationError(PlanningError):
    code = "OPTIMIZATION_ERROR"


class OptimizationNotConfiguredError(OptimizationError):
    code = "NOT_CONFIGURED"


class ApprovedPlanRequiredError(OptimizationError):
    code = "APPROVED_PLAN_REQUIRED"


class FuzzyMappingRejectedError(OptimizationError):
    code = "FUZZY_MAPPING_NOT_AUTHORITY"


class CrossProjectMappingError(OptimizationError):
    code = "CROSS_PROJECT_MODEL_MAPPING"


class CrossTenantMappingError(OptimizationError):
    code = "CROSS_TENANT_MODEL_MAPPING"


class OptimizationNotReadyError(OptimizationError):
    code = "OPTIMIZATION_NOT_READY"


class OptimizationReviewRequiredError(OptimizationError):
    code = "OPTIMIZATION_REVIEW_REQUIRED"


class OptimizationReadinessStaleError(OptimizationError):
    code = "OPTIMIZATION_READINESS_STALE"


class UnapprovedPlanError(OptimizationError):
    code = "UNAPPROVED_PLAN"


class ActualsNotFixedBudgetError(OptimizationError):
    code = "ACTUALS_NOT_FIXED_BUDGET"


class ClientBudgetArrayRejectedError(OptimizationError):
    code = "CLIENT_BUDGET_ARRAY_REJECTED"


class ModelArtifactUnavailableError(OptimizationError):
    code = "MODEL_ARTIFACT_UNAVAILABLE"


class NativeOptimizerFailedError(OptimizationError):
    code = "NATIVE_OPTIMIZER_FAILED"


class MeridianOptimizerApiReviewRequiredError(OptimizationError):
    code = "MERIDIAN_OPTIMIZER_API_REVIEW_REQUIRED"


class OptimizerResultInvalidError(OptimizationError):
    code = "OPTIMIZER_RESULT_INVALID"


class OptimizerBudgetInvariantFailedError(OptimizationError):
    code = "OPTIMIZER_BUDGET_INVARIANT_FAILED"


class ResultReadbackFailedError(OptimizationError):
    code = "RESULT_READBACK_FAILED"


class FlexibleBudgetNotImplementedError(OptimizationError):
    code = "FLEXIBLE_BUDGET_NOT_IMPLEMENTED"


class FlexibleBudgetApiUnsupportedError(OptimizationError):
    code = "FLEXIBLE_BUDGET_API_UNSUPPORTED"


class ObjectiveNotSupportedError(OptimizationError):
    code = "OBJECTIVE_NOT_SUPPORTED"


class FinancialValueAssumptionRequiredError(OptimizationError):
    code = "FINANCIAL_VALUE_ASSUMPTION_REQUIRED"


class FutureCostAssumptionInvalidError(OptimizationError):
    code = "FUTURE_COST_ASSUMPTION_INVALID"


class FlightingAssumptionInvalidError(OptimizationError):
    code = "FLIGHTING_ASSUMPTION_INVALID"


class ConstraintSetInfeasibleError(OptimizationError):
    code = "CONSTRAINT_SET_INFEASIBLE"

    def __init__(self, message: str, *, conflicting_constraint_ids: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.conflicting_constraint_ids = conflicting_constraint_ids


class ConstraintReferenceInvalidError(OptimizationError):
    code = "CONSTRAINT_REFERENCE_INVALID"


class ConstraintUnitMismatchError(OptimizationError):
    code = "CONSTRAINT_UNIT_MISMATCH"


class AdvancedReadinessStaleError(OptimizationError):
    code = "ADVANCED_READINESS_STALE"


class ResultConstraintViolationError(OptimizationError):
    code = "RESULT_CONSTRAINT_VIOLATION"


class FunnelMappingRequiredError(OptimizationError):
    code = "FUNNEL_MAPPING_REQUIRED"


class ProxyApprovalRequiredError(OptimizationError):
    code = "PROXY_APPROVAL_REQUIRED"


class AssumptionSetNotFoundError(OptimizationError):
    code = "ASSUMPTION_SET_NOT_FOUND"


class ConstraintSetNotFoundError(OptimizationError):
    code = "CONSTRAINT_SET_NOT_FOUND"


class CrossProjectRunAccessError(OptimizationError):
    code = "CROSS_PROJECT_RUN_ACCESS"


class CrossTenantRunAccessError(OptimizationError):
    code = "CROSS_TENANT_RUN_ACCESS"


class OptimizationRunNotFoundError(OptimizationError):
    code = "OPTIMIZATION_RUN_NOT_FOUND"


class ScenarioRequiresCompletedOptimizationError(OptimizationError):
    code = "SCENARIO_REQUIRES_COMPLETED_OPTIMIZATION"


class ScenarioNotFoundError(OptimizationError):
    code = "SCENARIO_NOT_FOUND"


class ScenarioImmutableError(OptimizationError):
    code = "SCENARIO_IMMUTABLE"


class ProposalNotFoundError(OptimizationError):
    code = "PROPOSAL_NOT_FOUND"


class ProposalNotReadyError(OptimizationError):
    code = "PROPOSAL_NOT_READY"


class ProposalStaleError(OptimizationError):
    code = "PROPOSAL_STALE"


class ProposalSourcePlanStaleError(OptimizationError):
    code = "PROPOSAL_SOURCE_PLAN_STALE"


class SubmittedProposalImmutableError(OptimizationError):
    code = "SUBMITTED_PROPOSAL_IMMUTABLE"


class InvalidProposalTransitionError(OptimizationError):
    code = "INVALID_PROPOSAL_TRANSITION"


class ProposalNotApprovedError(OptimizationError):
    code = "PROPOSAL_NOT_APPROVED"


class DecisionReceiptImmutableError(OptimizationError):
    code = "DECISION_RECEIPT_IMMUTABLE"


class CrossProjectProposalAccessError(OptimizationError):
    code = "CROSS_PROJECT_PROPOSAL_ACCESS"


class CrossTenantProposalAccessError(OptimizationError):
    code = "CROSS_TENANT_PROPOSAL_ACCESS"


class RiskNeutralParityFailedError(OptimizationError):
    code = "RISK_NEUTRAL_PARITY_FAILED"


class RiskPolicyInvalidError(OptimizationError):
    code = "RISK_POLICY_INVALID"


class RiskInputNotReadyError(OptimizationError):
    code = "RISK_INPUT_NOT_READY"


class PosteriorRiskUnavailableError(OptimizationError):
    code = "POSTERIOR_RISK_UNAVAILABLE"


class ScenarioRiskUnavailableError(OptimizationError):
    code = "SCENARIO_RISK_UNAVAILABLE"


class ExposureRiskNotQualifiedError(OptimizationError):
    code = "EXPOSURE_RISK_NOT_QUALIFIED"


class CandidateGenerationFailedError(OptimizationError):
    code = "CANDIDATE_GENERATION_FAILED"


class CandidateInfeasibleError(OptimizationError):
    code = "CANDIDATE_INFEASIBLE"


class InsufficientFrontierCandidatesError(OptimizationError):
    code = "INSUFFICIENT_FRONTIER_CANDIDATES"


class FrontierDominancePolicyInvalidError(OptimizationError):
    code = "FRONTIER_DOMINANCE_POLICY_INVALID"


class FrontierSelectionNotAllowedError(OptimizationError):
    code = "FRONTIER_SELECTION_NOT_ALLOWED"


class RiskArtifactFingerprintMismatchError(OptimizationError):
    code = "RISK_ARTIFACT_FINGERPRINT_MISMATCH"


class RiskPolicyNotFoundError(OptimizationError):
    code = "RISK_POLICY_NOT_FOUND"


class CandidateNotFoundError(OptimizationError):
    code = "CANDIDATE_NOT_FOUND"


class RiskEvaluationNotFoundError(OptimizationError):
    code = "RISK_EVALUATION_NOT_FOUND"


class FrontierNotFoundError(OptimizationError):
    code = "FRONTIER_NOT_FOUND"


class FrontierSelectionNotFoundError(OptimizationError):
    code = "FRONTIER_SELECTION_NOT_FOUND"


class ParityReceiptNotFoundError(OptimizationError):
    code = "PARITY_RECEIPT_NOT_FOUND"


class SimulationInputNotReadyError(OptimizationError):
    code = "SIMULATION_INPUT_NOT_READY"


class ScenarioDistributionNotGovernedError(OptimizationError):
    code = "SCENARIO_DISTRIBUTION_NOT_GOVERNED"


class ScenarioCorrelationInvalidError(OptimizationError):
    code = "SCENARIO_CORRELATION_INVALID"


class PosteriorSimulationSourceUnavailableError(OptimizationError):
    code = "POSTERIOR_SIMULATION_SOURCE_UNAVAILABLE"


class SimulationPolicyInvalidError(OptimizationError):
    code = "SIMULATION_POLICY_INVALID"


class SimulationLimitExceededError(OptimizationError):
    code = "SIMULATION_LIMIT_EXCEEDED"


class SimulationRuntimeUnavailableError(OptimizationError):
    code = "SIMULATION_RUNTIME_UNAVAILABLE"


class SimulationExecutionFailedError(OptimizationError):
    code = "SIMULATION_EXECUTION_FAILED"


class SimulationArtifactWriteFailedError(OptimizationError):
    code = "SIMULATION_ARTIFACT_WRITE_FAILED"


class SimulationFingerprintMismatchError(OptimizationError):
    code = "SIMULATION_FINGERPRINT_MISMATCH"


class SimulationOutputInvalidError(OptimizationError):
    code = "SIMULATION_OUTPUT_INVALID"


class SimulationCandidateInvalidError(OptimizationError):
    code = "SIMULATION_CANDIDATE_INVALID"


class SimulationInsufficientDrawsForTailError(OptimizationError):
    code = "SIMULATION_INSUFFICIENT_DRAWS_FOR_TAIL_METRIC"


class LiveSimulationJobProofPendingError(OptimizationError):
    code = "LIVE_SIMULATION_JOB_PROOF_PENDING"


class SimulationNotFoundError(OptimizationError):
    code = "SIMULATION_NOT_FOUND"
