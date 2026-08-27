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


class CrossProjectRunAccessError(OptimizationError):
    code = "CROSS_PROJECT_RUN_ACCESS"


class CrossTenantRunAccessError(OptimizationError):
    code = "CROSS_TENANT_RUN_ACCESS"


class OptimizationRunNotFoundError(OptimizationError):
    code = "OPTIMIZATION_RUN_NOT_FOUND"
