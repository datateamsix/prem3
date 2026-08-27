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
